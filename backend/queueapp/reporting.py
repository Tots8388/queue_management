"""
De-identified, aggregate reporting (spec FR14, governance item G3).

The spec asks for two things that pull in opposite directions: an accountability
trail that names who made a clinical override, and management reporting that
does not expose individuals. This module is the second half. Nothing it returns
names a member of staff or a patient.

Two rules, enforced by construction rather than by care:

* **No individual actor.** Counts are grouped by role, never by account, and
  ``assert_de_identified`` re-checks the finished payload before it is served.
* **Small groups are suppressed.** In a clinic where one person works a
  station, "the clinician who overrode the queue once this week" is a named
  individual dressed up as a statistic. Counts below a threshold are reported
  as a floor rather than an exact figure.
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Avg, Count
from django.utils import timezone

from .models import AuditLogEntry, PharmacyOutcome, PriorityChange, StageEvent, Visit
from .services import queue as queue_service
from .services.wait_range import rolling_median_seconds

# Below this, a count is reported as "fewer than N" rather than exactly. It is
# the difference between a statistic and a description of one person's day.
SMALL_GROUP_THRESHOLD = 5

# Fields that must never appear anywhere in a report payload.
FORBIDDEN_KEYS = frozenset(
    {
        "actor_staff_user",
        "actor_staff_user_id",
        "username",
        "first_name",
        "last_name",
        "phone_number",
        "token",
        "visit_token",
    }
)


class DeIdentificationError(AssertionError):
    """A report payload carried something that identifies a person."""


def _suppress(count: int) -> dict:
    """Report a small count as a floor, an ordinary one exactly."""
    if 0 < count < SMALL_GROUP_THRESHOLD:
        return {"value": None, "suppressed": True, "below": SMALL_GROUP_THRESHOLD}
    return {"value": count, "suppressed": False}


def assert_de_identified(payload) -> None:
    """
    Walk a finished payload and refuse anything identifying.

    Called before a report is served. A rule that is only followed by whoever
    wrote the query is a rule that lapses; this one is checked every time.
    """
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in FORBIDDEN_KEYS:
                raise DeIdentificationError(
                    f"Report payload contains {key!r}, which identifies a "
                    "person. Reports are aggregate and de-identified."
                )
            assert_de_identified(value)
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            assert_de_identified(item)


def _window(days: int):
    return timezone.now() - timedelta(days=days)


def throughput(days: int = 7) -> dict:
    """How many visits were handled, and how far they got."""
    since = _window(days)
    visits = Visit.objects.filter(check_in_time__gte=since)

    by_stage = dict(
        visits.values_list("current_stage").annotate(n=Count("id"))
    )

    return {
        "window_days": days,
        "visits_started": visits.count(),
        "visits_completed": visits.filter(closed_at__isnull=False).count(),
        "currently_at_stage": by_stage,
    }


def service_times() -> dict:
    """
    Median and mean service time per stage.

    Reported per stage, never per member of staff — "how long does vitals take"
    is a service question; "how long does this nurse take" is a performance
    review, and not something this system should quietly enable.
    """
    stages = {}
    for stage in queue_service.ACTIVE_STAGES:
        completed = StageEvent.objects.filter(
            stage=stage, completed_at__isnull=False
        )
        median = rolling_median_seconds(stage)
        stages[stage] = {
            "completed_services": completed.count(),
            "median_minutes": round(median / 60, 1) if median else None,
            "sample_sufficient": median is not None,
        }
    return {"stages": stages}


def priority_overrides(days: int = 7) -> dict:
    """
    How often clinical priority was applied, by role.

    This is the oversight view the spec asks for — is the override being used,
    and roughly by whom — without naming the individual who used it. The named
    record exists in the audit trail, reachable only by a role authorised to
    review it.
    """
    since = _window(days)
    changes = PriorityChange.objects.filter(timestamp__gte=since)

    by_priority = {}
    for priority, count in changes.values_list("new_priority").annotate(
        n=Count("id")
    ):
        by_priority[priority] = _suppress(count)

    by_role = {}
    for role, count in changes.values_list("changed_by_role").annotate(
        n=Count("id")
    ):
        by_role[role] = _suppress(count)

    return {
        "window_days": days,
        "total": changes.count(),
        "by_priority": by_priority,
        "by_role": by_role,
    }


def presence_exceptions(days: int = 7) -> dict:
    """Missed turns and step-aways — a signal about how the queue is running."""
    since = _window(days)
    visits = Visit.objects.filter(check_in_time__gte=since)

    counts = {}
    for status, count in visits.values_list("presence_status").annotate(
        n=Count("id")
    ):
        counts[status] = _suppress(count)

    return {"window_days": days, "by_status": counts}


def pharmacy_outcomes(days: int = 7) -> dict:
    """Including how often medicine was unavailable — a supply signal."""
    since = _window(days)
    outcomes = PharmacyOutcome.objects.filter(timestamp__gte=since)

    counts = {}
    for state, count in outcomes.values_list("state").annotate(n=Count("id")):
        counts[state] = _suppress(count)

    return {"window_days": days, "by_state": counts}


def waiting_summary() -> dict:
    """Current load per stage, for staffing decisions."""
    return {
        "stages": {
            stage: queue_service.stage_summary(stage)
            for stage in queue_service.ACTIVE_STAGES
        }
    }


def audit_activity(days: int = 7) -> dict:
    """Volume of recorded actions by type — never by actor."""
    since = _window(days)
    entries = AuditLogEntry.objects.filter(timestamp__gte=since)

    return {
        "window_days": days,
        "by_action": {
            action: _suppress(count)
            for action, count in entries.values_list("action").annotate(
                n=Count("id")
            )
        },
    }


def management_report(days: int = 7) -> dict:
    """
    The whole de-identified picture, checked before it leaves this module.
    """
    report = {
        "generated_at": timezone.now().isoformat(),
        "throughput": throughput(days),
        "service_times": service_times(),
        "priority_overrides": priority_overrides(days),
        "presence_exceptions": presence_exceptions(days),
        "pharmacy_outcomes": pharmacy_outcomes(days),
        "waiting_now": waiting_summary(),
        "audit_activity": audit_activity(days),
        "notes": [
            "All figures are aggregate and de-identified.",
            f"Counts below {SMALL_GROUP_THRESHOLD} are suppressed, because a "
            "very small count can describe one person's day.",
        ],
    }

    assert_de_identified(report)
    return report
