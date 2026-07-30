"""
Phase 3 tests: the queue policy.

The behaviours here are the ones that matter clinically — an emergency is never
behind a routine patient, a routine patient is never overtaken without a logged
reason, and history survives every path through the system.
"""

from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from .models import PharmacyOutcome, PriorityChange, Role, StaffUser, Visit
from .services import operations
from .services import queue as queue_service


def staff(role, username=None):
    return StaffUser.objects.create_user(
        username=username or f"user_{role}", password="x", role=role
    )


class RoutineOrderingTests(TestCase):
    """Spec FR2 — routine patients in check-in order, within their stage."""

    def setUp(self):
        self.clerk = staff(Role.REGISTRATION_CLERK)
        base = timezone.now() - timedelta(hours=1)

        self.visits = []
        for minutes in [0, 5, 10]:
            visit = Visit.check_in(check_in_time=base + timedelta(minutes=minutes))
            visit.queue_order_time = visit.check_in_time
            visit.current_stage = "vitals"
            visit.save()
            self.visits.append(visit)

    def test_patients_are_served_in_check_in_order(self):
        tokens = [v.token for v in queue_service.stage_queue("vitals")]
        self.assertEqual(tokens, [v.token for v in self.visits])

    def test_a_later_arrival_does_not_jump_ahead(self):
        latecomer = Visit.check_in(check_in_time=timezone.now())
        latecomer.queue_order_time = latecomer.check_in_time
        latecomer.current_stage = "vitals"
        latecomer.save()

        tokens = [v.token for v in queue_service.stage_queue("vitals")]
        self.assertEqual(tokens[-1], latecomer.token)

    def test_ordering_is_scoped_to_a_stage(self):
        """A patient waiting at pharmacy is not in the vitals queue."""
        self.visits[0].current_stage = "pharmacy"
        self.visits[0].save()

        vitals = [v.token for v in queue_service.stage_queue("vitals")]
        self.assertNotIn(self.visits[0].token, vitals)
        self.assertIn(
            self.visits[0].token,
            [v.token for v in queue_service.stage_queue("pharmacy")],
        )

    def test_positions_are_one_based(self):
        self.assertEqual(queue_service.position_in_stage(self.visits[0]), 1)
        self.assertEqual(queue_service.position_in_stage(self.visits[2]), 3)

    def test_people_ahead_counts_only_those_in_front(self):
        self.assertEqual(queue_service.people_ahead(self.visits[0]), 0)
        self.assertEqual(queue_service.people_ahead(self.visits[2]), 2)

    def test_a_completed_visit_has_no_position(self):
        visit = self.visits[0]
        visit.current_stage = "complete"
        visit.closed_at = timezone.now()
        visit.save()

        self.assertIsNone(queue_service.position_in_stage(visit))
        self.assertIsNone(queue_service.people_ahead(visit))


class PriorityOrderingTests(TestCase):
    """Spec FR4 — clinical urgency overrides time order."""

    def setUp(self):
        self.nurse = staff(Role.NURSE_VITALS)
        base = timezone.now() - timedelta(hours=1)

        self.early = self._waiting(base, "consultation")
        self.middle = self._waiting(base + timedelta(minutes=10), "consultation")
        self.late = self._waiting(base + timedelta(minutes=20), "consultation")

    def _waiting(self, when, stage):
        visit = Visit.check_in(check_in_time=when)
        visit.queue_order_time = when
        visit.current_stage = stage
        visit.save()
        return visit

    def test_an_emergency_goes_to_the_front_however_late_they_arrived(self):
        operations.set_priority(
            self.late,
            priority=Visit.Priority.EMERGENCY,
            actor=self.nurse,
            reason="Clinical assessment at triage",
        )

        tokens = [v.token for v in queue_service.stage_queue("consultation")]
        self.assertEqual(tokens[0], self.late.token)

    def test_urgent_goes_ahead_of_routine_but_behind_emergency(self):
        operations.set_priority(
            self.late,
            priority=Visit.Priority.URGENT,
            actor=self.nurse,
            reason="Referred urgently by clinician",
        )
        operations.set_priority(
            self.middle,
            priority=Visit.Priority.EMERGENCY,
            actor=self.nurse,
            reason="Clinical assessment at triage",
        )

        tokens = [v.token for v in queue_service.stage_queue("consultation")]
        self.assertEqual(
            tokens, [self.middle.token, self.late.token, self.early.token]
        )

    def test_two_emergencies_are_ordered_between_themselves_by_arrival(self):
        for visit in [self.late, self.early]:
            operations.set_priority(
                visit,
                priority=Visit.Priority.EMERGENCY,
                actor=self.nurse,
                reason="Clinical assessment at triage",
            )

        tokens = [v.token for v in queue_service.stage_queue("consultation")]
        self.assertEqual(tokens[:2], [self.early.token, self.late.token])


