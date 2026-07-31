"""
Phase 8 tests: the audit trail and de-identified reporting.

The two halves are tested against each other: the trail must name an individual
for accountability actions, and the reports must never name anybody at all.
"""

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from . import audit, reporting
from .models import AuditLogEntry, PharmacyOutcome, Role, StaffUser, Visit
from .services import operations


def staff(role, username=None):
    return StaffUser.objects.create_user(
        username=username or f"aud_{role}", password="x", role=role
    )


class AuditWriteTests(TestCase):
    def setUp(self):
        self.clerk = staff(Role.REGISTRATION_CLERK)
        self.clinician = staff(Role.CLINICIAN)
        self.nurse = staff(Role.NURSE_VITALS)

    def test_a_priority_override_names_the_individual_who_made_it(self):
        """
        The identifiable layer: this is a decision someone may have to answer
        for.
        """
        visit = operations.check_in(actor=self.clerk)
        operations.set_priority(
            visit,
            priority=Visit.Priority.EMERGENCY,
            actor=self.clinician,
            reason="Collapsed in waiting area",
        )

        entry = AuditLogEntry.objects.get(action="priority_change")
        self.assertEqual(entry.actor_staff_user, self.clinician)
        self.assertEqual(entry.actor_role, Role.CLINICIAN)
        self.assertIn("Collapsed in waiting area", entry.non_sensitive_detail)
        self.assertEqual(entry.visit_token, visit.token)

    def test_a_manual_reorder_names_the_individual(self):
        first = operations.check_in(actor=self.clerk)
        second = operations.check_in(actor=self.clerk)

        operations.manual_reorder(
            second, actor=self.nurse, reason="Clinician requested", ahead_of=first
        )

        entry = AuditLogEntry.objects.get(action="manual_reorder")
        self.assertEqual(entry.actor_staff_user, self.nurse)

    def test_routine_work_is_recorded_against_the_role_only(self):
        """
        Attributing every keystroke to a named employee would make this staff
        surveillance rather than an accountability trail.
        """
        visit = operations.check_in(actor=self.clerk)
        operations.complete_stage(visit, actor=self.clerk)

        for action in ["check_in", "stage_complete"]:
            with self.subTest(action=action):
                entry = AuditLogEntry.objects.get(action=action)
                self.assertIsNone(entry.actor_staff_user)
                self.assertEqual(entry.actor_role, Role.REGISTRATION_CLERK)

    def test_key_completions_are_recorded(self):
        """Spec FR14: priority changes, manual reorders and key completions."""
        visit = operations.check_in(actor=self.clerk)
        visit.current_stage = "pharmacy"
        visit.save()
        operations.record_pharmacy_outcome(
            visit,
            state=PharmacyOutcome.State.ISSUED,
            actor=staff(Role.PHARMACIST),
        )

        actions = set(AuditLogEntry.objects.values_list("action", flat=True))
        self.assertIn("pharmacy_outcome", actions)
        self.assertIn("stage_complete", actions)

    def test_the_return_after_tests_path_is_recorded(self):
        visit = operations.check_in(actor=self.clerk)
        visit.current_stage = "consultation"
        visit.save()

        operations.send_for_tests(visit, actor=self.clinician)
        operations.return_after_tests(visit, actor=self.clinician)

        actions = set(AuditLogEntry.objects.values_list("action", flat=True))
        self.assertIn("sent_for_tests", actions)
        self.assertIn("returned_after_tests", actions)

    def test_an_unrecognised_action_is_not_written(self):
        from .services.operations import AuditFact

        audit.record(
            AuditFact(action="mystery", actor_role=Role.CLINICIAN, visit_token="T-001")
        )

        self.assertFalse(AuditLogEntry.objects.filter(action="mystery").exists())

    def test_a_phone_number_in_the_detail_is_redacted(self):
        """
        The one identifying value the system holds must not end up in its
        longest-retained table.
        """
        from .services.operations import AuditFact

        audit.record(
            AuditFact(
                action="check_in",
                actor_role=Role.REGISTRATION_CLERK,
                visit_token="T-001",
                detail="Contact given as +254700000123",
            )
        )

        entry = AuditLogEntry.objects.get(action="check_in")
        self.assertNotIn("254700000123", entry.non_sensitive_detail)
        self.assertIn("[redacted]", entry.non_sensitive_detail)

    def test_a_failed_audit_write_does_not_undo_the_clinical_action(self):
        """
        A patient must not be left un-escalated because a log table was
        unavailable.
        """
        visit = operations.check_in(actor=self.clerk)

        with patch.object(
            AuditLogEntry.objects, "create", side_effect=RuntimeError("db gone")
        ):
            operations.set_priority(
                visit,
                priority=Visit.Priority.EMERGENCY,
                actor=self.clinician,
                reason="Collapsed",
            )

        visit.refresh_from_db()
        self.assertEqual(visit.priority, Visit.Priority.EMERGENCY)


