"""
Changing the queue.

Every mutation the system performs lives here, so the queue policy is enforced
in one place rather than re-implemented per view or per channel. Views validate
input and check permissions; they do not decide queue behaviour.

Two rules run through the whole module:

* **The system never makes a clinical decision.** It records the one a
  clinician made, with role, timestamp and a non-sensitive reason.
* **Emergency actions never fail on system state.** ``escalate_to_emergency``
  is written so that no ordinary condition — wrong stage, patient stepped away,
  visit already closed — can refuse it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from ..contracts import contracts, roles_that_may_assign_priority
from ..models import (
    NotificationContact,
    PharmacyOutcome,
    PriorityChange,
    StageEvent,
    Visit,
)

logger = logging.getLogger(__name__)

STAGE_ORDER = [stage["key"] for stage in contracts()["stages"]]

# Where an emergency goes. A patient needing immediate clinical attention is
# sent to a clinician rather than being walked through the routine path first.
EMERGENCY_STAGE = "consultation"


class QueueError(ValidationError):
    """A queue operation that cannot be performed as asked."""


# ---------------------------------------------------------------------------
# Audit seam
# ---------------------------------------------------------------------------
# FR14 requires an audit entry for every priority change, manual reorder and key
# completion. The write path for that trail is ``queueapp/audit.py``, which
# governance item G3 blocks — it decides what identifiable staff data is
# retained. Until G3 is approved that module does not exist, and the facts below
# are collected and dropped rather than written.
#
# This is loud on purpose: the warning fires once at import so nobody can
# believe an audit trail is being kept when it is not.


@dataclass(frozen=True)
class AuditFact:
    """One accountability event, ready for the trail once G3 is approved."""

    action: str
    actor_role: str
    visit_token: str
    detail: str = ""
    actor = None
    extra: dict = field(default_factory=dict)


try:  # pragma: no cover — the real recorder arrives with G3 in Phase 8
    from ..audit import record as record_audit
except ImportError:
    logger.warning(
        "Audit trail is NOT being written: queueapp/audit.py does not exist "
        "because governance item G3 is still PENDING. Queue operations will "
        "proceed and accountability events will be discarded. See "
        "docs/governance/SIGNOFF.md."
    )

    def record_audit(fact: AuditFact) -> None:  # noqa: D103
        return None


# ---------------------------------------------------------------------------
# Check-in
# ---------------------------------------------------------------------------


@transaction.atomic
def check_in(
    *,
    actor,
    notification_preference: str = "screen",
    phone_number: str | None = None,
    counter=None,
) -> Visit:
    """
    Register a patient and issue an anonymous token (spec FR1).

    Records the check-in time, which is what routine ordering within every
    later stage is based on.
    """
    now = timezone.now()
    visit = Visit.check_in(
        check_in_time=now,
        notification_preference=notification_preference,
        assigned_counter=counter,
    )

    StageEvent.objects.create(visit=visit, stage="registration", entered_at=now)

    if phone_number:
        if notification_preference != "sms":
            raise QueueError(
                "A phone number was supplied but this visit is not set to "
                "receive SMS updates."
            )
        NotificationContact.objects.create(visit=visit, phone_number=phone_number)

    record_audit(
        AuditFact(
            action="check_in",
            actor_role=getattr(actor, "role", ""),
            visit_token=visit.token,
            detail="Visit registered and token issued",
        )
    )
    return visit


# ---------------------------------------------------------------------------
# Stage transitions
# ---------------------------------------------------------------------------


def _next_stage(stage: str) -> str | None:
    index = STAGE_ORDER.index(stage)
    if index >= len(STAGE_ORDER) - 1:
        return None
    return STAGE_ORDER[index + 1]


def _close_open_event(visit: Visit, role: str) -> None:
    """Finish the visit's open event for its current stage, if there is one."""
    event = (
        visit.stage_events.filter(stage=visit.current_stage, completed_at__isnull=True)
        .order_by("-entered_at")
        .first()
    )
    if event:
        event.completed_at = timezone.now()
        event.completed_by_role = role
        event.save(update_fields=["completed_at", "completed_by_role"])


