"""
Phase 2 tests: every role can reach exactly what it should, and nothing else.

These are written as a matrix rather than as one test per rule, so adding a
capability to a role without deciding it deliberately shows up as a failure.
"""

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from .models import Role, StaffUser
from .permissions import (
    OVERSIGHT_ROLES,
    ROLE_CAPABILITIES,
    Capability,
    HasCapability,
    IsStaff,
    MayAssignPriority,
    capabilities_for,
    requires,
    role_has,
)

# The authoritative expectation. If a change to permissions.py disagrees with
# this table, one of the two is wrong and someone has to decide which.
EXPECTED_CAPABILITIES = {
    Role.REGISTRATION_CLERK: {
        Capability.REGISTER_PATIENT,
        Capability.OPERATE_FALLBACK,
        Capability.VIEW_STAGE_QUEUE,
        Capability.CALL_PATIENT,
        Capability.SET_PRESENCE,
        Capability.TRANSFER_STAGE,
    },
    Role.NURSE_VITALS: {
        Capability.COMPLETE_VITALS,
        Capability.ASSIGN_PRIORITY,
        Capability.MANUAL_REORDER,
        Capability.VIEW_STAGE_QUEUE,
        Capability.CALL_PATIENT,
        Capability.SET_PRESENCE,
        Capability.TRANSFER_STAGE,
    },
    Role.CLINICIAN: {
        Capability.COMPLETE_CONSULTATION,
        Capability.ASSIGN_PRIORITY,
        Capability.MANUAL_REORDER,
        Capability.RETURN_AFTER_TESTS,
        Capability.VIEW_STAGE_QUEUE,
        Capability.CALL_PATIENT,
        Capability.SET_PRESENCE,
        Capability.TRANSFER_STAGE,
    },
    Role.PHARMACIST: {
        Capability.RECORD_PHARMACY_OUTCOME,
        Capability.CLOSE_VISIT,
        Capability.VIEW_STAGE_QUEUE,
        Capability.CALL_PATIENT,
        Capability.SET_PRESENCE,
    },
    # Blocked by governance item G4 — no capabilities until it is approved.
    Role.SUPERVISOR: set(),
    Role.IT_SUPPORT: set(),
}


class CapabilityMatrixTests(TestCase):
    def test_each_role_holds_exactly_its_expected_capabilities(self):
        for role, expected in EXPECTED_CAPABILITIES.items():
            with self.subTest(role=role):
                self.assertEqual(set(capabilities_for(role)), expected)

    def test_every_role_appears_in_the_matrix(self):
        self.assertEqual(set(ROLE_CAPABILITIES), {role.value for role in Role})

    def test_an_unknown_role_gets_nothing(self):
        self.assertEqual(capabilities_for("hospital_director"), frozenset())
        self.assertEqual(capabilities_for(""), frozenset())


class PriorityRestrictionTests(TestCase):
    """Spec FR3 — the access rule the spec singles out."""

    def test_only_nurse_and_clinician_may_assign_priority(self):
        allowed = {
            role
            for role in ROLE_CAPABILITIES
            if role_has(role, Capability.ASSIGN_PRIORITY)
        }
        self.assertEqual(allowed, {Role.NURSE_VITALS, Role.CLINICIAN})

    def test_reception_and_pharmacy_cannot_assign_priority(self):
        for role in [Role.REGISTRATION_CLERK, Role.PHARMACIST]:
            with self.subTest(role=role):
                self.assertFalse(role_has(role, Capability.ASSIGN_PRIORITY))

    def test_management_and_it_support_cannot_assign_priority(self):
        """Neither oversight role assigns clinical priority, approved or not."""
        for role in OVERSIGHT_ROLES:
            with self.subTest(role=role):
                self.assertFalse(role_has(role, Capability.ASSIGN_PRIORITY))


class OversightGateTests(TestCase):
    def test_oversight_roles_hold_nothing_while_g4_is_pending(self):
        """
        The governance gate withholds access rather than postponing a file: with
        oversight.py absent, Supervisor and IT/Support sign in successfully and
        can do nothing at all.
        """
        for role in OVERSIGHT_ROLES:
            with self.subTest(role=role):
                self.assertEqual(capabilities_for(role), frozenset())

    def test_no_role_can_manage_users_or_read_the_audit_log_yet(self):
        for capability in [
            Capability.MANAGE_USERS,
            Capability.VIEW_AUDIT_LOG,
            Capability.VIEW_ANALYTICS,
            Capability.VIEW_SYSTEM_HEALTH,
            Capability.CONFIGURE_QUEUE,
        ]:
            with self.subTest(capability=capability):
                holders = [
                    role for role in ROLE_CAPABILITIES if role_has(role, capability)
                ]
                self.assertEqual(holders, [])


class PermissionClassTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def _check(self, permission, user, view=None):
        request = self.factory.get("/api/stub/")
        if user is not None:
            force_authenticate(request, user=user)
            request.user = user
        else:
            from django.contrib.auth.models import AnonymousUser

            request.user = AnonymousUser()
        return permission.has_permission(request, view or object())

    def _user(self, role, **kwargs):
        return StaffUser.objects.create_user(
            username=f"user_{role}", password="irrelevant", role=role, **kwargs
        )

    def test_anonymous_users_are_refused(self):
        self.assertFalse(self._check(IsStaff(), None))

    def test_deactivated_accounts_are_refused(self):
        user = self._user(Role.CLINICIAN, is_active=False)
        self.assertFalse(self._check(IsStaff(), user))

    def test_an_account_with_an_unrecognised_role_is_refused(self):
        user = self._user(Role.CLINICIAN)
        user.role = "hospital_director"
        self.assertFalse(self._check(IsStaff(), user))

    def test_a_view_that_declares_no_capability_is_refused(self):
        """An oversight in a view must fail closed."""

        class ViewWithoutCapability:
            pass

        user = self._user(Role.CLINICIAN)
        self.assertFalse(
            self._check(HasCapability(), user, ViewWithoutCapability())
        )

    def test_capability_is_enforced_against_the_declaring_view(self):
        class VitalsView:
            required_capability = Capability.COMPLETE_VITALS

        self.assertTrue(
            self._check(HasCapability(), self._user(Role.NURSE_VITALS), VitalsView())
        )
        self.assertFalse(
            self._check(HasCapability(), self._user(Role.PHARMACIST), VitalsView())
        )

    def test_requires_factory_builds_a_working_permission(self):
        permission = requires(Capability.RECORD_PHARMACY_OUTCOME)()

        self.assertTrue(self._check(permission, self._user(Role.PHARMACIST)))
        self.assertFalse(self._check(permission, self._user(Role.CLINICIAN)))

    def test_may_assign_priority_admits_only_clinical_roles(self):
        permission = MayAssignPriority()
        expected = {
            Role.REGISTRATION_CLERK: False,
            Role.NURSE_VITALS: True,
            Role.CLINICIAN: True,
            Role.PHARMACIST: False,
            Role.SUPERVISOR: False,
            Role.IT_SUPPORT: False,
        }

        for role, allowed in expected.items():
            with self.subTest(role=role):
                self.assertEqual(self._check(permission, self._user(role)), allowed)
