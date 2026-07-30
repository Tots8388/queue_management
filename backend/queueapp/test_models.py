"""
Phase 1 tests: the data model holds what the spec says it holds, and nothing
it says it must not.
"""

from concurrent.futures import ThreadPoolExecutor

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from .models import (
    AuditLogEntry,
    NotificationContact,
    PharmacyOutcome,
    PriorityChange,
    Role,
    ServiceCounter,
    StageEvent,
    StaffUser,
    Visit,
    format_token,
)


class TokenTests(TestCase):
    def test_default_format_matches_the_spec_example(self):
        self.assertEqual(format_token(41), "T-041")

    @override_settings(TOKEN={"PREFIX": "A", "SEPARATOR": "", "DIGITS": 3})
    def test_format_is_configurable_to_the_prototype_style(self):
        """The approved prototypes show A017; the format is a setting."""
        self.assertEqual(format_token(17), "A017")

    def test_tokens_are_issued_in_sequence(self):
        tokens = [Visit.check_in().token for _ in range(3)]
        self.assertEqual(tokens, ["T-001", "T-002", "T-003"])

    def test_a_visit_keeps_one_token_across_every_stage(self):
        """Spec: a single visit identity, not per-stage tickets."""
        visit = Visit.check_in()
        issued = visit.token

        for stage in ["vitals", "consultation", "pharmacy", "complete"]:
            visit.current_stage = stage
            visit.save()
            visit.refresh_from_db()
            self.assertEqual(visit.token, issued)

    def test_the_same_token_cannot_be_issued_twice_in_a_day(self):
        Visit.check_in()
        with self.assertRaises(Exception):
            with transaction.atomic():
                Visit.objects.create(token="T-001", token_date=timezone.localdate())


class ConcurrentCheckInTests(TransactionTestCase):
    """
    Several reception terminals check people in at once. Two patients holding
    the same token would be a serious operational failure, so allocation takes
    a row lock rather than reading MAX+1.
    """

    def test_parallel_check_ins_produce_distinct_tokens(self):
        if connection.vendor == "sqlite":
            self.skipTest("SQLite serialises writers; this proves nothing there.")

        def check_in():
            try:
                return Visit.check_in().token
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=8) as pool:
            tokens = list(pool.map(lambda _: check_in(), range(24)))

        self.assertEqual(len(set(tokens)), len(tokens))


class VisitTests(TestCase):
    def test_a_new_visit_is_routine_and_waiting_at_registration(self):
        visit = Visit.check_in()

        self.assertEqual(visit.current_stage, "registration")
        self.assertEqual(visit.stage_status, Visit.StageStatus.WAITING)
        self.assertEqual(visit.priority, Visit.Priority.ROUTINE)
        self.assertEqual(visit.presence_status, Visit.Presence.WAITING)

    def test_check_in_time_is_recorded(self):
        """Spec FR1, and the basis of routine ordering within a stage."""
        before = timezone.now()
        visit = Visit.check_in()
        self.assertGreaterEqual(visit.check_in_time, before)

    def test_public_destination_prefers_the_assigned_counter(self):
        counter = ServiceCounter.objects.create(
            name="Consultation Room 2", stage="consultation"
        )
        visit = Visit.check_in(current_stage="consultation", assigned_counter=counter)

        self.assertEqual(visit.public_destination, "Consultation Room 2")

    def test_public_destination_falls_back_to_the_stage_name(self):
        visit = Visit.check_in(current_stage="consultation")
        self.assertEqual(visit.public_destination, "Consultation")

    def test_the_visit_model_stores_no_patient_identity(self):
        """
        The privacy constraint, asserted rather than assumed: adding a name,
        diagnosis, symptom or prescription field to Visit should fail here.
        """
        fields = {field.name for field in Visit._meta.get_fields()}
        forbidden = {
            "name",
            "patient_name",
            "first_name",
            "last_name",
            "national_id",
            "student_id",
            "diagnosis",
            "symptoms",
            "prescription",
            "medication",
            "notes",
        }

        self.assertEqual(fields & forbidden, set())


class StageEventTests(TestCase):
    def setUp(self):
        self.visit = Visit.check_in()

    def test_duration_is_none_until_the_stage_completes(self):
        event = StageEvent.objects.create(visit=self.visit, stage="vitals")
        self.assertIsNone(event.duration_seconds)

        event.completed_at = event.entered_at + timezone.timedelta(minutes=6)
        event.save()
        self.assertEqual(event.duration_seconds, 360)

    def test_returning_after_tests_preserves_earlier_history(self):
        """
        Spec FR13: a patient sent for lab tests returns to the clinician without
        losing prior stage history.
        """
        first = StageEvent.objects.create(
            visit=self.visit,
            stage="consultation",
            completed_at=timezone.now(),
            completed_by_role=Role.CLINICIAN,
        )
        self.visit.awaiting_tests = True
        self.visit.save()

        # Patient comes back — a new consultation event, not an overwrite.
        second = StageEvent.objects.create(visit=self.visit, stage="consultation")

        events = list(self.visit.stage_events.filter(stage="consultation"))
        self.assertEqual(events, [first, second])
        self.assertIsNotNone(events[0].completed_at)

    def test_events_read_in_the_order_they_happened(self):
        for stage in ["registration", "vitals", "consultation"]:
            StageEvent.objects.create(visit=self.visit, stage=stage)

        self.assertEqual(
            [event.stage for event in self.visit.stage_events.all()],
            ["registration", "vitals", "consultation"],
        )


