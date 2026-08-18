"""
Serializers.

Queue and visit serializers arrive with the queue engine in Phase 3. This module
currently covers the signed-in staff account.
"""

from rest_framework import serializers

from . import contracts
from .models import PharmacyOutcome, ServiceCounter, StaffUser, Visit
from .permissions import capabilities_for
from .services import queue as queue_service
from .services import wait_range


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


# ---------------------------------------------------------------------------
# Queue
# ---------------------------------------------------------------------------


class StaffVisitSerializer(serializers.ModelSerializer):
    """
    A visit as a staff dashboard shows it.

    Includes priority, which is why this serializer must never be used for a
    patient-facing or public response — see ``PatientStatusSerializer`` and
    ``PublicDisplayRowSerializer``.
    """

    stage_label = serializers.CharField(source="get_current_stage_display")
    priority_label = serializers.CharField(source="get_priority_display")
    presence_label = serializers.CharField(source="get_presence_status_display")
    counter = serializers.CharField(source="assigned_counter.name", default=None)
    waiting_minutes = serializers.SerializerMethodField()

    class Meta:
        model = Visit
        fields = [
            "id",
            "token",
            "current_stage",
            "stage_label",
            "stage_status",
            "priority",
            "priority_label",
            "presence_status",
            "presence_label",
            "counter",
            "awaiting_tests",
            "check_in_time",
            "waiting_minutes",
            "last_updated",
        ]
        read_only_fields = fields

    def get_waiting_minutes(self, visit: Visit) -> int:
        from django.utils import timezone

        return int((timezone.now() - visit.check_in_time).total_seconds() // 60)


class StaleVisitSerializer(StaffVisitSerializer):
    """
    A visit reception is being asked to close as abandoned.

    Adds how long it has sat untouched, because that is the whole basis for
    the decision — "waiting 19 hours" and "nothing has happened for 19 hours"
    are different claims, and only the second one justifies closing a visit.
    Carries the id as well, which is how the close endpoint addresses it: a
    stale token may already have been reissued to a patient in the room.
    """

    idle_hours = serializers.SerializerMethodField()

    class Meta(StaffVisitSerializer.Meta):
        fields = StaffVisitSerializer.Meta.fields + ["idle_hours"]
        read_only_fields = fields

    def get_idle_hours(self, visit: Visit) -> int:
        from django.utils import timezone

        return int((timezone.now() - visit.last_updated).total_seconds() // 3600)


class PatientStatusSerializer(serializers.Serializer):
    """
    What a patient sees about their own visit (spec FR7).

    Carries no priority category: a patient is told what is happening to them,
    not how they were triaged relative to others. The wait range is filled in
    by the Phase 6 calculation; until then it reports as unavailable, which is
    the correct answer when there is no reliable estimate.
    """

    token = serializers.CharField()
    current_stage = serializers.CharField()
    stage_label = serializers.CharField()
    next_stage_label = serializers.CharField(allow_null=True)
    stage_status = serializers.CharField()
    presence_status = serializers.CharField()
    people_ahead = serializers.IntegerField(allow_null=True)
    wait_range = serializers.DictField()
    last_updated = serializers.DateTimeField()

    @classmethod
    def from_visit(cls, visit: Visit) -> dict:
        stages = contracts.contracts()["stages"]
        index = next(
            (i for i, s in enumerate(stages) if s["key"] == visit.current_stage), None
        )
        next_label = (
            stages[index + 1]["label"] if index is not None and index + 1 < len(stages) else None
        )

        return {
            "token": visit.token,
            "current_stage": visit.current_stage,
            "stage_label": visit.get_current_stage_display(),
            "next_stage_label": next_label,
            "stage_status": visit.stage_status,
            "presence_status": visit.presence_status,
            "people_ahead": queue_service.people_ahead(visit),
            "wait_range": wait_range.estimate_for(visit).as_dict(),
            "last_updated": visit.last_updated,
        }


class PublicDisplayRowSerializer(serializers.Serializer):
    """
    One patient on the waiting-room board (spec FR8).

    The board tracks where everyone in the clinic is, so it carries the stage
    and the destination alongside the token. It carries nothing more: no name,
    no priority category, no clinical detail may ever appear on a public
    screen, and no field here could hold one.
    """

    token = serializers.CharField()
    stage = serializers.CharField()
    destination = serializers.CharField()
    called = serializers.BooleanField()


class CheckInSerializer(serializers.Serializer):
    notification_preference = serializers.ChoiceField(
        choices=contracts.keys("notification_preferences"), default="screen"
    )
    phone_number = serializers.CharField(required=False, allow_blank=True)
    counter_id = serializers.IntegerField(required=False, allow_null=True)


class FallbackReconciliationSerializer(serializers.Serializer):
    """One line from the paper sheet kept during an outage (spec FR12)."""

    arrived_at = serializers.DateTimeField(
        help_text="The arrival time written on the paper sheet, not the time now."
    )
    paper_reference = serializers.CharField(
        max_length=40, required=False, allow_blank=True
    )
    stage = serializers.ChoiceField(
        choices=contracts.keys("stages"), default="registration"
    )


class PrioritySerializer(serializers.Serializer):
    priority = serializers.ChoiceField(choices=Visit.Priority.choices)
    # Free clinical text does not belong in this database, so the reason is
    # bounded and described to the caller as a category.
    reason = serializers.CharField(max_length=120)


class PresenceSerializer(serializers.Serializer):
    presence = serializers.ChoiceField(choices=Visit.Presence.choices)


class ReorderSerializer(serializers.Serializer):
    ahead_of_token = serializers.CharField()
    reason = serializers.CharField(max_length=120)


class PharmacyOutcomeSerializer(serializers.Serializer):
    state = serializers.ChoiceField(choices=PharmacyOutcome.State.choices)


class TransferSerializer(serializers.Serializer):
    to_stage = serializers.ChoiceField(
        choices=contracts.keys("stages"), required=False
    )
