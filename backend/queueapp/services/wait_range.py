"""
How long the wait is likely to be — as a cautious range, never a countdown.

The spec is emphatic on this, and the literature it cites is the reason: exact
waiting-time estimates do not reliably improve satisfaction, and a precise
number that turns out wrong is worse than no number at all. So everything here
is built to under-promise:

* the estimate is a **range**, never a single figure;
* it is rounded outward to a **coarse band** ("about 10–20 minutes"), so it
  never looks more precise than it is;
* when there is too little data to form a reliable median it says
  **"wait time unavailable"** rather than guessing;
* it is always described to the patient as a guide, never a commitment.

Method (spec): position in stage × rolling median service time for that stage,
widened by a buffer and rounded to a band.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from django.conf import settings

from ..models import StageEvent, Visit
from . import queue as queue_service

UNAVAILABLE_TEXT = "Wait time unavailable"
# Shown when a patient's own priority means a time estimate would mislead.
# Worded so it does not disclose which priority category they were given.
SOON_TEXT = "You will be seen as soon as possible"


@dataclass(frozen=True)
class WaitRange:
    available: bool
    text: str = ""
    low_minutes: int | None = None
    high_minutes: int | None = None

    def as_dict(self) -> dict:
        return {
            "available": self.available,
            "text": self.text,
            "low_minutes": self.low_minutes,
            "high_minutes": self.high_minutes,
        }


def rolling_median_seconds(stage: str) -> float | None:
    """
    Median service time at a stage, over the most recent completed services.

    The median rather than the mean on purpose: one patient who took an hour
    would drag a mean upward for the rest of the day, and every waiting patient
    would then be quoted a worse figure than they will actually experience.

    Returns None when there are too few completed services to be reliable.
    """
    config = settings.WAIT_RANGE
    events = (
        StageEvent.objects.filter(stage=stage, completed_at__isnull=False)
        .order_by("-completed_at")[: config["SAMPLE_SIZE"]]
        .values_list("entered_at", "completed_at")
    )

    durations = [
        (completed - entered).total_seconds()
        for entered, completed in events
        # Guard against clock skew or a corrected record producing a negative
        # or absurd duration that would poison the median.
        if completed > entered and (completed - entered).total_seconds() < 6 * 3600
    ]

    if len(durations) < config["MIN_SAMPLES"]:
        return None

    return statistics.median(durations)


def _band_step(high_minutes: float) -> int:
    """
    How coarse the band should be.

    A longer wait deserves a blunter number: "about 10–20 minutes" is useful,
    "about 97–133 minutes" is false precision dressed up as care.
    """
    if high_minutes <= 30:
        return 5
    if high_minutes <= 60:
        return 10
    return 15


def _round_outward(low: float, high: float) -> tuple[int, int]:
    """Widen to a band, always outward — never round a wait down."""
    step = _band_step(high)
    low_band = max(0, int(low // step) * step)
    high_band = int(-(-high // step) * step)  # ceiling division

    # A band must actually be a range, and must not start at zero — "0–10
    # minutes" reads as a promise that someone may be seen immediately.
    if high_band <= low_band:
        high_band = low_band + step
    if low_band == 0:
        low_band = min(step, high_band - step) or step
        high_band = max(high_band, low_band + step)

    return low_band, high_band


def _describe(low: int, high: int) -> str:
    if high >= 120:
        return "More than 2 hours"
    return f"About {low}–{high} minutes"


def estimate_for(visit: Visit) -> WaitRange:
    """
    The waiting range shown to one patient (spec FR7).

    Degrades to "unavailable" rather than guessing whenever the data is thin,
    the patient is not in a queue, or a number would mislead.
    """
    if visit.closed_at or visit.current_stage == "complete":
        return WaitRange(available=False, text=UNAVAILABLE_TEXT)

    # A patient with a clinical priority is not waiting a routine amount of
    # time, and quoting them a routine range would be wrong in the one case
    # where being wrong matters most.
    if visit.priority != Visit.Priority.ROUTINE:
        return WaitRange(available=False, text=SOON_TEXT)

    ahead = queue_service.people_ahead(visit)
    if ahead is None:
        return WaitRange(available=False, text=UNAVAILABLE_TEXT)

    median = rolling_median_seconds(visit.current_stage)
    if median is None:
        return WaitRange(available=False, text=UNAVAILABLE_TEXT)

    # Position in stage, counting the patient themselves: someone who is next
    # still waits for the service in front of them to finish.
    position = ahead + 1
    base_minutes = (position * median) / 60

    buffer = settings.WAIT_RANGE["BUFFER_PERCENT"] / 100
    low, high = _round_outward(
        base_minutes * (1 - buffer), base_minutes * (1 + buffer)
    )

    return WaitRange(
        available=True,
        text=_describe(low, high),
        low_minutes=low,
        high_minutes=high,
    )
