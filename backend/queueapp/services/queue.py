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
from datetime import timedelta

from django.conf import settings
from django.db.models import Case, IntegerField, QuerySet, Value, When
from django.utils import timezone

from ..contracts import contracts
from ..models import Visit, token_period_start

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


def current_visits() -> QuerySet[Visit]:
    """
    The visits belonging to the token period now in progress.

    Every live queue is built on this. Tokens are only unique within a period —
    the database constraint is ``unique(token_period, token)`` — and a token is
    how staff actions and the patient's own channel address a visit. A queue
    reaching back over earlier periods would therefore list two different
    patients under one token, and the Start button on the older row would act
    on the current patient.

    It is also what bounds the queues. A patient now leaves the board only when
    pharmacy is done, so a visit abandoned halfway — someone who went home
    without telling anyone — has nothing else to clear it. Scoping to the
    period means such a visit falls out on its own instead of sitting in a
    dashboard for good.

    Earlier records are untouched and stay available to the admin and the
    reports; they simply stop appearing in a queue that is being worked now.
    """
    return Visit.objects.filter(token_period=token_period_start())


def resolve_token(token: str) -> Visit | None:
    """
    The visit a patient means when they type their token.

    An **open** visit always wins. Periods exist so tokens can be reused, but a
    visit that is still going is the one thing that must never be shadowed by
    that reuse: a patient checked in on the last evening of a period is still
    in the clinic the next morning, and their slip has to keep working. Only
    when no open visit holds the token does this fall back to a finished one in
    the current period, so someone who has collected their medication can still
    see that they are done.
    """
    open_visit = (
        Visit.objects.filter(token=token, closed_at__isnull=True)
        .exclude(current_stage="complete")
        .order_by("-check_in_time")
        .first()
    )
    if open_visit is not None:
        return open_visit

    return (
        current_visits()
        .filter(token=token)
        .order_by("-check_in_time")
        .first()
    )


def stale_cutoff():
    """The moment before which an untouched visit counts as abandoned."""
    return timezone.now() - timedelta(hours=settings.STALE_VISIT_HOURS)


def is_stale(visit: Visit) -> bool:
    """Has nothing happened to this visit for STALE_VISIT_HOURS?"""
    if visit.closed_at or visit.current_stage == "complete":
        return False
    return visit.last_updated <= stale_cutoff()


def stale_visits() -> QuerySet[Visit]:
    """
    Visits still open that nothing has touched for STALE_VISIT_HOURS.

    Measured from ``last_updated`` — the time of the last thing that actually
    happened to the visit — rather than from check-in. A patient who arrived
    yesterday morning and was seen at vitals last night is mid-journey, not
    abandoned; one whose record has not moved since they checked in went home
    without telling anybody. Check-in time cannot tell those apart.

    Deliberately **not** scoped to the current token period. A visit that fell
    off the board when the period rolled over is exactly the one that most
    needs closing, and it is the only list in the system that will still show
    it. Oldest first: reception works the backlog from the far end.
    """
    return (
        Visit.objects.filter(closed_at__isnull=True, last_updated__lte=stale_cutoff())
        .exclude(current_stage="complete")
        .select_related("assigned_counter")
        .order_by("last_updated", "id")
    )


def stage_queue(stage: str, *, include_stepped_away: bool = True) -> QuerySet[Visit]:
    """
    Everyone currently waiting at one stage, in service order.

    Staff dashboards include patients who have stepped away, because staff need
    to see them to call them back. Counting who is *ahead* of someone excludes
    them — see ``people_ahead``.
    """
    queryset = current_visits().filter(
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

    # Matched on primary key, not token: a token identifies a visit only
    # within its own period, so the key is what cannot be ambiguous.
    ids = list(stage_queue(visit.current_stage).values_list("pk", flat=True))
    try:
        return ids.index(visit.pk) + 1
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
    queue = stage_queue(visit.current_stage).values_list("pk", "presence_status")

    ahead = 0
    for pk, presence in queue:
        if pk == visit.pk:
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
    One patient on the waiting-room board.

    The board tracks everyone currently in the clinic, so this carries where
    the patient is as well as the token. It carries nothing else. Priority in
    particular is absent by design: it is a clinical judgement, and a public
    screen is the last place it belongs. The dataclass is frozen and has these
    four fields so that a name, a priority or a clinical detail cannot be added
    to a public payload by accident — there is nowhere to put it.

    ``called`` is not clinical. It says only that staff have just asked for
    this token, which is the one thing the board exists to shout.
    """

    token: str
    stage: str
    destination: str
    called: bool


# Far above any real clinic's concurrent load. It exists so a runaway or
# mis-seeded database cannot push an unbounded payload to a wall screen.
DISPLAY_LIMIT = 200


def public_display_rows(limit: int = DISPLAY_LIMIT) -> list[PublicDisplayRow]:
    """
    The public board: every patient currently in the clinic, and where they are.

    This is a tracking board, not a call-forward list. A patient appears from
    the moment they are checked in and stays until pharmacy is finished with
    them, so anyone in the building can find their own token and see how far
    along they are without asking at a desk.

    **Ordered by arrival, deliberately not by service order.** The queues
    themselves run emergencies first, but publishing that order would let the
    room work out who has been given a clinical priority by watching a token
    move up the list. Arrival order discloses nothing and is the order a
    patient can make sense of anyway. The board is a picture of where people
    are; it has never been a promise of who is next.
    """
    visits = (
        current_visits()
        .filter(closed_at__isnull=True)
        .exclude(current_stage="complete")
        .select_related("assigned_counter")
        .order_by("check_in_time", "id")[:limit]
    )

    called_states = {Visit.Presence.CALLED, Visit.Presence.RECALLED}
    return [
        PublicDisplayRow(
            token=visit.token,
            stage=visit.current_stage,
            destination=visit.public_destination,
            called=visit.presence_status in called_states,
        )
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
