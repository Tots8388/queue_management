"""
WebSocket consumers — the three channels that share one queue state.

Each consumer sends its current state immediately on connect. That is what
makes reconnection work: a phone that lost signal, or a display screen that was
switched off overnight, gets the present state on reconnect rather than waiting
for the next change. There is no replay of missed events and no need for one,
because every message is the whole of that channel's view.

Consumers never receive a payload from the broadcaster — they are told only
that something changed, and rebuild their own view through the service layer.
See ``services/broadcast.py`` for why.
"""

import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from .models import Visit
from .permissions import Capability, role_has
from .serializers import (
    PatientStatusSerializer,
    PublicDisplayRowSerializer,
    StaffVisitSerializer,
)
from .services import broadcast
from .services import queue as queue_service

logger = logging.getLogger(__name__)


class BaseQueueConsumer(AsyncJsonWebsocketConsumer):
    """Subscribe to a group, push current state, push it again on every change."""

    group_name: str = ""

    @classmethod
    async def encode_json(cls, content) -> str:
        # Payloads carry timestamps, which the stdlib encoder cannot handle.
        # DjangoJSONEncoder renders them as ISO-8601, matching the REST
        # responses so a client parses both channels the same way.
        return json.dumps(content, cls=DjangoJSONEncoder)

    async def connect(self):
        if not await self.authorise():
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_state()

    async def disconnect(self, code):
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def authorise(self) -> bool:
        return True

    async def receive_json(self, content, **kwargs):
        """
        Clients may ask for a resync — after a sleep/wake, say, when they cannot
        tell whether they missed anything.
        """
        if content.get("action") == "resync":
            await self.send_state()

    async def queue_changed(self, event) -> None:
        await self.send_state()

    async def send_state(self) -> None:
        payload = await self.build_state()
        if payload is None:
            await self.close(code=4404)
            return
        await self.send_json({**payload, "generated_at": timezone.now().isoformat()})

    async def build_state(self) -> dict | None:  # pragma: no cover - abstract
        raise NotImplementedError


class PublicDisplayConsumer(BaseQueueConsumer):
    """
    The waiting-room board (spec FR8).

    Unauthenticated — it drives a screen on a wall. The payload is built by
    ``public_display_rows()``, which returns a two-field dataclass, so this
    consumer has no way to put a name or a priority category on a public screen.
    """

    group_name = broadcast.DISPLAY_GROUP

    @database_sync_to_async
    def build_state(self) -> dict:
        rows = queue_service.public_display_rows()
        return {
            "channel": "display",
            "rows": PublicDisplayRowSerializer(rows, many=True).data,
        }


class PatientStatusConsumer(BaseQueueConsumer):
    """
    One patient's own status (spec FR7).

    Unauthenticated for the same reason the REST endpoint is: patients have no
    accounts, and holding the token identifies the visit. The payload carries no
    priority category and no clinical detail, so a guessed token discloses
    nothing about a person.
    """

    async def connect(self):
        self.token = self.scope["url_route"]["kwargs"]["token"]
        self.group_name = broadcast.visit_group(self.token)
        await super().connect()

    @database_sync_to_async
    def build_state(self) -> dict | None:
        visit = Visit.objects.filter(
            token=self.token, token_date=timezone.localdate()
        ).first()
        if visit is None:
            return None
        return {"channel": "patient", **PatientStatusSerializer.from_visit(visit)}


class StaffQueueConsumer(BaseQueueConsumer):
    """
    One stage's queue, for the staff working it.

    Authenticated and capability-checked on connect, the same rule the REST
    endpoint applies — a socket must not be a way around a permission.
    """

    async def connect(self):
        self.stage = self.scope["url_route"]["kwargs"]["stage"]
        self.group_name = broadcast.stage_group(self.stage)
        await super().connect()

    async def authorise(self) -> bool:
        user = self.scope.get("user")
        if not user or not user.is_authenticated or not user.is_active:
            return False
        if self.stage not in queue_service.ACTIVE_STAGES:
            return False
        return role_has(user.role, Capability.VIEW_STAGE_QUEUE)

    @database_sync_to_async
    def build_state(self) -> dict:
        visits = queue_service.stage_queue(self.stage)
        return {
            "channel": "staff",
            "stage": self.stage,
            "summary": queue_service.stage_summary(self.stage),
            "visits": StaffVisitSerializer(visits, many=True).data,
        }
