"""
Phase 10 integration tests.

The other suites test parts. These drive whole journeys through the real API,
the way staff and patients actually use the system, and check that the layers
agree with each other — queue engine, permissions, patient channel, public
board and audit trail all telling the same story about the same visit.

Each test is one of the paths the spec's task analysis says the interface must
support.
"""

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import AuditLogEntry, PharmacyOutcome, Role, ServiceCounter, StaffUser, Visit

PASSWORD = "integration-test-only"


class JourneyTestCase(APITestCase):
    """Shared helpers: one member of staff per station, signed in as needed."""

    def setUp(self):
        self.clerk = self._staff("reception1", Role.REGISTRATION_CLERK)
        self.nurse = self._staff("nurse1", Role.NURSE_VITALS)
        self.clinician = self._staff("clinician1", Role.CLINICIAN)
        self.pharmacist = self._staff("pharmacy1", Role.PHARMACIST)

    def _staff(self, username, role):
        return StaffUser.objects.create_user(
            username=username, password=PASSWORD, role=role
        )

    def _as(self, user):
        self.client.force_authenticate(user)

    def _check_in(self) -> str:
        self._as(self.clerk)
        response = self.client.post(reverse("queueapp:check-in"), {})
        self.assertEqual(response.status_code, 201)
        return response.data["token"]

    def _post(self, name, token, body=None, expect=200):
        response = self.client.post(reverse(name, args=[token]), body or {})
        self.assertEqual(
            response.status_code, expect, msg=f"{name}: {response.data}"
        )
        return response

    def _patient_view(self, token):
        self.client.force_authenticate(None)
        response = self.client.get(reverse("queueapp:patient-status", args=[token]))
        self.assertEqual(response.status_code, 200)
        return response.data

    def _board(self):
        self.client.force_authenticate(None)
        return self.client.get(reverse("queueapp:public-display")).data["rows"]


class HappyPathTests(JourneyTestCase):
    """Registration → vitals → consultation → pharmacy → complete."""

    def test_a_whole_visit_from_check_in_to_medicine_issued(self):
        token = self._check_in()

        patient = self._patient_view(token)
        self.assertEqual(patient["stage_label"], "Registration")
        self.assertEqual(patient["next_stage_label"], "Vital signs")

        self._as(self.clerk)
        self._post("queueapp:complete-stage", token)
        self.assertEqual(self._patient_view(token)["current_stage"], "vitals")

        self._as(self.nurse)
        self._post("queueapp:complete-stage", token)
        self.assertEqual(self._patient_view(token)["current_stage"], "consultation")

        self._as(self.clinician)
        self._post("queueapp:complete-stage", token)
        self.assertEqual(self._patient_view(token)["current_stage"], "pharmacy")

        self._as(self.pharmacist)
        self._post(
            "queueapp:pharmacy-outcome",
            token,
            {"state": PharmacyOutcome.State.ISSUED},
        )

        patient = self._patient_view(token)
        self.assertEqual(patient["current_stage"], "complete")
        self.assertIsNone(patient["people_ahead"])

    def test_the_token_is_the_same_at_every_stage(self):
        """One visit identity, not per-stage tickets."""
        token = self._check_in()
        seen = [self._patient_view(token)["token"]]

        for actor in [self.clerk, self.nurse, self.clinician]:
            self._as(actor)
            self._post("queueapp:complete-stage", token)
            seen.append(self._patient_view(token)["token"])

        self.assertEqual(set(seen), {token})

    def test_every_stage_leaves_an_audit_entry(self):
        token = self._check_in()
        self._as(self.clerk)
        self._post("queueapp:complete-stage", token)

        actions = list(
            AuditLogEntry.objects.filter(visit_token=token).values_list(
                "action", flat=True
            )
        )
        self.assertIn("check_in", actions)
        self.assertIn("stage_complete", actions)


