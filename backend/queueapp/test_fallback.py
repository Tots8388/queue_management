"""
Phase 9 tests: reconciling the paper fallback (spec FR12).

The behaviour that matters: a patient who waited through an outage must not be
punished for it when the system comes back.
"""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from django.test import TestCase

from .models import AuditLogEntry, Role, StaffUser, Visit
from .services import operations
from .services import queue as queue_service


def staff(role, username=None):
    return StaffUser.objects.create_user(
        username=username or f"fb_{role}", password="x", role=role
    )


class ReconciliationTests(TestCase):
    def setUp(self):
        self.clerk = staff(Role.REGISTRATION_CLERK)

    def test_the_recorded_arrival_time_is_used_not_the_clock(self):
        arrived = timezone.now() - timedelta(hours=2)

        visit = operations.reconcile_fallback_visit(
            actor=self.clerk, arrived_at=arrived
        )

        self.assertEqual(visit.check_in_time, arrived)
        self.assertEqual(visit.queue_order_time, arrived)

    def test_a_patient_who_waited_through_the_outage_keeps_their_place(self):
        """
        The point of the whole exercise: someone who arrived at 9am and waited
        must not go behind someone who walked in at 11am, just because the
        system came back at 11.
        """
        walked_in_late = operations.check_in(actor=self.clerk)

        waited_through_outage = operations.reconcile_fallback_visit(
            actor=self.clerk, arrived_at=timezone.now() - timedelta(hours=2)
        )

        tokens = [v.token for v in queue_service.stage_queue("registration")]
        self.assertEqual(
            tokens, [waited_through_outage.token, walked_in_late.token]
        )

    def test_the_entry_is_marked_in_the_audit_trail(self):
        """What was added after the fact must be distinguishable from live."""
        visit = operations.reconcile_fallback_visit(
            actor=self.clerk,
            arrived_at=timezone.now() - timedelta(minutes=45),
            paper_reference="Sheet 2, line 7",
        )

        entry = AuditLogEntry.objects.get(action="fallback_reconciliation")
        self.assertEqual(entry.visit_token, visit.token)
        self.assertIn("Sheet 2, line 7", entry.non_sensitive_detail)
        self.assertEqual(entry.actor_role, Role.REGISTRATION_CLERK)

    def test_a_patient_can_be_entered_at_the_stage_they_reached_on_paper(self):
        visit = operations.reconcile_fallback_visit(
            actor=self.clerk,
            arrived_at=timezone.now() - timedelta(hours=1),
            stage="consultation",
        )

        self.assertEqual(visit.current_stage, "consultation")
        self.assertTrue(visit.stage_events.filter(stage="consultation").exists())

    def test_a_future_arrival_time_is_refused(self):
        with self.assertRaises(ValidationError):
            operations.reconcile_fallback_visit(
                actor=self.clerk, arrived_at=timezone.now() + timedelta(hours=1)
            )

    def test_an_arrival_time_over_a_day_old_is_refused(self):
        """A mistyped date is likelier than a genuine day-old entry."""
        with self.assertRaises(ValidationError):
            operations.reconcile_fallback_visit(
                actor=self.clerk, arrived_at=timezone.now() - timedelta(days=2)
            )

    def test_a_patient_cannot_be_entered_as_already_complete(self):
        with self.assertRaises(ValidationError):
            operations.reconcile_fallback_visit(
                actor=self.clerk,
                arrived_at=timezone.now() - timedelta(hours=1),
                stage="complete",
            )

    def test_reconciled_visits_get_ordinary_system_tokens(self):
        """
        No separate token scheme to collide with the live sequence — staff hand
        the patient their digital token when the system returns.
        """
        first = operations.reconcile_fallback_visit(
            actor=self.clerk, arrived_at=timezone.now() - timedelta(hours=1)
        )
        second = operations.check_in(actor=self.clerk)

        self.assertNotEqual(first.token, second.token)
        self.assertEqual(Visit.objects.filter(token=first.token).count(), 1)


class ReconciliationEndpointTests(APITestCase):
    def setUp(self):
        self.url = reverse("queueapp:reconcile-fallback")

    def test_reception_can_reconcile(self):
        self.client.force_authenticate(staff(Role.REGISTRATION_CLERK))
        response = self.client.post(
            self.url,
            {
                "arrived_at": (timezone.now() - timedelta(hours=1)).isoformat(),
                "paper_reference": "Sheet 1, line 3",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["current_stage"], "registration")

    def test_other_roles_cannot_reconcile(self):
        """Running the fallback is reception's job, and only reception's."""
        for role in [Role.NURSE_VITALS, Role.CLINICIAN, Role.PHARMACIST]:
            with self.subTest(role=role):
                self.client.force_authenticate(staff(role, username=f"fbe_{role}"))
                response = self.client.post(
                    self.url,
                    {"arrived_at": (timezone.now() - timedelta(hours=1)).isoformat()},
                )
                self.assertEqual(response.status_code, 403)

    def test_a_missing_arrival_time_is_rejected(self):
        self.client.force_authenticate(
            staff(Role.REGISTRATION_CLERK, username="fb_clerk2")
        )
        self.assertEqual(self.client.post(self.url, {}).status_code, 400)

    def test_a_bad_arrival_time_gives_a_useful_message(self):
        self.client.force_authenticate(
            staff(Role.REGISTRATION_CLERK, username="fb_clerk3")
        )
        response = self.client.post(
            self.url,
            {"arrived_at": (timezone.now() - timedelta(days=3)).isoformat()},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("paper sheet", response.data["detail"])