class AuditReviewTests(TestCase):
    def setUp(self):
        self.clerk = staff(Role.REGISTRATION_CLERK)
        self.clinician = staff(Role.CLINICIAN)
        self.visit = operations.check_in(actor=self.clerk)
        operations.set_priority(
            self.visit,
            priority=Visit.Priority.URGENT,
            actor=self.clinician,
            reason="Referred urgently by clinician",
        )

    def test_the_trail_can_be_filtered_to_accountability_actions(self):
        entries = audit.entries_for_review(accountability_only=True)

        self.assertTrue(entries)
        for entry in entries:
            self.assertIn(entry.action, audit.ACCOUNTABILITY_ACTIONS)

    def test_the_trail_can_be_filtered_by_token(self):
        other = operations.check_in(actor=self.clerk)

        entries = audit.entries_for_review(token=self.visit.token)

        self.assertTrue(entries)
        self.assertNotIn(
            other.token, [entry.visit_token for entry in entries]
        )


class ReportingTests(TestCase):
    def setUp(self):
        self.clerk = staff(Role.REGISTRATION_CLERK)
        self.clinician = staff(Role.CLINICIAN)

        for _ in range(6):
            visit = operations.check_in(actor=self.clerk)
            operations.complete_stage(visit, actor=self.clerk)

    def test_a_report_never_names_a_member_of_staff(self):
        report = reporting.management_report()
        rendered = str(report)

        self.assertNotIn(self.clerk.username, rendered)
        self.assertNotIn(self.clinician.username, rendered)

    def test_a_report_never_carries_a_patient_token(self):
        token = Visit.objects.first().token
        rendered = str(reporting.management_report())

        self.assertNotIn(token, rendered)

    def test_the_de_identification_check_rejects_an_identifying_field(self):
        """The rule is re-checked on every payload, not merely followed."""
        with self.assertRaises(reporting.DeIdentificationError):
            reporting.assert_de_identified({"nested": [{"username": "nurse1"}]})

        with self.assertRaises(reporting.DeIdentificationError):
            reporting.assert_de_identified({"rows": [{"visit_token": "T-001"}]})

    def test_small_counts_are_suppressed(self):
        """
        In a clinic where one person works a station, a count of one is a
        description of that person's day, not a statistic.
        """
        visit = operations.check_in(actor=self.clerk)
        operations.set_priority(
            visit,
            priority=Visit.Priority.EMERGENCY,
            actor=self.clinician,
            reason="Collapsed",
        )

        overrides = reporting.priority_overrides()

        self.assertTrue(overrides["by_role"][Role.CLINICIAN]["suppressed"])
        self.assertIsNone(overrides["by_role"][Role.CLINICIAN]["value"])

    def test_ordinary_counts_are_reported_exactly(self):
        throughput = reporting.throughput()

        self.assertEqual(throughput["visits_started"], 6)

    def test_service_times_are_reported_per_stage_never_per_person(self):
        times = reporting.service_times()

        self.assertIn("registration", times["stages"])
        self.assertNotIn("by_staff", times)
        self.assertNotIn(self.clerk.username, str(times))


class OversightEndpointTests(APITestCase):
    """Both endpoints refuse everybody while G4 is pending."""

    def setUp(self):
        self.audit_url = reverse("queueapp:audit-log")
        self.reports_url = reverse("queueapp:reports")

    def test_no_role_can_read_the_audit_log_yet(self):
        for role in Role.values:
            with self.subTest(role=role):
                self.client.force_authenticate(staff(role, username=f"a_{role}"))
                self.assertEqual(self.client.get(self.audit_url).status_code, 403)

    def test_no_role_can_read_the_reports_yet(self):
        for role in Role.values:
            with self.subTest(role=role):
                self.client.force_authenticate(staff(role, username=f"r_{role}"))
                self.assertEqual(self.client.get(self.reports_url).status_code, 403)

    def test_anonymous_callers_are_refused(self):
        self.assertEqual(self.client.get(self.audit_url).status_code, 401)
        self.assertEqual(self.client.get(self.reports_url).status_code, 401)