class PriorityRestrictionTests(TestCase):
    """Spec FR3, FR5."""

    def setUp(self):
        self.visit = Visit.check_in()

    def test_a_clinician_may_escalate(self):
        change = operations.escalate_to_emergency(
            self.visit, actor=staff(Role.CLINICIAN), reason="Collapsed in waiting area"
        )

        self.assertEqual(change.new_priority, Visit.Priority.EMERGENCY)
        self.assertEqual(change.changed_by_role, Role.CLINICIAN)
        self.assertEqual(change.non_sensitive_reason, "Collapsed in waiting area")

    def test_reception_may_not_assign_priority(self):
        with self.assertRaises(PermissionDenied):
            operations.set_priority(
                self.visit,
                priority=Visit.Priority.URGENT,
                actor=staff(Role.REGISTRATION_CLERK),
                reason="Looks unwell",
            )

        self.visit.refresh_from_db()
        self.assertEqual(self.visit.priority, Visit.Priority.ROUTINE)

    def test_pharmacy_supervisor_and_it_may_not_assign_priority(self):
        for role in [Role.PHARMACIST, Role.SUPERVISOR, Role.IT_SUPPORT]:
            with self.subTest(role=role):
                with self.assertRaises(PermissionDenied):
                    operations.set_priority(
                        self.visit,
                        priority=Visit.Priority.EMERGENCY,
                        actor=staff(role, username=f"u{role}"),
                        reason="Reason",
                    )

    def test_a_priority_change_requires_a_reason(self):
        clinician = staff(Role.CLINICIAN, username="c2")

        for reason in ["", "   "]:
            with self.subTest(reason=reason):
                with self.assertRaises(ValidationError):
                    operations.set_priority(
                        self.visit,
                        priority=Visit.Priority.URGENT,
                        actor=clinician,
                        reason=reason,
                    )

    def test_every_change_is_recorded_with_role_time_and_reason(self):
        nurse = staff(Role.NURSE_VITALS)
        operations.set_priority(
            self.visit, priority=Visit.Priority.URGENT, actor=nurse, reason="Escalated at triage"
        )
        operations.set_priority(
            self.visit,
            priority=Visit.Priority.EMERGENCY,
            actor=nurse,
            reason="Deteriorated",
        )

        changes = list(PriorityChange.objects.filter(visit=self.visit).order_by("timestamp"))
        self.assertEqual(len(changes), 2)
        self.assertEqual(changes[0].previous_priority, Visit.Priority.ROUTINE)
        self.assertEqual(changes[1].previous_priority, Visit.Priority.URGENT)
        self.assertTrue(all(c.timestamp and c.non_sensitive_reason for c in changes))


class EmergencyRoutingTests(TestCase):
    """Spec FR4 — an emergency is routed to clinical care immediately."""

    def setUp(self):
        self.clinician = staff(Role.CLINICIAN)

    def test_an_emergency_at_registration_is_moved_to_consultation(self):
        visit = Visit.check_in()
        self.assertEqual(visit.current_stage, "registration")

        operations.escalate_to_emergency(
            visit, actor=self.clinician, reason="Collapsed at reception"
        )
        visit.refresh_from_db()

        self.assertEqual(visit.current_stage, "consultation")
        self.assertEqual(visit.stage_status, Visit.StageStatus.WAITING)

    def test_an_emergency_already_past_consultation_is_not_moved_backwards(self):
        visit = Visit.check_in()
        visit.current_stage = "pharmacy"
        visit.save()

        operations.escalate_to_emergency(
            visit, actor=self.clinician, reason="Deteriorated at pharmacy"
        )
        visit.refresh_from_db()

        self.assertEqual(visit.current_stage, "pharmacy")

    def test_an_emergency_who_had_stepped_away_is_back_in_the_running_order(self):
        visit = Visit.check_in()
        visit.current_stage = "consultation"
        visit.presence_status = Visit.Presence.MISSED_TURN
        visit.save()

        operations.escalate_to_emergency(
            visit, actor=self.clinician, reason="Returned in distress"
        )
        visit.refresh_from_db()

        self.assertEqual(visit.presence_status, Visit.Presence.RESUMED)

    def test_the_escalation_stands_even_if_routing_fails(self):
        """
        Spec: never block an emergency action on system state. If routing
        raises, the recorded priority must still be emergency.
        """
        visit = Visit.check_in()

        def explode(*args, **kwargs):
            raise RuntimeError("stage routing blew up")

        original = operations._close_open_event
        operations._close_open_event = explode
        try:
            operations.escalate_to_emergency(
                visit, actor=self.clinician, reason="Collapsed"
            )
        finally:
            operations._close_open_event = original

        visit.refresh_from_db()
        self.assertEqual(visit.priority, Visit.Priority.EMERGENCY)
        self.assertTrue(
            PriorityChange.objects.filter(
                visit=visit, new_priority=Visit.Priority.EMERGENCY
            ).exists()
        )


