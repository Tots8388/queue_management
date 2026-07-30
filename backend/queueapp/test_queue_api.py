"""
Phase 3 tests: the queue endpoints, and who may reach them.
"""

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import PharmacyOutcome, Role, ServiceCounter, StaffUser, Visit
from .services import operations


def staff(role, username=None):
    return StaffUser.objects.create_user(
        username=username or f"api_{role}", password="x", role=role
    )


class CheckInEndpointTests(APITestCase):
    def setUp(self):
        self.url = reverse("queueapp:check-in")

    def test_reception_can_check_a_patient_in(self):
        self.client.force_authenticate(staff(Role.REGISTRATION_CLERK))
        response = self.client.post(self.url, {})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["token"], "T-001")
        self.assertEqual(response.data["current_stage"], "registration")

    def test_other_roles_cannot_check_a_patient_in(self):
        for role in [Role.NURSE_VITALS, Role.CLINICIAN, Role.PHARMACIST]:
            with self.subTest(role=role):
                self.client.force_authenticate(staff(role))
                self.assertEqual(self.client.post(self.url, {}).status_code, 403)

    def test_anonymous_callers_cannot_check_a_patient_in(self):
        self.assertEqual(self.client.post(self.url, {}).status_code, 401)

    def test_a_phone_number_requires_the_sms_preference(self):
        self.client.force_authenticate(staff(Role.REGISTRATION_CLERK))
        response = self.client.post(
            self.url, {"notification_preference": "screen", "phone_number": "+254700000111"}
        )
        self.assertEqual(response.status_code, 400)


class StageQueueEndpointTests(APITestCase):
    def setUp(self):
        self.clerk = staff(Role.REGISTRATION_CLERK)
        self.visit = operations.check_in(actor=self.clerk)
        operations.complete_stage(self.visit, actor=self.clerk)

    def test_staff_can_read_their_stage_queue(self):
        self.client.force_authenticate(staff(Role.NURSE_VITALS))
        response = self.client.get(reverse("queueapp:stage-queue", args=["vitals"]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["visits"]), 1)
        self.assertEqual(response.data["summary"]["waiting"], 1)

    def test_an_unknown_stage_is_rejected(self):
        self.client.force_authenticate(staff(Role.NURSE_VITALS))
        response = self.client.get(reverse("queueapp:stage-queue", args=["complete"]))
        self.assertEqual(response.status_code, 400)

    def test_oversight_roles_cannot_read_the_queue_while_g4_is_pending(self):
        for role in [Role.SUPERVISOR, Role.IT_SUPPORT]:
            with self.subTest(role=role):
                self.client.force_authenticate(staff(role))
                response = self.client.get(
                    reverse("queueapp:stage-queue", args=["vitals"])
                )
                self.assertEqual(response.status_code, 403)


class StageCompletionEndpointTests(APITestCase):
    def setUp(self):
        self.clerk = staff(Role.REGISTRATION_CLERK)
        self.visit = operations.check_in(actor=self.clerk)

    def _complete(self, user):
        self.client.force_authenticate(user)
        return self.client.post(
            reverse("queueapp:complete-stage", args=[self.visit.token]), {}
        )

    def test_the_nurse_completes_vitals(self):
        operations.complete_stage(self.visit, actor=self.clerk)
        response = self._complete(staff(Role.NURSE_VITALS))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["current_stage"], "consultation")

    def test_a_pharmacist_cannot_complete_a_consultation(self):
        """The capability required depends on the stage being completed."""
        self.visit.current_stage = "consultation"
        self.visit.save()

        self.assertEqual(self._complete(staff(Role.PHARMACIST)).status_code, 403)

    def test_a_nurse_cannot_complete_a_consultation(self):
        self.visit.current_stage = "consultation"
        self.visit.save()

        self.assertEqual(self._complete(staff(Role.NURSE_VITALS)).status_code, 403)