class EmergencyInterruptionTests(JourneyTestCase):
    """The exceptional path the spec cares most about."""

    def test_an_emergency_overtakes_everyone_and_reaches_a_clinician(self):
        early = [self._check_in() for _ in range(3)]

        # Move them all to consultation so there is a real queue to overtake.
        for token in early:
            self._as(self.clerk)
            self._post("queueapp:complete-stage", token)
            self._as(self.nurse)
            self._post("queueapp:complete-stage", token)

        latecomer = self._check_in()

        self._as(self.clinician)
        self._post(
            "queueapp:priority",
            latecomer,
            {"priority": "emergency", "reason": "Collapsed in waiting area"},
        )

        self._as(self.clinician)
        queue = self.client.get(
            reverse("queueapp:stage-queue", args=["consultation"])
        ).data

        self.assertEqual(queue["visits"][0]["token"], latecomer)
        self.assertEqual(queue["visits"][0]["priority"], "emergency")

    def test_the_patient_is_never_told_their_priority_category(self):
        token = self._check_in()
        self._as(self.clinician)
        self._post(
            "queueapp:priority",
            token,
            {"priority": "emergency", "reason": "Collapsed in waiting area"},
        )

        body = str(self._patient_view(token)).lower()
        self.assertNotIn("emergency", body)
        self.assertNotIn("priority", body)

    def test_the_override_is_attributable_afterwards(self):
        """The point of an audit trail: who decided, when, and why."""
        token = self._check_in()
        self._as(self.clinician)
        self._post(
            "queueapp:priority",
            token,
            {"priority": "emergency", "reason": "Collapsed in waiting area"},
        )

        entry = AuditLogEntry.objects.get(
            action="priority_change", visit_token=token
        )
        self.assertEqual(entry.actor_staff_user, self.clinician)
        self.assertEqual(entry.actor_role, Role.CLINICIAN)
        self.assertIn("Collapsed in waiting area", entry.non_sensitive_detail)

    def test_reception_cannot_declare_an_emergency(self):
        token = self._check_in()
        self._as(self.clerk)
        self._post(
            "queueapp:priority",
            token,
            {"priority": "emergency", "reason": "Looks unwell"},
            expect=403,
        )

        self.assertEqual(Visit.objects.get(token=token).priority, "routine")


class MissedTurnRecoveryTests(JourneyTestCase):
    """Called → away → missed → resumed, without losing your place."""

    def test_a_patient_who_steps_away_keeps_their_place(self):
        first = self._check_in()
        second = self._check_in()

        self._as(self.clerk)
        self._post("queueapp:presence", first, {"presence": "temporarily_away"})

        # The person behind is told there is nobody effectively ahead of them.
        self.assertEqual(self._patient_view(second)["people_ahead"], 0)

        self._as(self.clerk)
        self._post("queueapp:presence", first, {"presence": "resumed"})

        self._as(self.clerk)
        queue = self.client.get(
            reverse("queueapp:stage-queue", args=["registration"])
        ).data
        self.assertEqual(queue["visits"][0]["token"], first)

    def test_a_missed_turn_can_be_recovered(self):
        token = self._check_in()

        self._as(self.clerk)
        for presence in ["called", "missed_turn", "recalled", "resumed"]:
            self._post("queueapp:presence", token, {"presence": presence})

        patient = self._patient_view(token)
        self.assertEqual(patient["presence_status"], "resumed")
        self.assertIsNotNone(patient["people_ahead"])


class ReturnAfterTestsTests(JourneyTestCase):
    """Spec FR13, end to end."""

    def test_a_patient_returns_to_the_clinician_with_history_intact(self):
        token = self._check_in()
        self._as(self.clerk)
        self._post("queueapp:complete-stage", token)
        self._as(self.nurse)
        self._post("queueapp:complete-stage", token)

        self._as(self.clinician)
        self._post("queueapp:send-for-tests", token)

        patient = self._patient_view(token)
        self.assertEqual(patient["presence_status"], "temporarily_away")

        self._as(self.clinician)
        self._post("queueapp:return-after-tests", token)

        visit = Visit.objects.get(token=token)
        self.assertFalse(visit.awaiting_tests)
        self.assertEqual(visit.current_stage, "consultation")
        # Registration, vitals, the first consultation and the second.
        self.assertEqual(visit.stage_events.count(), 4)
        self.assertEqual(
            visit.stage_events.filter(stage="consultation").count(), 2
        )


class MedicineUnavailableTests(JourneyTestCase):
    def test_the_visit_stays_open_so_the_patient_can_be_directed_onward(self):
        token = self._check_in()
        for actor in [self.clerk, self.nurse, self.clinician]:
            self._as(actor)
            self._post("queueapp:complete-stage", token)

        self._as(self.pharmacist)
        self._post(
            "queueapp:pharmacy-outcome",
            token,
            {"state": PharmacyOutcome.State.UNAVAILABLE},
        )

        patient = self._patient_view(token)
        self.assertEqual(patient["current_stage"], "pharmacy")
        self.assertIsNone(Visit.objects.get(token=token).closed_at)

    def test_medicine_ready_then_issued_closes_the_visit(self):
        token = self._check_in()
        for actor in [self.clerk, self.nurse, self.clinician]:
            self._as(actor)
            self._post("queueapp:complete-stage", token)

        self._as(self.pharmacist)
        self._post(
            "queueapp:pharmacy-outcome",
            token,
            {"state": PharmacyOutcome.State.READY},
        )
        self._post(
            "queueapp:pharmacy-outcome",
            token,
            {"state": PharmacyOutcome.State.ISSUED},
        )

        self.assertEqual(self._patient_view(token)["current_stage"], "complete")


