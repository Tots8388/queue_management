"""
Management review endpoints (spec FR14).

Both require capabilities that, while governance item G4 is pending, **no role
holds** — so these endpoints exist, are wired up and are tested, and refuse
everybody. That is the gate working: the boundary decides who may see
oversight data, and until it is settled the answer is nobody.
"""

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from . import audit, reporting
from .permissions import Capability, HasCapability


class AuditLogView(APIView):
    """
    The identifiable audit trail, for authorised management review.

    This is the one place an individual member of staff is named. Reporting
    never is — see ``ReportsView``.
    """

    permission_classes = [HasCapability]
    required_capability = Capability.VIEW_AUDIT_LOG

    def get(self, request: Request) -> Response:
        entries = audit.entries_for_review(
            action=request.query_params.get("action") or None,
            token=request.query_params.get("token") or None,
            accountability_only=request.query_params.get("accountability")
            in {"1", "true", "yes"},
            limit=min(int(request.query_params.get("limit", 200)), 500),
        )

        return Response(
            {
                "entries": [
                    {
                        "timestamp": entry.timestamp,
                        "action": entry.action,
                        "actor_role": entry.actor_role,
                        # Present only for accountability actions; routine work
                        # is recorded against the role alone.
                        "actor": (
                            entry.actor_staff_user.get_username()
                            if entry.actor_staff_user
                            else None
                        ),
                        "visit_token": entry.visit_token,
                        "detail": entry.non_sensitive_detail,
                    }
                    for entry in entries
                ]
            }
        )


class ReportsView(APIView):
    """
    De-identified aggregate reporting.

    The payload is checked by ``assert_de_identified`` before it is built into
    a response, so an identifying field cannot be served even if a future query
    accidentally selects one.
    """

    permission_classes = [HasCapability]
    required_capability = Capability.VIEW_ANALYTICS

    def get(self, request: Request) -> Response:
        try:
            days = min(max(int(request.query_params.get("days", 7)), 1), 90)
        except ValueError:
            days = 7

        return Response(reporting.management_report(days))
