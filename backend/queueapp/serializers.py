"""
Serializers.

Queue and visit serializers arrive with the queue engine in Phase 3. This module
currently covers the signed-in staff account.
"""

from rest_framework import serializers

from . import contracts
from .models import ServiceCounter, StaffUser
from .permissions import capabilities_for


class ServiceCounterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCounter
        fields = ["id", "name", "stage", "is_active"]


class StaffUserSerializer(serializers.ModelSerializer):
    """
    The signed-in user, as their dashboard needs them.

    Includes the capability list so the frontend can hide controls the role
    cannot use. That is a usability measure, not a security one — every action
    is checked again on the server.
    """

    role_label = serializers.SerializerMethodField()
    capabilities = serializers.SerializerMethodField()
    dashboard = serializers.SerializerMethodField()
    default_counter = ServiceCounterSerializer(read_only=True)

    class Meta:
        model = StaffUser
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "role",
            "role_label",
            "capabilities",
            "dashboard",
            "default_counter",
        ]
        read_only_fields = fields

    def get_role_label(self, user: StaffUser) -> str:
        return user.get_role_display()

    def get_capabilities(self, user: StaffUser) -> list[str]:
        return sorted(capabilities_for(user.role))

    def get_dashboard(self, user: StaffUser) -> str | None:
        """
        Where this role's work happens. Null for Supervisor and IT/Support until
        governance item G4 settles the oversight boundary — a role with no
        capabilities has no dashboard to be sent to.
        """
        return contracts.by_key("roles", user.role).get("dashboard")


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(write_only=True)


class ContractsSerializer(serializers.Serializer):
    """Passthrough for the shared vocabulary; kept for schema clarity."""

    def to_representation(self, instance) -> dict:
        return contracts.contracts()