class StageTransitionTests(TestCase):
    """Spec FR6, FR10."""

    def setUp(self):
        self.clerk = staff(Role.REGISTRATION_CLERK)
        self.nurse = staff(Role.NURSE_VITALS)
        self.clinician = staff(Role.CLINICIAN)
        self.pharmacist = staff(Role.PHARMACIST)

    def test_a_visit_moves_through_the_whole_journey(self):
        visit = operations.check_in(actor=self.clerk)
        self.assertEqual(visit.current_stage, "registration")

        for actor, expected in [
            (self.clerk, "vitals"),
            (self.nurse, "consultation"),
            (self.clinician, "pharmacy"),
        ]:
            visit = operations.complete_stage(visit, actor=actor)
            self.assertEqual(visit.current_stage, expected)

        operations.record_pharmacy_outcome(
            visit, state=PharmacyOutcome.State.ISSUED, actor=self.pharmacist
        )
        visit.refresh_from_db()

        self.assertEqual(visit.current_stage, "complete")
        self.assertIsNotNone(visit.closed_at)

    def test_each_completed_stage_leaves_a_closed_event(self):
        visit = operations.check_in(actor=self.clerk)
        operations.complete_stage(visit, actor=self.clerk)

        event = visit.stage_events.get(stage="registration")
        self.assertIsNotNone(event.completed_at)
        self.assertEqual(event.completed_by_role, Role.REGISTRATION_CLERK)

    def test_a_closed_visit_cannot_be_advanced(self):
        visit = operations.check_in(actor=self.clerk)
        visit.closed_at = timezone.now()
        visit.save()

        with self.assertRaises(ValidationError):
            operations.complete_stage(visit, actor=self.clerk)

    def test_medicine_unavailable_keeps_the_visit_open(self):
        """The patient still needs somewhere to go, so the visit stays open."""
        visit = operations.check_in(actor=self.clerk)
        visit.current_stage = "pharmacy"
        visit.save()

        operations.record_pharmacy_outcome(
            visit, state=PharmacyOutcome.State.UNAVAILABLE, actor=self.pharmacist
        )
        visit.refresh_from_db()

        self.assertIsNone(visit.closed_at)
        self.assertEqual(visit.current_stage, "pharmacy")


class ReturnAfterTestsTests(TestCase):
    """Spec FR13 — no prior stage history is lost."""

    def setUp(self):
        self.clinician = staff(Role.CLINICIAN)
        self.visit = operations.check_in(actor=staff(Role.REGISTRATION_CLERK))
        self.visit.current_stage = "consultation"
        self.visit.save()

    def test_sending_for_tests_takes_the_patient_out_of_the_running_order(self):
        operations.send_for_tests(self.visit, actor=self.clinician)
        self.visit.refresh_from_db()

        self.assertTrue(self.visit.awaiting_tests)
        self.assertEqual(self.visit.presence_status, Visit.Presence.TEMPORARILY_AWAY)

    def test_returning_opens_a_new_consultation_without_erasing_the_first(self):
        first = self.visit.stage_events.create(
            stage="consultation",
            completed_at=timezone.now(),
            completed_by_role=Role.CLINICIAN,
        )
        operations.send_for_tests(self.visit, actor=self.clinician)
        operations.return_after_tests(self.visit, actor=self.clinician)
        self.visit.refresh_from_db()

        events = list(self.visit.stage_events.filter(stage="consultation"))
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].pk, first.pk)
        self.assertIsNotNone(events[0].completed_at)
        self.assertIsNone(events[1].completed_at)
        self.assertFalse(self.visit.awaiting_tests)

    def test_a_patient_not_sent_for_tests_cannot_return_from_them(self):
        with self.assertRaises(ValidationError):
            operations.return_after_tests(self.visit, actor=self.clinician)