@transaction.atomic
def complete_stage(visit: Visit, *, actor, to_stage: str | None = None) -> Visit:
    """
    Mark the current stage done and move the patient on (spec FR6, FR10).

    History is append-only: the finished stage keeps its event, and the new
    stage gets a fresh one. That is what makes return-after-tests safe.
    """
    if visit.closed_at:
        raise QueueError(f"Visit {visit.token} is already closed.")

    role = getattr(actor, "role", "")
    destination = to_stage or _next_stage(visit.current_stage)
    if destination is None:
        raise QueueError(f"Visit {visit.token} has no stage after its current one.")
    if destination not in STAGE_ORDER:
        raise QueueError(f"{destination!r} is not a known stage.")

    completed_stage = visit.current_stage
    _close_open_event(visit, role)

    visit.current_stage = destination
    visit.presence_status = Visit.Presence.WAITING

    if destination == "complete":
        visit.stage_status = Visit.StageStatus.COMPLETE
        visit.closed_at = timezone.now()
        visit.assigned_counter = None
    else:
        visit.stage_status = Visit.StageStatus.WAITING
        StageEvent.objects.create(visit=visit, stage=destination)

    visit.save()

    record_audit(
        AuditFact(
            action="stage_complete",
            actor_role=role,
            visit_token=visit.token,
            detail=f"{completed_stage} complete, moved to {destination}",
        )
    )
    return visit


@transaction.atomic
def start_serving(visit: Visit, *, actor, counter=None) -> Visit:
    """A member of staff begins serving this patient at their current stage."""
    if visit.closed_at:
        raise QueueError(f"Visit {visit.token} is already closed.")

    visit.stage_status = Visit.StageStatus.IN_PROGRESS
    visit.presence_status = Visit.Presence.CALLED
    if counter is not None:
        visit.assigned_counter = counter
    visit.save(
        update_fields=["stage_status", "presence_status", "assigned_counter", "last_updated"]
    )
    return visit


@transaction.atomic
def send_for_tests(visit: Visit, *, actor) -> Visit:
    """
    The clinician sends the patient for laboratory tests (spec FR13).

    The visit stays at consultation and keeps its history; it simply leaves the
    running order until the patient comes back.
    """
    if visit.current_stage != "consultation":
        raise QueueError("Only a patient at consultation can be sent for tests.")

    visit.awaiting_tests = True
    visit.presence_status = Visit.Presence.TEMPORARILY_AWAY
    visit.stage_status = Visit.StageStatus.WAITING
    visit.save()

    record_audit(
        AuditFact(
            action="sent_for_tests",
            actor_role=getattr(actor, "role", ""),
            visit_token=visit.token,
            detail="Sent for laboratory tests",
        )
    )
    return visit


@transaction.atomic
def return_after_tests(visit: Visit, *, actor) -> Visit:
    """
    The patient returns to the clinician after tests (spec FR13).

    A new consultation event is opened; the earlier one still stands, so no
    prior stage history is lost.
    """
    if not visit.awaiting_tests:
        raise QueueError(f"Visit {visit.token} was not sent for tests.")

    visit.awaiting_tests = False
    visit.current_stage = "consultation"
    visit.stage_status = Visit.StageStatus.WAITING
    visit.presence_status = Visit.Presence.RESUMED
    visit.save()

    StageEvent.objects.create(visit=visit, stage="consultation")

    record_audit(
        AuditFact(
            action="returned_after_tests",
            actor_role=getattr(actor, "role", ""),
            visit_token=visit.token,
            detail="Returned to clinician after tests",
        )
    )
    return visit


@transaction.atomic
def record_pharmacy_outcome(visit: Visit, *, state: str, actor) -> PharmacyOutcome:
    """
    Medicine ready, issued or unavailable (spec FR10).

    Issuing closes the visit. "Unavailable" does not: the patient still needs
    somewhere to go, so the visit stays open for staff to handle.
    """
    if state not in PharmacyOutcome.State.values:
        raise QueueError(f"{state!r} is not a pharmacy outcome.")

    role = getattr(actor, "role", "")
    outcome = PharmacyOutcome.objects.create(visit=visit, state=state, by_role=role)

    if state == PharmacyOutcome.State.ISSUED:
        complete_stage(visit, actor=actor, to_stage="complete")
    else:
        visit.save(update_fields=["last_updated"])

    record_audit(
        AuditFact(
            action="pharmacy_outcome",
            actor_role=role,
            visit_token=visit.token,
            detail=outcome.get_state_display(),
        )
    )
    return outcome


# ---------------------------------------------------------------------------
# Clinical priority
# ---------------------------------------------------------------------------


