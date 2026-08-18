"""
Phase 3 tests: the queue endpoints, and who may reach them.
"""

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import (
    AuditLogEntry,
    PharmacyOutcome,
    Role,
    ServiceCounter,
    StaffUser,
    Visit,
)
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
        self.assertRegex(response.data["token"], r"^[A-Z]\d{3}$")
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


def make_stale(visit, *, hours=None):
    """
    Age a visit past the staleness threshold.

    Writes ``last_updated`` with a queryset update rather than ``save()``,
    because the field is ``auto_now`` — saving it would stamp it with now and
    quietly undo the very thing the test is arranging.
    """
    hours = hours if hours is not None else settings.STALE_VISIT_HOURS + 1
    when = timezone.now() - timezone.timedelta(hours=hours)
    Visit.objects.filter(pk=visit.pk).update(last_updated=when)
    visit.refresh_from_db()
    return visit


class StaleVisitEndpointTests(APITestCase):
    """
    Reception closes visits nobody ever finished — the one gap the tracking
    board opens, since a patient now leaves it only when pharmacy is done.
    """

    def setUp(self):
        self.clerk = staff(Role.REGISTRATION_CLERK)
        self.list_url = reverse("queueapp:stale-visits")

    def _close_url(self, visit):
        return reverse("queueapp:close-abandoned", args=[visit.id])

    def test_a_visit_untouched_for_a_day_is_listed(self):
        stale = make_stale(Visit.check_in())

        self.client.force_authenticate(self.clerk)
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["stale_after_hours"], 24)
        self.assertEqual(
            [v["token"] for v in response.data["visits"]], [stale.token]
        )
        self.assertGreaterEqual(response.data["visits"][0]["idle_hours"], 24)

    def test_an_active_visit_is_not_listed(self):
        Visit.check_in()

        self.client.force_authenticate(self.clerk)
        response = self.client.get(self.list_url)

        self.assertEqual(response.data["visits"], [])

    def test_reception_can_close_one(self):
        stale = make_stale(Visit.check_in())

        self.client.force_authenticate(self.clerk)
        response = self.client.post(self._close_url(stale))

        self.assertEqual(response.status_code, 200)
        stale.refresh_from_db()
        self.assertIsNotNone(stale.closed_at)
        self.assertEqual(self.client.get(self.list_url).data["visits"], [])

    def test_the_stage_they_stopped_at_is_preserved(self):
        """
        Not rewritten to "complete": that would tell the reports somebody
        collected medication they never received.
        """
        stale = Visit.check_in()
        operations.complete_stage(stale, actor=self.clerk)
        make_stale(stale)

        self.client.force_authenticate(self.clerk)
        self.client.post(self._close_url(stale))

        stale.refresh_from_db()
        self.assertEqual(stale.current_stage, "vitals")

    def test_an_active_visit_cannot_be_closed(self):
        """
        The threshold is the whole safeguard. Without it this capability reads
        "reception may remove any patient from the queue".
        """
        active = Visit.check_in()

        self.client.force_authenticate(self.clerk)
        response = self.client.post(self._close_url(active))

        self.assertEqual(response.status_code, 400)
        active.refresh_from_db()
        self.assertIsNone(active.closed_at)

    def test_a_visit_just_short_of_the_threshold_cannot_be_closed(self):
        recent = make_stale(Visit.check_in(), hours=23)

        self.client.force_authenticate(self.clerk)

        self.assertEqual(self.client.post(self._close_url(recent)).status_code, 400)
        self.assertEqual(self.client.get(self.list_url).data["visits"], [])

    def test_closing_twice_is_refused(self):
        stale = make_stale(Visit.check_in())

        self.client.force_authenticate(self.clerk)
        self.client.post(self._close_url(stale))

        self.assertEqual(self.client.post(self._close_url(stale)).status_code, 400)

    def test_only_reception_may_see_or_close_them(self):
        stale = make_stale(Visit.check_in())

        for role in [Role.NURSE_VITALS, Role.CLINICIAN, Role.PHARMACIST]:
            with self.subTest(role=role):
                self.client.force_authenticate(staff(role, f"stale_{role}"))
                self.assertEqual(self.client.get(self.list_url).status_code, 403)
                self.assertEqual(
                    self.client.post(self._close_url(stale)).status_code, 403
                )

    def test_anonymous_callers_are_refused(self):
        stale = make_stale(Visit.check_in())

        self.assertEqual(self.client.get(self.list_url).status_code, 401)
        self.assertEqual(self.client.post(self._close_url(stale)).status_code, 401)

    def test_the_clerk_who_closed_it_is_named_in_the_audit_trail(self):
        """
        An accountability action, not routine work: if the judgement was wrong,
        somebody who was still waiting has been erased from every queue.
        """
        stale = make_stale(Visit.check_in())

        self.client.force_authenticate(self.clerk)
        self.client.post(self._close_url(stale))

        entry = AuditLogEntry.objects.get(action="closed_abandoned")
        self.assertEqual(entry.actor_staff_user, self.clerk)
        self.assertEqual(entry.visit_token, stale.token)
        self.assertIn("registration", entry.non_sensitive_detail)

    def test_a_visit_stranded_in_an_earlier_period_is_still_listed(self):
        """
        It is the visit that most needs closing — it has already fallen off the
        board and out of every stage queue, so this list is the only place it
        can still be seen.
        """
        stale = make_stale(Visit.check_in())
        Visit.objects.filter(pk=stale.pk).update(
            token_period=stale.token_period - timezone.timedelta(days=7)
        )

        self.client.force_authenticate(self.clerk)
        response = self.client.get(self.list_url)

        self.assertEqual(
            [v["token"] for v in response.data["visits"]], [stale.token]
        )

    def test_closing_addresses_the_visit_by_id_not_by_a_reusable_token(self):
        """
        The collision the id exists for: a stale visit's token reissued to
        somebody now sitting in the waiting room. Closing the old row must not
        touch the new patient — and token lookup would resolve to the new one.
        """
        stale = make_stale(Visit.check_in())
        Visit.objects.filter(pk=stale.pk).update(
            token_period=stale.token_period - timezone.timedelta(days=7)
        )
        stale.refresh_from_db()
        live = Visit.objects.create(token=stale.token, current_stage="vitals")

        self.client.force_authenticate(self.clerk)
        self.client.post(self._close_url(stale))

        stale.refresh_from_db()
        live.refresh_from_db()
        self.assertIsNotNone(stale.closed_at)
        self.assertIsNone(live.closed_at)

    def test_a_closed_abandoned_visit_leaves_the_public_board(self):
        stale = Visit.check_in()
        operations.complete_stage(stale, actor=self.clerk)
        make_stale(stale)

        self.client.force_authenticate(self.clerk)
        self.client.post(self._close_url(stale))

        self.client.force_authenticate(None)
        rows = self.client.get(reverse("queueapp:public-display")).data["rows"]
        self.assertNotIn(stale.token, [row["token"] for row in rows])


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
    """Spec FR8 — the tracking board: where everyone is, and nothing else."""

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

    def test_a_row_carries_only_where_the_patient_is(self):
        row = self.client.get(self.url).data["rows"][0]

        self.assertEqual(set(row), {"token", "stage", "destination", "called"})
        self.assertEqual(row["token"], self.visit.token)
        self.assertEqual(row["stage"], "consultation")
        self.assertEqual(row["destination"], "Consultation Room 2")
        self.assertIs(row["called"], True)

    def test_the_board_discloses_no_priority_or_clinical_detail(self):
        body = str(self.client.get(self.url).data).lower()

        for forbidden in ["emergency", "urgent", "routine", "priority", "reason"]:
            with self.subTest(term=forbidden):
                self.assertNotIn(forbidden, body)

    def test_the_board_carries_everyone_still_in_the_clinic(self):
        """
        Not a call-forward list. A patient at any stage is somewhere in the
        building and belongs on the board, so they can find their own token
        without asking at a desk.
        """
        others = {
            stage: operations.check_in(actor=staff(Role.REGISTRATION_CLERK, f"r_{stage}"))
            for stage in ["registration", "vitals", "pharmacy"]
        }
        for stage, visit in others.items():
            visit.current_stage = stage
            visit.save()

        rows = self.client.get(self.url).data["rows"]

        self.assertEqual(
            {row["token"] for row in rows},
            {self.visit.token} | {visit.token for visit in others.values()},
        )
        self.assertEqual(
            {row["stage"] for row in rows},
            {"registration", "vitals", "consultation", "pharmacy"},
        )

    def test_a_patient_leaves_the_board_only_once_pharmacy_is_done(self):
        self.visit.current_stage = "complete"
        self.visit.save()

        rows = self.client.get(self.url).data["rows"]

        self.assertEqual(rows, [])

    def test_the_board_is_in_arrival_order_not_service_order(self):
        """
        The queues themselves run emergencies first. Publishing that order
        would let the room work out who has been given a clinical priority, so
        the board sorts by arrival instead — self.visit is an emergency and is
        still listed first because it arrived first.
        """
        later = operations.check_in(actor=staff(Role.REGISTRATION_CLERK, "r_later"))

        tokens = [row["token"] for row in self.client.get(self.url).data["rows"]]

        self.assertEqual(tokens, [self.visit.token, later.token])


