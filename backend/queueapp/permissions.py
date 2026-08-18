"""
Role-based access control.

Least privilege is expressed as one capability matrix rather than as conditions
scattered through views: it is the thing an auditor asks to see, and a rule that
lives in one place can be read, tested and shown to a reviewer. Views declare
the capability they need; they never test roles directly.

The matrix below covers the four station roles. Supervisor and IT/Support hold
**no capabilities** until governance item G4 settles the oversight boundary —
see ``OVERSIGHT_ROLES`` at the end of this module. That is deliberate: while the
question is open, the answer is no.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission

from .contracts import roles_that_may_assign_priority
from .models import Role


class Capability:
    """
    Named actions the system can perform on the queue.

    Kept as constants so a typo in a view becomes an ImportError rather than a
    silently-granted permission.
    """

    # Reception
    REGISTER_PATIENT = "register_patient"
    OPERATE_FALLBACK = "operate_fallback"
    # Close a visit nothing has happened to for STALE_VISIT_HOURS. Reception's,
    # because reception is the desk that knows who walked back out. Not a
    # clinical decision and not a way to clear a live queue: the server refuses
    # any visit that is not already stale.
    CLOSE_ABANDONED_VISIT = "close_abandoned_visit"

    # Stage completions (spec FR10)
    COMPLETE_VITALS = "complete_vitals"
    COMPLETE_CONSULTATION = "complete_consultation"
    RECORD_PHARMACY_OUTCOME = "record_pharmacy_outcome"
    CLOSE_VISIT = "close_visit"

    # Clinical decisions (spec FR3, FR4, FR5) — clinical roles only
    ASSIGN_PRIORITY = "assign_priority"
    MANUAL_REORDER = "manual_reorder"
    RETURN_AFTER_TESTS = "return_after_tests"

    # Queue operation (spec FR9)
    VIEW_STAGE_QUEUE = "view_stage_queue"
    CALL_PATIENT = "call_patient"
    SET_PRESENCE = "set_presence"
    TRANSFER_STAGE = "transfer_stage"

    # Oversight and administration — granted only once G4 is approved.
    VIEW_AUDIT_LOG = "view_audit_log"
    VIEW_ANALYTICS = "view_analytics"
    CONFIGURE_QUEUE = "configure_queue"
    MANAGE_USERS = "manage_users"
    VIEW_SYSTEM_HEALTH = "view_system_health"


# Every role that operates a station. Each gets exactly what its stage needs.
STATION_CAPABILITIES: dict[str, frozenset[str]] = {
    Role.REGISTRATION_CLERK: frozenset(
        {
            Capability.REGISTER_PATIENT,
            Capability.OPERATE_FALLBACK,
            Capability.CLOSE_ABANDONED_VISIT,
            Capability.VIEW_STAGE_QUEUE,
            Capability.CALL_PATIENT,
            Capability.SET_PRESENCE,
            Capability.TRANSFER_STAGE,
        }
    ),
    Role.NURSE_VITALS: frozenset(
        {
            Capability.COMPLETE_VITALS,
            Capability.ASSIGN_PRIORITY,
            Capability.MANUAL_REORDER,
            Capability.VIEW_STAGE_QUEUE,
            Capability.CALL_PATIENT,
            Capability.SET_PRESENCE,
            Capability.TRANSFER_STAGE,
        }
    ),
    Role.CLINICIAN: frozenset(
        {
            Capability.COMPLETE_CONSULTATION,
            Capability.ASSIGN_PRIORITY,
            Capability.MANUAL_REORDER,
            Capability.RETURN_AFTER_TESTS,
            Capability.VIEW_STAGE_QUEUE,
            Capability.CALL_PATIENT,
            Capability.SET_PRESENCE,
            Capability.TRANSFER_STAGE,
        }
    ),
    Role.PHARMACIST: frozenset(
        {
            Capability.RECORD_PHARMACY_OUTCOME,
            Capability.CLOSE_VISIT,
            Capability.VIEW_STAGE_QUEUE,
            Capability.CALL_PATIENT,
            Capability.SET_PRESENCE,
        }
    ),
}

# Supervisor/Management and IT/Support. Their capabilities are governance item
# G4 and are defined in ``oversight.py``, which does not exist until G4 is
# approved. Until then they authenticate successfully and can do nothing —
# the gate withholds access rather than merely postponing a file.
OVERSIGHT_ROLES = frozenset({Role.SUPERVISOR, Role.IT_SUPPORT})

try:  # pragma: no cover — exercised only once G4 is approved
    from .oversight import OVERSIGHT_CAPABILITIES
except ImportError:
    OVERSIGHT_CAPABILITIES: dict[str, frozenset[str]] = {
        role: frozenset() for role in OVERSIGHT_ROLES
    }


ROLE_CAPABILITIES: dict[str, frozenset[str]] = {
    **STATION_CAPABILITIES,
    **OVERSIGHT_CAPABILITIES,
}


def capabilities_for(role: str) -> frozenset[str]:
    """What a role may do. An unknown role gets nothing."""
    return ROLE_CAPABILITIES.get(role, frozenset())


def role_has(role: str, capability: str) -> bool:
    return capability in capabilities_for(role)


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------
# Spec FR3 is not merely implemented above — it is checked at import time, so a
# well-meaning edit that hands ASSIGN_PRIORITY to reception fails immediately
# and loudly rather than at some point in a clinic.
_PRIVILEGED = {
    Capability.ASSIGN_PRIORITY: set(roles_that_may_assign_priority()),
}

for _capability, _allowed_roles in _PRIVILEGED.items():
    _actual = {
        role for role, caps in ROLE_CAPABILITIES.items() if _capability in caps
    }
    if _actual != _allowed_roles:
        raise RuntimeError(
            f"Least-privilege violation: {_capability!r} is granted to "
            f"{sorted(_actual)}, but the shared contracts permit only "
            f"{sorted(_allowed_roles)} (spec FR3)."
        )


# ---------------------------------------------------------------------------
# DRF permission classes
# ---------------------------------------------------------------------------


class IsStaff(BasePermission):
    """Authenticated, active staff account with a recognised role."""

    message = "This action requires a signed-in staff account."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.role in ROLE_CAPABILITIES
        )


class HasCapability(IsStaff):
    """
    Grants access when the user's role holds ``view.required_capability``.

    A view that forgets to declare one is denied, not allowed — the failure mode
    of an oversight should be no access.
    """

    message = "Your role does not permit this action."

    def has_permission(self, request, view) -> bool:
        if not super().has_permission(request, view):
            return False

        capability = getattr(view, "required_capability", None)
        if not capability:
            return False

        return role_has(request.user.role, capability)


def requires(capability: str) -> type[BasePermission]:
    """
    Build a permission class for one capability.

        permission_classes = [requires(Capability.COMPLETE_VITALS)]

    Useful where a view needs a capability that is not its main one, or where
    declaring ``required_capability`` on the view would be less readable.
    """

    class _RequiresCapability(HasCapability):
        def has_permission(self, request, view) -> bool:
            if not IsStaff().has_permission(request, view):
                return False
            return role_has(request.user.role, capability)

    _RequiresCapability.__name__ = f"Requires_{capability}"
    return _RequiresCapability


class MayAssignPriority(HasCapability):
    """
    Spec FR3: only authorised clinical roles may set emergency or urgent
    priority. Reception, pharmacy, management and IT/Support may not.

    Named explicitly rather than left as a generic capability check, because it
    is the one access rule the spec singles out and the one a reviewer will look
    for by name.
    """

    message = (
        "Only authorised clinical staff (nurse/triage, clinician) may assign "
        "clinical priority."
    )

    def has_permission(self, request, view) -> bool:
        if not IsStaff().has_permission(request, view):
            return False
        return role_has(request.user.role, Capability.ASSIGN_PRIORITY)