@transaction.atomic
def set_priority(visit: Visit, *, priority: str, actor, reason: str) -> PriorityChange:
    """
    Record a clinical priority decision (spec FR3, FR4, FR5).

    The system records the decision; it never makes it. Only authorised
    clinical roles may call this, every change carries a non-sensitive reason,
    and an emergency is routed to a clinician immediately.
    """
    role = getattr(actor, "role", "")
    if role not in roles_that_may_assign_priority():
        raise PermissionDenied(
            "Only authorised clinical staff may assign clinical priority."
        )
    if priority not in Visit.Priority.values:
        raise QueueError(f"{priority!r} is not a priority level.")
    if not reason or not reason.strip():
        raise QueueError("A non-sensitive reason is required for a priority change.")

    previous = visit.priority
    change = PriorityChange.objects.create(
        visit=visit,
        previous_priority=previous,
        new_priority=priority,
        changed_by_role=role,
        non_sensitive_reason=reason.strip(),
    )

    visit.priority = priority
    visit.save(update_fields=["priority", "last_updated"])

    if priority == Visit.Priority.EMERGENCY:
        _route_emergency(visit, actor=actor)

    record_audit(
        AuditFact(
            action="priority_change",
            actor_role=role,
            visit_token=visit.token,
            detail=f"{previous} -> {priority}: {reason.strip()}",
        )
    )
    return change


def _route_emergency(visit: Visit, *, actor) -> None:
    """
    Send an emergency case straight to clinical care (spec FR4).

    Deliberately forgiving. A patient needing immediate attention must not be
    held up because the software disagreed about which stage they were in, so
    every step here is best-effort and nothing raises.
    """
    try:
        if STAGE_ORDER.index(visit.current_stage) < STAGE_ORDER.index(
            EMERGENCY_STAGE
        ):
            _close_open_event(visit, getattr(actor, "role", ""))
            visit.current_stage = EMERGENCY_STAGE
            StageEvent.objects.create(visit=visit, stage=EMERGENCY_STAGE)

        # An emergency who had stepped away or missed a turn is back in the
        # running order the moment they are escalated.
        if visit.presence_status in {
            Visit.Presence.TEMPORARILY_AWAY,
            Visit.Presence.MISSED_TURN,
        }:
            visit.presence_status = Visit.Presence.RESUMED

        visit.stage_status = Visit.StageStatus.WAITING
        visit.save()
    except Exception:  # noqa: BLE001
        # Log it and carry on. The priority is already recorded, and that is
        # what staff act on; a routing failure must not undo the escalation.
        logger.exception(
            "Emergency routing failed for %s — the priority change stands and "
            "staff must be alerted by other means.",
            visit.token,
        )


def escalate_to_emergency(visit: Visit, *, actor, reason: str) -> PriorityChange:
    """Convenience wrapper — the action a clinician reaches for under pressure."""
    return set_priority(
        visit, priority=Visit.Priority.EMERGENCY, actor=actor, reason=reason
    )


@transaction.atomic
def manual_reorder(visit: Visit, *, actor, reason: str, ahead_of: Visit) -> Visit:
    """
    Move a routine patient ahead of another, with a logged reason.

    Changes only ``queue_order_time``. The recorded check-in time is left
    alone — a reorder is a decision someone made, not a claim that the patient
    arrived earlier than they did.
    """
    if not reason or not reason.strip():
        raise QueueError("A reason is required to reorder the queue.")
    if visit.current_stage != ahead_of.current_stage:
        raise QueueError("Both patients must be waiting at the same stage.")
    if visit.pk == ahead_of.pk:
        raise QueueError("A patient cannot be moved ahead of themselves.")

    # A hair before the other patient, so ordering is unambiguous.
    visit.queue_order_time = ahead_of.queue_order_time - timezone.timedelta(
        microseconds=1
    )
    visit.save(update_fields=["queue_order_time", "last_updated"])

    record_audit(
        AuditFact(
            action="manual_reorder",
            actor_role=getattr(actor, "role", ""),
            visit_token=visit.token,
            detail=f"Moved ahead of {ahead_of.token}: {reason.strip()}",
        )
    )
    return visit


# ---------------------------------------------------------------------------
# Presence (spec FR9)
# ---------------------------------------------------------------------------


@transaction.atomic
def set_presence(visit: Visit, *, presence: str, actor) -> Visit:
    """
    Call, recall, step away, miss a turn, resume.

    Resuming restores the patient to the running order at their existing place:
    the spec says a patient can recover their place, and ``queue_order_time`` is
    never touched here. Staff who judge that unfair to others can move them with
    a manual reorder, which is logged.
    """
    if presence not in Visit.Presence.values:
        raise QueueError(f"{presence!r} is not a presence status.")
    if visit.closed_at:
        raise QueueError(f"Visit {visit.token} is already closed.")

    visit.presence_status = presence
    if presence in {Visit.Presence.CALLED, Visit.Presence.RECALLED}:
        visit.stage_status = Visit.StageStatus.IN_PROGRESS
    elif presence in {Visit.Presence.RESUMED, Visit.Presence.WAITING}:
        visit.stage_status = Visit.StageStatus.WAITING

    visit.save(update_fields=["presence_status", "stage_status", "last_updated"])
    return visit
