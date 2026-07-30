"""
Reading the queue.

One ordering rule, defined once, used by every channel:

    priority rank, then queue order time

Priority rank comes from the shared contracts (emergency 0, urgent 1, routine
2), so an emergency sorts ahead of everything without any special-casing at the
call site — which is what stops an emergency being delayed by a code path
someone forgot to update.

``queue_order_time`` starts equal to the patient's recorded check-in time, so
routine patients are served in check-in order within their stage (spec FR2). It
moves only through a manual reorder, which requires a logged reason.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Case, IntegerField, QuerySet, Value, When

from ..contracts import contracts
from ..models import Visit

# Stages a patient actually waits in. "complete" is not a queue.
ACTIVE_STAGES = [
    stage["key"] for stage in contracts()["stages"] if stage["key"] != "complete"
]

# Presence states that take a patient out of the running order without removing
# them from the queue. They keep their place and can be resumed (spec FR9).
STEPPED_AWAY = {Visit.Presence.TEMPORARILY_AWAY, Visit.Presence.MISSED_TURN}


def priority_rank_expression() -> Case:
    """Sortable rank for each priority, built from the shared contracts."""
    return Case(
        *[
            When(priority=priority["key"], then=Value(priority["rank"]))
            for priority in contracts()["priorities"]
        ],
        default=Value(99),
        output_field=IntegerField(),
    )


def ordered_visits(queryset: QuerySet[Visit] | None = None) -> QuerySet[Visit]:
    """Apply the system's one ordering rule to any set of visits."""
    queryset = Visit.objects.all() if queryset is None else queryset
    return queryset.annotate(priority_rank=priority_rank_expression()).order_by(
        "priority_rank", "queue_order_time", "id"
    )


def stage_queue(stage: str, *, include_stepped_away: bool = True) -> QuerySet[Visit]:
    """
    Everyone currently waiting at one stage, in service order.

    Staff dashboards include patients who have stepped away, because staff need
    to see them to call them back. Counting who is *ahead* of someone excludes
    them — see ``people_ahead``.
    """
    queryset = Visit.objects.filter(
        current_stage=stage,
        stage_status__in=[Visit.StageStatus.WAITING, Visit.StageStatus.IN_PROGRESS],
        closed_at__isnull=True,
    )
    if not include_stepped_away:
        queryset = queryset.exclude(presence_status__in=STEPPED_AWAY)
    return ordered_visits(queryset).select_related("assigned_counter")


def position_in_stage(visit: Visit) -> int | None:
    """
    1-based position in the visit's current stage queue, or None if the visit
    is not waiting in one.
    """
    if visit.current_stage == "complete" or visit.closed_at:
        return None

    tokens = list(
        stage_queue(visit.current_stage).values_list("token", flat=True)
    )
    try:
        return tokens.index(visit.token) + 1
    except ValueError:
        return None


def people_ahead(visit: Visit) -> int | None:
    """
    How many people will be served before this patient (spec FR7).

    Patients who have stepped away are not counted: telling someone four people
    are ahead when two of them are not in the building would make the number
    worse than useless.
    """
    if visit.current_stage == "complete" or visit.closed_at:
        return None

    # One pass over the full stage queue. A patient who has stepped away keeps
    # their place, so they still get a count — of the people ahead who are
    # actually present.
    queue = stage_queue(visit.current_stage).values_list(
        "token", "presence_status"
    )

    ahead = 0
    for token, presence in queue:
        if token == visit.token:
            return ahead
        if presence not in STEPPED_AWAY:
            ahead += 1

    return None


def next_visit(stage: str) -> Visit | None:
    """Who a member of staff should call next at this stage."""
    return stage_queue(stage, include_stepped_away=False).first()


# ---------------------------------------------------------------------------
# Channel payloads
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PublicDisplayRow:
    """
    One line on the waiting-room board.

    Spec FR8 allows exactly two things in public: the anonymous token and where
    it is going. This dataclass has exactly two fields so that a name, priority
    or clinical detail cannot be added to a public payload by accident — there
    is nowhere to put it.
    """

    token: str
    destination: str


def public_display_rows(limit: int = 20) -> list[PublicDisplayRow]:
    """
    The public board: anonymous tokens and destinations only.

    Shows patients who are being called or served, since the board's job is to
    tell people where to go — not to publish the whole queue.
    """
    visits = ordered_visits(
        Visit.objects.filter(
            closed_at__isnull=True,
            presence_status__in=[
                Visit.Presence.CALLED,
                Visit.Presence.RECALLED,
                Visit.Presence.RESUMED,
            ],
        ).exclude(current_stage="complete")
    ).select_related("assigned_counter")[:limit]

    return [
        PublicDisplayRow(token=visit.token, destination=visit.public_destination)
        for visit in visits
    ]


def stage_summary(stage: str) -> dict:
    """Counts a staff dashboard header shows for its stage."""
    queue = stage_queue(stage)
    return {
        "stage": stage,
        "waiting": queue.filter(stage_status=Visit.StageStatus.WAITING).count(),
        "in_progress": queue.filter(
            stage_status=Visit.StageStatus.IN_PROGRESS
        ).count(),
        "stepped_away": queue.filter(presence_status__in=STEPPED_AWAY).count(),
        "emergency": queue.filter(priority=Visit.Priority.EMERGENCY).count(),
        "urgent": queue.filter(priority=Visit.Priority.URGENT).count(),
    }
