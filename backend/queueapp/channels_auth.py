"""
WebSocket authentication for staff channels.

Staff sign in over REST and get a JWT. A browser cannot set an Authorization
header on a WebSocket handshake, so the access token arrives as a query
parameter instead: ``ws://host/ws/staff/vitals/?token=<access token>``.

That is a real trade-off. Query strings turn up in server logs and proxy logs
in a way headers do not, which is why the token used here is the short-lived
**access** token and never the refresh token. On the clinic's own LAN, with the
logs on the same machine, this is an acceptable exposure; if the system ever
runs over a network the Medical Center does not control, move to a
subprotocol-based scheme.
"""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def _user_from_token(raw_token: str):
    from .models import StaffUser

    try:
        token = AccessToken(raw_token)
        user = StaffUser.objects.get(pk=token["user_id"])
    except (InvalidToken, TokenError, KeyError, StaffUser.DoesNotExist):
        return AnonymousUser()

    return user if user.is_active else AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """Populates ``scope["user"]`` from a ``token`` query parameter."""

    async def __call__(self, scope, receive, send):
        if scope.get("user") is None or scope["user"].is_anonymous:
            query = parse_qs(scope.get("query_string", b"").decode())
            raw_token = (query.get("token") or [None])[0]
            if raw_token:
                scope["user"] = await _user_from_token(raw_token)

        return await super().__call__(scope, receive, send)
