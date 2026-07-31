"""
The audit trail (spec FR14, governance item G3).

Two layers, and the distinction between them is the whole point:

1. **Identifiable.** Accountability actions — an emergency or urgent override,
   a manual reorder of the queue — record the specific staff account, their
   role, and the non-sensitive reason they gave. These are the decisions
   someone may later have to answer for.

2. **Role-only.** Routine work — checking a patient in, completing a stage,
   marking medicine issued — records the role that did it and no individual.
   Attributing every routine keystroke to a named employee would turn a queue
   system into staff surveillance, which is not what the accountability
   requirement asks for.

Reporting reads neither directly: all analytics are aggregated and
de-identified in ``reporting.py``.

What never enters this table: a patient name, a diagnosis, a symptom, a
prescription, or a phone number. Entries hold an anonymous token and a
non-sensitive detail string, and ``_scrub`` is the last line of defence if a
caller ever tries otherwise.
"""

from __future__ import annotations

import logging
import re

from .models import AuditLogEntry

logger = logging.getLogger(__name__)

# Actions that identify the individual who performed them. Everything else is
# recorded against the role alone.
ACCOUNTABILITY_ACTIONS = frozenset(
    {
        "priority_change",
        "manual_reorder",
    }
)

# Actions worth keeping at all. An action not listed here is dropped rather
# than written under a name nobody recognises later.
RECORDED_ACTIONS = ACCOUNTABILITY_ACTIONS | frozenset(
    {
        "check_in",
        "stage_complete",
        "pharmacy_outcome",
        "sent_for_tests",
        "returned_after_tests",
        "fallback_reconciliation",
    }
)

MAX_DETAIL_LENGTH = 500

# A phone number reaching the audit log would be the one identifying value the
# system holds turning up in its longest-retained table.
_PHONE = re.compile(r"\+?\d[\d\s\-]{7,}\d")


def _scrub(detail: str) -> str:
    """
    Last line of defence on the detail string.

    Callers are expected to pass non-sensitive text; this makes sure a mistake
    upstream cannot quietly become a long-lived record of a phone number.
    """
    cleaned = _PHONE.sub("[redacted]", detail or "")
    if len(cleaned) > MAX_DETAIL_LENGTH:
        cleaned = cleaned[: MAX_DETAIL_LENGTH - 1] + "…"
    return cleaned


def record(fact) -> AuditLogEntry | None:
    """
    Write one accountability event.

    Never raises. An audit write failing must not roll back the clinical action
    it describes — a patient must not be left un-escalated because a log table
    was unavailable. A failure is logged loudly instead, because a silently
    missing audit entry is exactly what this system exists to prevent.
    """
    try:
        if fact.action not in RECORDED_ACTIONS:
            logger.warning("Unrecognised audit action %r — not recorded.", fact.action)
            return None

        actor = fact.actor if fact.action in ACCOUNTABILITY_ACTIONS else None

        return AuditLogEntry.objects.create(
            actor_staff_user=actor if getattr(actor, "pk", None) else None,
            actor_role=fact.actor_role or "",
            action=fact.action,
            visit_token=fact.visit_token or "",
            non_sensitive_detail=_scrub(fact.detail),
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "AUDIT WRITE FAILED for action=%r token=%r. The action itself "
            "stands; the trail does not have it.",
            getattr(fact, "action", "?"),
            getattr(fact, "visit_token", "?"),
        )
        return None


def entries_for_review(
    *,
    action: str | None = None,
    token: str | None = None,
    accountability_only: bool = False,
    limit: int = 200,
):
    """
    The trail, for authorised management review.

    Reached only by a role holding ``VIEW_AUDIT_LOG``. While governance item G4
    is pending, no role holds it, so this returns to nobody.
    """
    queryset = AuditLogEntry.objects.select_related("actor_staff_user")

    if action:
        queryset = queryset.filter(action=action)
    if token:
        queryset = queryset.filter(visit_token=token)
    if accountability_only:
        queryset = queryset.filter(action__in=ACCOUNTABILITY_ACTIONS)

    return queryset[:limit]
