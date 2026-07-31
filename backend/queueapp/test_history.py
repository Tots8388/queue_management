"""
Tests for the visit-history view added after the Phase 10 heuristic evaluation.
"""

from django.urls import reverse
from rest_framework.test import APITestCase

from .models import PharmacyOutcome, Role, StaffUser, Visit
from .services import operations


def staff(role, username=None):
    return StaffUser.objects.create_user(
        username=username or f"hist_{role}", password="x", role=role
    )


class VisitHistoryTests(APITestCase):
    def setUp(self):
        self.clerk = staff(Role.REGISTRATION_CLERK)
        self.clinician = staff(Role.CLINICIAN)
        self.visit = operations.check_in(actor=self.clerk)
        operations.complete_stage(self.visit, actor=self.clerk)
        self.url = reverse("queueapp:visit-history", args=[self.visit.token])

    def test_history_shows_each_stage_with_its_timing(self):
        self.client.force_authenticate(self.clinician)
        data = self.client.get(self.url).data

        stages = {entry["stage"]: entry for entry in data["stages"]}
        self.assertIn("registration", stages)
        self.assertIsNotNone(stages["registration"]["completed_at"])
        self.assertEqual(
            stages["registration"]["completed_by_role"], Role.REGISTRATION_CLERK
        )
        self.assertIsNone(stages["vitals"]["completed_at"])

    def test_history_shows_priority_decisions_with_their_reasons(self):
        operations.set_priority(
            self.visit,
            priority=Visit.Priority.URGENT,
            actor=self.clinician,
            reason="Referred urgently by clinician",
        )

        self.client.force_authenticate(self.clinician)
        changes = self.client.get(self.url).data["priority_changes"]

        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["to"], "urgent")
        self.assertEqual(changes[0]["reason"], "Referred urgently by clinician")

    def test_a_second_consultation_appears_after_returning_from_tests(self):
        """Spec FR13 — the history is what makes the return safe."""
        self.visit.current_stage = "consultation"
        self.visit.save()
        operations.send_for_tests(self.visit, actor=self.clinician)
        operations.return_after_tests(self.visit, actor=self.clinician)

        self.client.force_authenticate(self.clinician)
        stages = self.client.get(self.url).data["stages"]

        consultations = [s for s in stages if s["stage"] == "consultation"]
        self.assertEqual(len(consultations), 1)

    def test_history_shows_pharmacy_outcomes(self):
        self.visit.current_stage = "pharmacy"
        self.visit.save()
        operations.record_pharmacy_outcome(
            self.visit,
            state=PharmacyOutcome.State.UNAVAILABLE,
            actor=staff(Role.PHARMACIST),
        )

        self.client.force_authenticate(self.clinician)
        pharmacy = self.client.get(self.url).data["pharmacy"]

        self.assertEqual(pharmacy[0]["state"], "medicine_unavailable")

    def test_history_carries_no_clinical_or_identifying_data(self):
        """The queue database holds none, and the view must not invent any."""
        self.client.force_authenticate(self.clinician)
        rendered = str(self.client.get(self.url).data).lower()

        for term in ["diagnosis", "symptom", "prescription", "phone", "name"]:
            with self.subTest(term=term):
                self.assertNotIn(term, rendered)

    def test_history_needs_a_staff_account(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_oversight_roles_cannot_read_it_while_g4_is_pending(self):
        for role in [Role.SUPERVISOR, Role.IT_SUPPORT]:
            with self.subTest(role=role):
                self.client.force_authenticate(staff(role, username=f"h_{role}"))
                self.assertEqual(self.client.get(self.url).status_code, 403)
