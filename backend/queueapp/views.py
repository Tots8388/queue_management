"""
Infrastructure endpoints. Queue behaviour arrives in Phase 3.
"""

from django.conf import settings
from django.db import connection
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from . import contracts


class HealthView(APIView):
    """
    Liveness/readiness probe for the clinic machine.

    Unauthenticated on purpose: staff need to see whether the queue server is
    up before they can log in, and the offline fallback decision depends on it.
    Exposes no queue data.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request: Request) -> Response:
        try:
            connection.ensure_connection()
            database_ok = True
        except Exception:  # noqa: BLE001 — report the failure, don't raise it
            database_ok = False

        engine = connection.settings_dict["ENGINE"].rsplit(".", 1)[-1]
        return Response(
            {
                "status": "ok" if database_ok else "degraded",
                "database": {"connected": database_ok, "engine": engine},
                "realtime": {
                    "channel_layer": settings.CHANNEL_LAYERS["default"]["BACKEND"]
                    .rsplit(".", 1)[-1],
                },
                "sms_enabled": settings.SMS_ENABLED,
                "environment": settings.DJANGO_ENV,
            },
            status=200 if database_ok else 503,
        )


class ContractsView(APIView):
    """
    The shared queue vocabulary — roles, stages, statuses, priorities.

    Served so the frontend can render labels without hard-coding them. Contains
    only vocabulary, no patient or queue data, so it is unauthenticated.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request: Request) -> Response:
        return Response(contracts.contracts())
