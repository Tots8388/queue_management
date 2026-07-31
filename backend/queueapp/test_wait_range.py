"""
Phase 6 tests: the waiting range.

The point of these is less "is the arithmetic right" than "does it ever
over-promise". A range that is too optimistic, or a number where there should
be none, is the failure mode the spec is guarding against.
"""

from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Role, StageEvent, StaffUser, Visit
from .services import operations
from .services import wait_range as wr

SETTINGS = {"SAMPLE_SIZE": 20, "MIN_SAMPLES": 5, "BUFFER_PERCENT": 30}


def completed_services(stage: str, minutes: list[int]) -> None:
    """
    Lay down finished services at a stage, so a median can be taken.

    ``minutes[0]`` is the most recently completed service. Entries are spaced
    far wider than any duration in them, so completion order is strictly the
    list order — otherwise a long service started earlier could finish later
    and silently reorder the sample the test is reasoning about.
    """
    now = timezone.now()
    spacing = timedelta(hours=3)

    for index, duration in enumerate(minutes):
        entered = now - timedelta(hours=1) - spacing * index
        StageEvent.objects.create(
            visit=Visit.check_in(),
            stage=stage,
            entered_at=entered,
            completed_at=entered + timedelta(minutes=duration),
            completed_by_role=Role.NURSE_VITALS,
        )


@override_settings(WAIT_RANGE=SETTINGS)
class RollingMedianTests(TestCase):
    def test_no_history_means_no_median(self):
        self.assertIsNone(wr.rolling_median_seconds("vitals"))

    def test_thin_history_means_no_median(self):
        """Four completed services is not enough to quote anybody a time."""
        completed_services("vitals", [10, 10, 10, 10])
        self.assertIsNone(wr.rolling_median_seconds("vitals"))

    def test_the_median_is_taken_once_there_is_enough_history(self):
        completed_services("vitals", [8, 10, 12, 14, 16])
        self.assertEqual(wr.rolling_median_seconds("vitals"), 12 * 60)

    def test_one_very_long_service_does_not_drag_the_estimate_up(self):
        """
        The median rather than the mean: one patient who took an hour must not
        worsen the figure quoted to everyone else for the rest of the day.
        """
        completed_services("vitals", [10, 10, 10, 10, 180])

        self.assertEqual(wr.rolling_median_seconds("vitals"), 10 * 60)

    def test_only_the_most_recent_services_count(self):
        """A quiet morning should not keep flattering a busy afternoon."""
        with override_settings(WAIT_RANGE={**SETTINGS, "SAMPLE_SIZE": 5}):
            # Most recent first: the clinic has slowed down to 30 minutes a
            # patient, after a quiet spell of 5.
            completed_services("vitals", [30, 30, 30, 30, 30, 5, 5, 5, 5, 5])
            median = wr.rolling_median_seconds("vitals")

        self.assertEqual(median, 30 * 60)

    def test_a_negative_duration_is_ignored(self):
        """Clock skew or a corrected record must not poison the median."""
        completed_services("vitals", [10, 10, 10, 10, 10])
        now = timezone.now()
        StageEvent.objects.create(
            visit=Visit.check_in(),
            stage="vitals",
            entered_at=now,
            completed_at=now - timedelta(minutes=30),
        )

        self.assertEqual(wr.rolling_median_seconds("vitals"), 10 * 60)

    def test_stages_are_measured_separately(self):
        completed_services("vitals", [5, 5, 5, 5, 5])
        completed_services("consultation", [20, 20, 20, 20, 20])

        self.assertEqual(wr.rolling_median_seconds("vitals"), 5 * 60)
        self.assertEqual(wr.rolling_median_seconds("consultation"), 20 * 60)


@override_settings(WAIT_RANGE=SETTINGS)
class BandingTests(TestCase):
    def test_a_band_is_always_a_range(self):
        for low, high in [(0, 0), (7, 7), (100, 100)]:
            with self.subTest(low=low, high=high):
                banded_low, banded_high = wr._round_outward(low, high)
                self.assertLess(banded_low, banded_high)

    def test_a_band_never_starts_at_zero(self):
        """"0–10 minutes" reads as a promise someone may be seen at once."""
        low, _ = wr._round_outward(1.0, 8.0)
        self.assertGreater(low, 0)

    def test_rounding_is_outward_so_a_wait_is_never_rounded_down(self):
        low, high = wr._round_outward(11.0, 19.0)

        self.assertLessEqual(low, 11)
        self.assertGreaterEqual(high, 19)

    def test_longer_waits_get_blunter_bands(self):
        """Precision that the estimate does not have should not be displayed."""
        self.assertEqual(wr._band_step(20), 5)
        self.assertEqual(wr._band_step(45), 10)
        self.assertEqual(wr._band_step(90), 15)

    def test_very_long_waits_are_described_rather_than_numbered(self):
        self.assertEqual(wr._describe(120, 150), "More than 2 hours")


