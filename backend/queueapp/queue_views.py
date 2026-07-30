"""
Queue endpoints.

Views validate input, check the caller's capability, and hand off to
``services.operations``. They contain no queue policy of their own — the policy
lives in one place so no channel can enforce a different version of it.
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ServiceCounter, Visit
from .permissions import (
    Capability,
    HasCapability,
    IsStaff,
    MayAssignPriority,
    role_has,
)
from .serializers import (
    CheckInSerializer,
    PatientStatusSerializer,
    PharmacyOutcomeSerializer,
    PresenceSerializer,
    PrioritySerializer,
    PublicDisplayRowSerializer,
    ReorderSerializer,
    StaffVisitSerializer,
    TransferSerializer,
)
from .services import operations
from .services import queue as queue_service


def _visit(token: str) -> Visit:
    """Look a visit up by today's token."""
    return get_object_or_404(Visit, token=token, token_date=timezone.localdate())


class QueueActionView(APIView):
    """
    Base for actions on one visit.

    Translates the service layer's errors into HTTP so each view does not
    repeat it: a refused clinical permission is 403, an impossible queue
    operation is 400.
    """

    permission_classes = [HasCapability]

    def handle_exception(self, exc):
        if isinstance(exc, PermissionDenied):
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        if isinstance(exc, ValidationError):
            return Response(
                {"detail": exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().handle_exception(exc)


# ---------------------------------------------------------------------------
# Reception
# ---------------------------------------------------------------------------


class CheckInView(QueueActionView):
    """Register a patient and issue a token (spec FR1)."""

    required_capability = Capability.REGISTER_PATIENT

    def post(self, request: Request) -> Response:
        serializer = CheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        counter = None
        if data.get("counter_id"):
            counter = get_object_or_404(ServiceCounter, pk=data["counter_id"])

        visit = operations.check_in(
            actor=request.user,
            notification_preference=data["notification_preference"],
            phone_number=data.get("phone_number") or None,
            counter=counter,
        )
        return Response(
            StaffVisitSerializer(visit).data, status=status.HTTP_201_CREATED
        )


# ---------------------------------------------------------------------------
# Staff queue views
# ---------------------------------------------------------------------------


class StageQueueView(QueueActionView):
    """The queue at one stage, in service order."""

    required_capability = Capability.VIEW_STAGE_QUEUE

    def get(self, request: Request, stage: str) -> Response:
        if stage not in queue_service.ACTIVE_STAGES:
            return Response(
                {"detail": f"{stage!r} is not a stage patients wait in."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        visits = queue_service.stage_queue(stage)
        return Response(
            {
                "summary": queue_service.stage_summary(stage),
                "visits": StaffVisitSerializer(visits, many=True).data,
            }
        )


class StartServingView(QueueActionView):
    required_capability = Capability.CALL_PATIENT

    def post(self, request: Request, token: str) -> Response:
        visit = operations.start_serving(_visit(token), actor=request.user)
        return Response(StaffVisitSerializer(visit).data)


class CompleteStageView(QueueActionView):
    """
    Mark the current stage complete and move the patient on (FR6, FR10).

    Which capability is required depends on the stage being completed, so a
    pharmacist cannot close a consultation and a nurse cannot dispense. That
    cannot be expressed as a class-level ``required_capability``, because the
    stage is only known once the visit has been looked up — so the view holds
    the door with ``IsStaff`` and makes the specific check itself.
    """

    permission_classes = [IsStaff]

    CAPABILITY_BY_STAGE = {
        "registration": Capability.TRANSFER_STAGE,
        "vitals": Capability.COMPLETE_VITALS,
        "consultation": Capability.COMPLETE_CONSULTATION,
        "pharmacy": Capability.RECORD_PHARMACY_OUTCOME,
    }

    def post(self, request: Request, token: str) -> Response:
        visit = _visit(token)

        # An unmapped stage yields no capability, and no capability is a
        # refusal — an unhandled stage must never fall through to allowed.
        required = self.CAPABILITY_BY_STAGE.get(visit.current_stage)
        if not required or not role_has(request.user.role, required):
            return Response(
                {
                    "detail": (
                        f"Your role does not complete the "
                        f"{visit.get_current_stage_display().lower()} stage."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = TransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        visit = operations.complete_stage(
            visit,
            actor=request.user,
            to_stage=serializer.validated_data.get("to_stage"),
        )
        return Response(StaffVisitSerializer(visit).data)


class PresenceView(QueueActionView):
    """Call, recall, step away, miss a turn, resume (spec FR9)."""

    required_capability = Capability.SET_PRESENCE

    def post(self, request: Request, token: str) -> Response:
        serializer = PresenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        visit = operations.set_presence(
            _visit(token),
            presence=serializer.validated_data["presence"],
            actor=request.user,
        )
        return Response(StaffVisitSerializer(visit).data)


# ---------------------------------------------------------------------------
# Clinical
# ---------------------------------------------------------------------------


class PriorityView(QueueActionView):
    """
    Record a clinical priority decision (spec FR3, FR4, FR5).

    Guarded by the named permission rather than a generic capability check,
    because this is the one access rule the spec singles out.
    """

    permission_classes = [MayAssignPriority]
    required_capability = Capability.ASSIGN_PRIORITY

    def post(self, request: Request, token: str) -> Response:
        serializer = PrioritySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        visit = _visit(token)
        operations.set_priority(
            visit,
            priority=serializer.validated_data["priority"],
            actor=request.user,
            reason=serializer.validated_data["reason"],
        )
        visit.refresh_from_db()
        return Response(StaffVisitSerializer(visit).data)


class ReorderView(QueueActionView):
    """Move a patient ahead of another, with a logged reason."""

    required_capability = Capability.MANUAL_REORDER

    def post(self, request: Request, token: str) -> Response:
        serializer = ReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        visit = operations.manual_reorder(
            _visit(token),
            actor=request.user,
            reason=serializer.validated_data["reason"],
            ahead_of=_visit(serializer.validated_data["ahead_of_token"]),
        )
        return Response(StaffVisitSerializer(visit).data)


class SendForTestsView(QueueActionView):
    required_capability = Capability.RETURN_AFTER_TESTS

    def post(self, request: Request, token: str) -> Response:
        visit = operations.send_for_tests(_visit(token), actor=request.user)
        return Response(StaffVisitSerializer(visit).data)


class ReturnAfterTestsView(QueueActionView):
    """Spec FR13 — back to the clinician, with prior history intact."""

    required_capability = Capability.RETURN_AFTER_TESTS

    def post(self, request: Request, token: str) -> Response:
        visit = operations.return_after_tests(_visit(token), actor=request.user)
        return Response(StaffVisitSerializer(visit).data)


class PharmacyOutcomeView(QueueActionView):
    """Medicine ready, issued or unavailable (spec FR10)."""

    required_capability = Capability.RECORD_PHARMACY_OUTCOME

    def post(self, request: Request, token: str) -> Response:
        serializer = PharmacyOutcomeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        visit = _visit(token)
        operations.record_pharmacy_outcome(
            visit, state=serializer.validated_data["state"], actor=request.user
        )
        visit.refresh_from_db()
        return Response(StaffVisitSerializer(visit).data)


# ---------------------------------------------------------------------------
# Patient and public channels
# ---------------------------------------------------------------------------


class PatientStatusView(APIView):
    """
    A patient's own status (spec FR7).

    Unauthenticated: patients have no accounts, and holding the token is what
    identifies the visit. The response carries no priority category and no
    clinical detail, so a token guessed by a stranger discloses nothing about a
    person — only that a visit is at some stage of a queue.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request: Request, token: str) -> Response:
        visit = _visit(token)
        return Response(PatientStatusSerializer.from_visit(visit))


class PublicDisplayView(APIView):
    """
    The waiting-room board (spec FR8).

    Anonymous token and destination only. The payload is built from a two-field
    dataclass, so there is no field on it that could carry a name, a priority
    category or a clinical detail.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request: Request) -> Response:
        rows = queue_service.public_display_rows()
        return Response(
            {
                "rows": PublicDisplayRowSerializer(rows, many=True).data,
                "generated_at": timezone.now(),
            }
        )