class PriorityEndpointTests(APITestCase):
    def setUp(self):
        self.visit = operations.check_in(actor=staff(Role.REGISTRATION_CLERK))
        self.url = reverse("queueapp:priority", args=[self.visit.token])

    def test_a_clinician_can_escalate_with_a_reason(self):
        self.client.force_authenticate(staff(Role.CLINICIAN))
        response = self.client.post(
            self.url, {"priority": "emergency", "reason": "Collapsed in waiting area"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["priority"], "emergency")

    def test_reception_and_pharmacy_are_refused(self):
        for role in [Role.REGISTRATION_CLERK, Role.PHARMACIST]:
            with self.subTest(role=role):
                self.client.force_authenticate(staff(role, username=f"p_{role}"))
                response = self.client.post(
                    self.url, {"priority": "urgent", "reason": "Looks unwell"}
                )
                self.assertEqual(response.status_code, 403)

    def test_a_reason_is_required(self):
        self.client.force_authenticate(staff(Role.CLINICIAN))
        response = self.client.post(self.url, {"priority": "urgent"})
        self.assertEqual(response.status_code, 400)


class PharmacyEndpointTests(APITestCase):
    def setUp(self):
        self.visit = operations.check_in(actor=staff(Role.REGISTRATION_CLERK))
        self.visit.current_stage = "pharmacy"
        self.visit.save()
        self.url = reverse("queueapp:pharmacy-outcome", args=[self.visit.token])

    def test_the_pharmacist_can_issue_medicine_and_close_the_visit(self):
        self.client.force_authenticate(staff(Role.PHARMACIST))
        response = self.client.post(
            self.url, {"state": PharmacyOutcome.State.ISSUED}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["current_stage"], "complete")

    def test_medicine_unavailable_leaves_the_visit_open(self):
        self.client.force_authenticate(staff(Role.PHARMACIST))
        response = self.client.post(
            self.url, {"state": PharmacyOutcome.State.UNAVAILABLE}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["current_stage"], "pharmacy")

    def test_a_clinician_cannot_dispense(self):
        self.client.force_authenticate(staff(Role.CLINICIAN))
        response = self.client.post(self.url, {"state": PharmacyOutcome.State.ISSUED})
        self.assertEqual(response.status_code, 403)


class PatientStatusEndpointTests(APITestCase):
    """Spec FR7 — and what a patient must never be shown."""

    def setUp(self):
        self.nurse = staff(Role.NURSE_VITALS)
        self.visit = operations.check_in(actor=staff(Role.REGISTRATION_CLERK))
        self.visit.current_stage = "vitals"
        self.visit.save()
        self.url = reverse("queueapp:patient-status", args=[self.visit.token])

    def test_a_patient_needs_no_account_to_see_their_own_status(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["token"], self.visit.token)

    def test_the_response_shows_stage_position_and_last_update(self):
        response = self.client.get(self.url)

        self.assertEqual(response.data["stage_label"], "Vital signs")
        self.assertEqual(response.data["next_stage_label"], "Consultation")
        self.assertEqual(response.data["people_ahead"], 0)
        self.assertIsNotNone(response.data["last_updated"])

    def test_the_wait_range_is_a_range_or_unavailable_never_a_countdown(self):
        wait = self.client.get(self.url).data["wait_range"]

        self.assertIn("available", wait)
        self.assertFalse(wait["available"])
        self.assertEqual(wait["text"], "Wait time unavailable")

    def test_the_patient_is_never_shown_their_priority_category(self):
        operations.set_priority(
            self.visit,
            priority=Visit.Priority.EMERGENCY,
            actor=self.nurse,
            reason="Clinical assessment at triage",
        )

        body = str(self.client.get(self.url).data).lower()

        self.assertNotIn("emergency", body)
        self.assertNotIn("priority", body)

    def test_an_unknown_token_is_not_found(self):
        response = self.client.get(reverse("queueapp:patient-status", args=["T-999"]))
        self.assertEqual(response.status_code, 404)


class PublicDisplayEndpointTests(APITestCase):
    """Spec FR8 — anonymous token and destination only."""

    def setUp(self):
        self.nurse = staff(Role.NURSE_VITALS)
        counter = ServiceCounter.objects.create(
            name="Consultation Room 2", stage="consultation"
        )
        self.visit = operations.check_in(actor=staff(Role.REGISTRATION_CLERK))
        self.visit.current_stage = "consultation"
        self.visit.assigned_counter = counter
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
        self.url = reverse("queueapp:public-display")

    def test_the_board_is_readable_without_an_account(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_a_row_carries_exactly_a_token_and_a_destination(self):
        row = self.client.get(self.url).data["rows"][0]

        self.assertEqual(set(row), {"token", "destination"})
        self.assertEqual(row["token"], self.visit.token)
        self.assertEqual(row["destination"], "Consultation Room 2")

    def test_the_board_discloses_no_priority_or_clinical_detail(self):
        body = str(self.client.get(self.url).data).lower()

        for forbidden in ["emergency", "urgent", "routine", "priority", "reason"]:
            with self.subTest(term=forbidden):
                self.assertNotIn(forbidden, body)


class VisitLookupTests(APITestCase):
    def test_yesterdays_token_is_not_reachable_today(self):
        """
        Tokens restart daily, so a lookup must be scoped to today or it would
        eventually return the wrong person's visit.
        """
        stale = Visit.check_in()
        stale.token_date = timezone.localdate() - timezone.timedelta(days=1)
        stale.save()

        response = self.client.get(
            reverse("queueapp:patient-status", args=[stale.token])
        )
        self.assertEqual(response.status_code, 404)