@override_settings(WAIT_RANGE=SETTINGS)
class EstimateTests(TestCase):
    def setUp(self):
        self.nurse = StaffUser.objects.create_user(
            username="wr_nurse", password="x", role=Role.NURSE_VITALS
        )

    def _waiting_visit(self, stage="vitals", **fields) -> Visit:
        visit = Visit.check_in(**fields)
        visit.current_stage = stage
        visit.save()
        return visit

    def test_thin_data_degrades_to_unavailable(self):
        """Spec: degrade rather than guess."""
        visit = self._waiting_visit()
        estimate = wr.estimate_for(visit)

        self.assertFalse(estimate.available)
        self.assertEqual(estimate.text, wr.UNAVAILABLE_TEXT)
        self.assertIsNone(estimate.low_minutes)

    def test_a_range_is_produced_once_there_is_enough_history(self):
        completed_services("vitals", [10, 10, 10, 10, 10])
        visit = self._waiting_visit()

        estimate = wr.estimate_for(visit)

        self.assertTrue(estimate.available)
        # One position × 10 min, ±30% → 7–13, banded outward to 5–15.
        self.assertEqual((estimate.low_minutes, estimate.high_minutes), (5, 15))
        self.assertEqual(estimate.text, "About 5–15 minutes")

    def test_the_estimate_grows_with_the_number_of_people_ahead(self):
        completed_services("vitals", [10, 10, 10, 10, 10])
        base = timezone.now() - timedelta(minutes=40)

        first = self._waiting_visit(check_in_time=base)
        first.queue_order_time = base
        first.save()

        later = self._waiting_visit(check_in_time=base + timedelta(minutes=5))
        later.queue_order_time = later.check_in_time
        later.save()

        first_estimate = wr.estimate_for(first)
        later_estimate = wr.estimate_for(later)

        self.assertGreater(
            later_estimate.high_minutes, first_estimate.high_minutes
        )

    def test_the_output_is_never_a_single_number(self):
        completed_services("vitals", [10, 10, 10, 10, 10])
        estimate = wr.estimate_for(self._waiting_visit())

        self.assertNotEqual(estimate.low_minutes, estimate.high_minutes)
        self.assertIn("–", estimate.text)

    def test_a_completed_visit_has_no_estimate(self):
        visit = self._waiting_visit(stage="complete")
        visit.closed_at = timezone.now()
        visit.save()

        self.assertFalse(wr.estimate_for(visit).available)

    def test_a_prioritised_patient_is_not_quoted_a_routine_wait(self):
        """
        Quoting a routine range to someone who has been escalated would be
        wrong in the one case where being wrong matters most.
        """
        completed_services("vitals", [10, 10, 10, 10, 10])
        visit = self._waiting_visit()

        operations.set_priority(
            visit,
            priority=Visit.Priority.EMERGENCY,
            actor=self.nurse,
            reason="Clinical assessment at triage",
        )
        visit.refresh_from_db()

        estimate = wr.estimate_for(visit)
        self.assertFalse(estimate.available)
        self.assertEqual(estimate.text, wr.SOON_TEXT)

    def test_that_message_does_not_disclose_the_priority_category(self):
        """The patient is reassured without being told how they were triaged."""
        text = wr.SOON_TEXT.lower()

        for term in ["emergency", "urgent", "routine", "priority", "triage"]:
            with self.subTest(term=term):
                self.assertNotIn(term, text)


@override_settings(WAIT_RANGE=SETTINGS)
class PatientPayloadTests(TestCase):
    """The range as the patient view actually receives it."""

    def test_the_payload_carries_the_range_and_its_bounds(self):
        completed_services("vitals", [10, 10, 10, 10, 10])
        visit = Visit.check_in()
        visit.current_stage = "vitals"
        visit.save()

        response = self.client.get(f"/api/patient/{visit.token}/")
        wait = response.json()["wait_range"]

        self.assertTrue(wait["available"])
        self.assertEqual(wait["low_minutes"], 5)
        self.assertEqual(wait["high_minutes"], 15)

    def test_the_payload_says_unavailable_when_data_is_thin(self):
        visit = Visit.check_in()
        response = self.client.get(f"/api/patient/{visit.token}/")

        self.assertFalse(response.json()["wait_range"]["available"])
        self.assertEqual(
            response.json()["wait_range"]["text"], wr.UNAVAILABLE_TEXT
        )