class PresenceTests(TestCase):
    """Spec FR9 — call, recall, away, missed, resumed."""

    def setUp(self):
        self.nurse = staff(Role.NURSE_VITALS)
        base = timezone.now() - timedelta(minutes=30)
        self.first = self._waiting(base)
        self.second = self._waiting(base + timedelta(minutes=5))

    def _waiting(self, when):
        visit = Visit.check_in(check_in_time=when)
        visit.queue_order_time = when
        visit.current_stage = "vitals"
        visit.save()
        return visit

    def test_every_specified_status_can_be_set(self):
        for presence in [
            Visit.Presence.CALLED,
            Visit.Presence.RECALLED,
            Visit.Presence.TEMPORARILY_AWAY,
            Visit.Presence.MISSED_TURN,
            Visit.Presence.RESUMED,
        ]:
            with self.subTest(presence=presence):
                visit = operations.set_presence(
                    self.first, presence=presence, actor=self.nurse
                )
                self.assertEqual(visit.presence_status, presence)

    def test_a_patient_who_stepped_away_is_not_counted_as_ahead_of_others(self):
        """Telling someone people are ahead who are not in the building is worse
        than useless."""
        self.assertEqual(queue_service.people_ahead(self.second), 1)

        operations.set_presence(
            self.first, presence=Visit.Presence.TEMPORARILY_AWAY, actor=self.nurse
        )
        self.assertEqual(queue_service.people_ahead(self.second), 0)

    def test_a_missed_turn_keeps_the_patient_in_the_queue(self):
        operations.set_presence(
            self.first, presence=Visit.Presence.MISSED_TURN, actor=self.nurse
        )

        tokens = [v.token for v in queue_service.stage_queue("vitals")]
        self.assertIn(self.first.token, tokens)

    def test_resuming_recovers_the_patients_place(self):
        """Spec: a patient can recover their place via the recall route."""
        operations.set_presence(
            self.first, presence=Visit.Presence.MISSED_TURN, actor=self.nurse
        )
        operations.set_presence(
            self.first, presence=Visit.Presence.RESUMED, actor=self.nurse
        )

        tokens = [
            v.token
            for v in queue_service.stage_queue("vitals", include_stepped_away=False)
        ]
        self.assertEqual(tokens[0], self.first.token)

    def test_next_visit_skips_those_who_have_stepped_away(self):
        operations.set_presence(
            self.first, presence=Visit.Presence.TEMPORARILY_AWAY, actor=self.nurse
        )
        self.assertEqual(queue_service.next_visit("vitals").token, self.second.token)


class ManualReorderTests(TestCase):
    def setUp(self):
        self.nurse = staff(Role.NURSE_VITALS)
        base = timezone.now() - timedelta(minutes=30)
        self.first = self._waiting(base)
        self.second = self._waiting(base + timedelta(minutes=10))

    def _waiting(self, when):
        visit = Visit.check_in(check_in_time=when)
        visit.queue_order_time = when
        visit.current_stage = "vitals"
        visit.save()
        return visit

    def test_a_reorder_changes_the_running_order(self):
        operations.manual_reorder(
            self.second,
            actor=self.nurse,
            reason="Clinician requested",
            ahead_of=self.first,
        )

        tokens = [v.token for v in queue_service.stage_queue("vitals")]
        self.assertEqual(tokens, [self.second.token, self.first.token])

    def test_a_reorder_never_rewrites_the_recorded_check_in_time(self):
        """
        The check-in time is the record of when the patient arrived. A reorder
        is a decision someone made, not a claim about arrival.
        """
        original = self.second.check_in_time

        operations.manual_reorder(
            self.second,
            actor=self.nurse,
            reason="Clinician requested",
            ahead_of=self.first,
        )
        self.second.refresh_from_db()

        self.assertEqual(self.second.check_in_time, original)

    def test_a_reorder_requires_a_reason(self):
        for reason in ["", "  "]:
            with self.subTest(reason=reason):
                with self.assertRaises(ValidationError):
                    operations.manual_reorder(
                        self.second, actor=self.nurse, reason=reason, ahead_of=self.first
                    )

    def test_patients_at_different_stages_cannot_be_reordered_against_each_other(self):
        self.second.current_stage = "pharmacy"
        self.second.save()

        with self.assertRaises(ValidationError):
            operations.manual_reorder(
                self.second,
                actor=self.nurse,
                reason="Clinician requested",
                ahead_of=self.first,
            )


class PublicDisplayTests(TestCase):
    """Spec FR8 — anonymous token and destination, nothing else."""

    def setUp(self):
        self.nurse = staff(Role.NURSE_VITALS)
        self.visit = Visit.check_in()
        self.visit.current_stage = "consultation"
        self.visit.save()
        operations.set_priority(
            self.visit,
            priority=Visit.Priority.EMERGENCY,
            actor=self.nurse,
            reason="Clinical assessment at triage",
        )
        operations.set_presence(
            self.visit, presence=Visit.Presence.CALLED, actor=self.nurse
        )

    def test_a_row_carries_only_a_token_and_a_destination(self):
        rows = queue_service.public_display_rows()

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            set(vars(rows[0])), {"token", "destination"}
        )

    def test_the_board_never_discloses_the_priority_category(self):
        rendered = str(queue_service.public_display_rows())

        self.assertNotIn("emergency", rendered.lower())
        self.assertNotIn("urgent", rendered.lower())

    def test_patients_not_yet_called_are_not_listed(self):
        waiting = Visit.check_in()
        waiting.current_stage = "consultation"
        waiting.save()

        tokens = [row.token for row in queue_service.public_display_rows()]
        self.assertNotIn(waiting.token, tokens)