class VisitLookupTests(APITestCase):
    def test_a_token_from_a_past_period_is_not_reachable(self):
        """
        Tokens are reused once a period has passed, so a lookup that found any
        visit ever holding a token would eventually return the wrong person's.
        """
        stale = Visit.check_in()
        stale.token_period -= timezone.timedelta(days=365)
        stale.token_date = stale.token_period
        # Closed, because an open visit is deliberately reachable however old
        # it is — see the test below.
        stale.closed_at = timezone.now()
        stale.current_stage = "complete"
        stale.save()

        response = self.client.get(
            reverse("queueapp:patient-status", args=[stale.token])
        )
        self.assertEqual(response.status_code, 404)

    def test_an_open_visit_is_reachable_even_across_a_period_boundary(self):
        """
        A visit no longer ends when the day does — it ends when pharmacy is
        finished. Somebody still in the clinic when the period rolls over must
        not lose their own status page.
        """
        visit = Visit.check_in()
        visit.token_period -= timezone.timedelta(days=7)
        visit.save()

        response = self.client.get(
            reverse("queueapp:patient-status", args=[visit.token])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["token"], visit.token)

    def test_a_reused_token_resolves_to_the_visit_still_open(self):
        """
        The collision that matters: the same token issued again in a later
        period while an old closed visit still holds it. The live one wins.
        """
        old = Visit.check_in()
        old.token_period -= timezone.timedelta(days=7)
        old.closed_at = timezone.now()
        old.current_stage = "complete"
        old.save()

        current = Visit.objects.create(token=old.token, current_stage="vitals")

        response = self.client.get(
            reverse("queueapp:patient-status", args=[old.token])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["current_stage"], "vitals")
        self.assertEqual(response.data["token"], current.token)