class PublicBoardIntegrationTests(JourneyTestCase):
    """FR8, checked against a real journey rather than a fixture."""

    def setUp(self):
        super().setUp()
        self.counter = ServiceCounter.objects.create(
            name="Consultation Room 2", stage="consultation"
        )

    def test_the_board_shows_a_called_patient_as_token_and_destination_only(self):
        token = self._check_in()
        self._as(self.clerk)
        self._post("queueapp:complete-stage", token)
        self._as(self.nurse)
        self._post("queueapp:complete-stage", token)

        visit = Visit.objects.get(token=token)
        visit.assigned_counter = self.counter
        visit.save()

        self._as(self.clinician)
        self._post(
            "queueapp:priority",
            token,
            {"priority": "urgent", "reason": "Referred urgently by clinician"},
        )
        self._post("queueapp:start-serving", token)

        rows = self._board()
        self.assertEqual(len(rows), 1)
        self.assertEqual(set(rows[0]), {"token", "destination"})
        self.assertEqual(rows[0]["destination"], "Consultation Room 2")
        self.assertNotIn("urgent", str(rows).lower())

    def test_patients_merely_waiting_are_not_published(self):
        self._check_in()
        self.assertEqual(self._board(), [])


class FallbackRehearsalTests(JourneyTestCase):
    """
    The offline fallback, rehearsed end to end (spec FR12).

    Simulates an outage: patients arrive and are recorded on paper, the system
    returns, reception enters the sheet, and the queue order must come out the
    way the waiting room experienced it.
    """

    def test_paper_arrivals_are_reconciled_into_the_right_order(self):
        now = timezone.now()

        # Three people arrived during the outage, in this order.
        paper = [
            ("Sheet 1, line 1", now - timedelta(minutes=90)),
            ("Sheet 1, line 2", now - timedelta(minutes=60)),
            ("Sheet 1, line 3", now - timedelta(minutes=30)),
        ]

        # Someone walks in after the system is back, before reconciliation.
        walk_in = self._check_in()

        self._as(self.clerk)
        reconciled = []
        for reference, arrived in paper:
            response = self.client.post(
                reverse("queueapp:reconcile-fallback"),
                {"arrived_at": arrived.isoformat(), "paper_reference": reference},
            )
            self.assertEqual(response.status_code, 201)
            reconciled.append(response.data["token"])

        queue = self.client.get(
            reverse("queueapp:stage-queue", args=["registration"])
        ).data

        # Everyone who waited through the outage comes before the walk-in, in
        # the order they actually arrived.
        self.assertEqual(
            [visit["token"] for visit in queue["visits"]],
            reconciled + [walk_in],
        )

    def test_each_reconciled_entry_is_marked_as_such(self):
        self._as(self.clerk)
        response = self.client.post(
            reverse("queueapp:reconcile-fallback"),
            {
                "arrived_at": (timezone.now() - timedelta(hours=1)).isoformat(),
                "paper_reference": "Sheet 2, line 4",
            },
        )

        entry = AuditLogEntry.objects.get(action="fallback_reconciliation")
        self.assertEqual(entry.visit_token, response.data["token"])
        self.assertIn("Sheet 2, line 4", entry.non_sensitive_detail)

    def test_a_reconciled_patient_continues_through_the_journey_normally(self):
        """Nothing about a paper-entered patient behaves differently afterwards."""
        self._as(self.clerk)
        token = self.client.post(
            reverse("queueapp:reconcile-fallback"),
            {"arrived_at": (timezone.now() - timedelta(hours=1)).isoformat()},
        ).data["token"]

        for actor in [self.clerk, self.nurse, self.clinician]:
            self._as(actor)
            self._post("queueapp:complete-stage", token)

        self._as(self.pharmacist)
        self._post(
            "queueapp:pharmacy-outcome",
            token,
            {"state": PharmacyOutcome.State.ISSUED},
        )

        self.assertEqual(self._patient_view(token)["current_stage"], "complete")


class RoleSeparationTests(JourneyTestCase):
    """Each station can do its own work and nobody else's."""

    def test_each_station_completes_only_its_own_stage(self):
        token = self._check_in()
        self._as(self.clerk)
        self._post("queueapp:complete-stage", token)  # now at vitals

        # Everyone except the nurse is refused.
        for actor in [self.clerk, self.clinician, self.pharmacist]:
            with self.subTest(actor=actor.role):
                self._as(actor)
                self._post("queueapp:complete-stage", token, expect=403)

        self._as(self.nurse)
        self._post("queueapp:complete-stage", token)

    def test_only_pharmacy_records_a_pharmacy_outcome(self):
        token = self._check_in()
        for actor in [self.clerk, self.nurse, self.clinician]:
            self._as(actor)
            self._post("queueapp:complete-stage", token)

        for actor in [self.clerk, self.nurse, self.clinician]:
            with self.subTest(actor=actor.role):
                self._as(actor)
                self._post(
                    "queueapp:pharmacy-outcome",
                    token,
                    {"state": PharmacyOutcome.State.ISSUED},
                    expect=403,
                )
