"""
Staff authentication.

JWT (``djangorestframework-simplejwt``) with signing keys from the environment.
Patients never authenticate — a patient reaches their own status view with their
token alone, which is why nothing here has a patient-facing path.
"""

import logging

from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .permissions import ROLE_CAPABILITIES
from .serializers import LoginSerializer, LogoutSerializer, StaffUserSerializer

logger = logging.getLogger(__name__)


class LoginView(APIView):
    """
    Exchange staff credentials for an access and refresh token pair.

    Failures return one message for every cause — bad username, bad password,
    disabled account — so the endpoint cannot be used to enumerate who works
    here.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )

        if user is None or not user.is_active or user.role not in ROLE_CAPABILITIES:
            # Logged without the password, and without confirming whether the
            # account exists.
            logger.warning(
                "Failed sign-in attempt for username=%r",
                serializer.validated_data["username"],
            )
            return Response(
                {"detail": "Incorrect username or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": StaffUserSerializer(user).data,
            }
        )


class LogoutView(APIView):
    """
    Revoke a refresh token.

    Clinic terminals are shared between shifts, so signing out has to actually
    end the session rather than just clear the browser's copy of the token.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except TokenError:
            # Already expired or already revoked — the caller wanted the session
            # gone, and it is gone. Reporting an error here would only tempt a
            # frontend into leaving a token in place on a shared machine.
            pass

        return Response(status=status.HTTP_205_RESET_CONTENT)


class CurrentUserView(APIView):
    """Who am I, and what may I do? Drives dashboard routing after a refresh."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(StaffUserSerializer(request.user).data)
