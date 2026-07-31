"""
Telling the channels that the queue changed.

A deliberate design choice runs through this module: a broadcast carries a
**notification, not a payload**. It says "the vitals queue changed"; it does not
say what the queue now contains. Each consumer then rebuilds its own view
through the same service functions the REST endpoints use.

That costs a little more work per event and buys two things:

* The public display's payload is always built by ``public_display_rows()``, so
  a name or priority category cannot reach a public screen even if someone
  broadcasts a rich object from a staff code path. The privacy rule is
  structural rather than a habit.
* Every channel reads one authoritative queue state, so a patient's view and
  the staff dashboard cannot disagree about who is next.

Broadcasts are queued with ``transaction.on_commit`` so nothing announces a
state that then rolls back.
"""

from __future__ import annotations

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

logger = logging.getLogger(__name__)

DISPLAY_GROUP = "display"


def stage_group(stage: str) -> str:
    return f"stage.{stage}"


def visit_group(token: str) -> str:
    return f"visit.{token}"


def _send(group: str, message: dict) -> None:
    layer = get_channel_layer()
    if layer is None:  # pragma: no cover — only if Channels is misconfigured
        logger.warning("No channel layer configured; %s not notified.", group)
        return
    try:
        async_to_sync(layer.group_send)(group, message)
    except Exception:  # noqa: BLE001
        # A real-time update failing must never take down the queue operation
        # that triggered it. Staff dashboards refresh on their own; the
        # authoritative state is in the database either way.
        logger.exception("Failed to notify %s of a queue change.", group)


def queue_changed(*, token: str | None = None, stages: list[str] | None = None) -> None:
    """
    Announce that the queue changed.

    ``stages`` should name every stage whose queue is affected — for a
    transition that is both the stage left and the stage joined, or a dashboard
    keeps showing a patient who has moved on.
    """
    groups = [DISPLAY_GROUP]
    groups += [stage_group(stage) for stage in (stages or [])]
    if token:
        groups.append(visit_group(token))

    def publish() -> None:
        for group in dict.fromkeys(groups):  # de-duplicated, order preserved
            _send(group, {"type": "queue.changed"})

    transaction.on_commit(publish)