class PriorityChangeTests(TestCase):
    def setUp(self):
        self.visit = Visit.check_in()

    def _change(self, role):
        return PriorityChange(
            visit=self.visit,
            previous_priority=Visit.Priority.ROUTINE,
            new_priority=Visit.Priority.EMERGENCY,
            changed_by_role=role,
            non_sensitive_reason="Clinical assessment at triage",
        )

    def test_clinical_roles_may_assign_priority(self):
        """Spec FR3: nurse/triage and clinician."""
        for role in [Role.NURSE_VITALS, Role.CLINICIAN]:
            with self.subTest(role=role):
                self._change(role).full_clean()

    def test_non_clinical_roles_may_not_assign_priority(self):
        """Spec FR3: reception and pharmacy cannot, nor can supervisor or IT."""
        for role in [
            Role.REGISTRATION_CLERK,
            Role.PHARMACIST,
            Role.SUPERVISOR,
            Role.IT_SUPPORT,
        ]:
            with self.subTest(role=role):
                with self.assertRaises(ValidationError) as raised:
                    self._change(role).full_clean()
                self.assertIn("changed_by_role", raised.exception.message_dict)

    def test_a_change_records_role_timestamp_and_reason(self):
        """Spec FR5."""
        change = self._change(Role.CLINICIAN)
        change.save()

        self.assertEqual(change.changed_by_role, Role.CLINICIAN)
        self.assertIsNotNone(change.timestamp)
        self.assertTrue(change.non_sensitive_reason)


class PharmacyOutcomeTests(TestCase):
    def test_the_three_specified_states_exist(self):
        """Spec FR10 — and nothing about what the medicine is."""
        self.assertEqual(
            [state.value for state in PharmacyOutcome.State],
            ["medicine_ready", "medicine_issued", "medicine_unavailable"],
        )

    def test_outcome_records_no_medicine_detail(self):
        fields = {field.name for field in PharmacyOutcome._meta.get_fields()}
        self.assertEqual(
            fields & {"medicine", "drug", "prescription", "dosage"}, set()
        )


class AuditLogEntryTests(TestCase):
    def test_entry_survives_the_daily_purge_of_visits(self):
        """
        Live tokens are purged at end of day while audit logs are retained far
        longer, so the log holds the token as a string rather than a foreign key.
        """
        visit = Visit.check_in()
        entry = AuditLogEntry.objects.create(
            actor_role=Role.CLINICIAN,
            action="priority_change",
            visit_token=visit.token,
            non_sensitive_detail="Escalated to emergency",
        )

        visit.delete()
        entry.refresh_from_db()

        self.assertEqual(entry.visit_token, "T-001")

    def test_entry_survives_the_staff_account_being_removed(self):
        user = StaffUser.objects.create_user(
            username="clinician9", password="x", role=Role.CLINICIAN
        )
        entry = AuditLogEntry.objects.create(
            actor_staff_user=user, actor_role=Role.CLINICIAN, action="manual_reorder"
        )

        user.delete()
        entry.refresh_from_db()

        self.assertIsNone(entry.actor_staff_user)
        self.assertEqual(entry.actor_role, Role.CLINICIAN)


class StaffUserTests(TestCase):
    def test_only_clinical_roles_may_assign_priority(self):
        expected = {
            Role.REGISTRATION_CLERK: False,
            Role.NURSE_VITALS: True,
            Role.CLINICIAN: True,
            Role.PHARMACIST: False,
            Role.SUPERVISOR: False,
            Role.IT_SUPPORT: False,
        }

        for role, allowed in expected.items():
            with self.subTest(role=role):
                user = StaffUser(username=f"u_{role}", role=role)
                self.assertEqual(user.may_assign_priority, allowed)

    def test_the_six_specified_roles_exist(self):
        self.assertEqual(
            [role.value for role in Role],
            [
                "registration_clerk",
                "nurse_vitals",
                "clinician",
                "pharmacist",
                "supervisor",
                "it_support",
            ],
        )


class NotificationContactTests(TestCase):
    def test_the_phone_number_is_kept_off_the_visit_record(self):
        """
        A phone number identifies a person. Isolating it keeps the visit table
        anonymous and lets the number be purged on its own schedule.
        """
        visit_fields = {field.name for field in Visit._meta.get_fields()}
        self.assertNotIn("phone_number", visit_fields)

    def test_repr_never_discloses_the_number(self):
        visit = Visit.check_in()
        contact = NotificationContact.objects.create(
            visit=visit, phone_number="+254700000123"
        )

        self.assertNotIn("254700000123", str(contact))
