"""
Phase 2 tests: staff sign-in, sign-out and identity.
"""

from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Role, ServiceCounter, StaffUser

PASSWORD = "correct-horse-battery-staple"


class LoginTests(APITestCase):
    def setUp(self):
        self.counter = ServiceCounter.objects.create(
            name="Vitals Room", stage="vitals"
        )
        self.user = StaffUser.objects.create_user(
            username="nurse1",
            password=PASSWORD,
            role=Role.NURSE_VITALS,
            default_counter=self.counter,
        )
        self.url = reverse("queueapp:login")

    def test_valid_credentials_return_tokens_and_the_user(self):
        response = self.client.post(
            self.url, {"username": "nurse1", "password": PASSWORD}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["role"], Role.NURSE_VITALS)
        self.assertEqual(response.data["user"]["default_counter"]["name"], "Vitals Room")

    def test_the_response_carries_the_role_capabilities(self):
        response = self.client.post(
            self.url, {"username": "nurse1", "password": PASSWORD}
        )

        capabilities = response.data["user"]["capabilities"]
        self.assertIn("complete_vitals", capabilities)
        self.assertIn("assign_priority", capabilities)
        self.assertNotIn("record_pharmacy_outcome", capabilities)

    def test_the_response_names_the_dashboard_for_this_role(self):
        response = self.client.post(
            self.url, {"username": "nurse1", "password": PASSWORD}
        )
        self.assertEqual(response.data["user"]["dashboard"], "/staff/vitals")

    def test_oversight_roles_have_no_dashboard_while_g4_is_pending(self):
        for role in [Role.SUPERVISOR, Role.IT_SUPPORT]:
            with self.subTest(role=role):
                StaffUser.objects.create_user(
                    username=f"oversight_{role}", password=PASSWORD, role=role
                )
                response = self.client.post(
                    self.url, {"username": f"oversight_{role}", "password": PASSWORD}
                )

                self.assertEqual(response.status_code, 200)
                self.assertIsNone(response.data["user"]["dashboard"])
                self.assertEqual(response.data["user"]["capabilities"], [])

    def test_the_response_never_carries_the_password(self):
        response = self.client.post(
            self.url, {"username": "nurse1", "password": PASSWORD}
        )

        self.assertNotIn("password", response.data["user"])
        self.assertNotIn(PASSWORD, str(response.data))

    def test_a_wrong_password_is_refused(self):
        response = self.client.post(
            self.url, {"username": "nurse1", "password": "wrong"}
        )
        self.assertEqual(response.status_code, 401)

    def test_an_unknown_user_and_a_wrong_password_are_indistinguishable(self):
        """The endpoint must not reveal who works here."""
        unknown = self.client.post(
            self.url, {"username": "nobody", "password": "wrong"}
        )
        wrong = self.client.post(
            self.url, {"username": "nurse1", "password": "wrong"}
        )

        self.assertEqual(unknown.status_code, wrong.status_code)
        self.assertEqual(unknown.data["detail"], wrong.data["detail"])

    def test_a_deactivated_account_cannot_sign_in(self):
        self.user.is_active = False
        self.user.save()

        response = self.client.post(
            self.url, {"username": "nurse1", "password": PASSWORD}
        )
        self.assertEqual(response.status_code, 401)

    def test_missing_fields_are_rejected(self):
        self.assertEqual(self.client.post(self.url, {}).status_code, 400)


class CurrentUserTests(APITestCase):
    def setUp(self):
        self.user = StaffUser.objects.create_user(
            username="clinician1", password=PASSWORD, role=Role.CLINICIAN
        )
        self.url = reverse("queueapp:current-user")

    def test_requires_authentication(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_returns_the_signed_in_user(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "clinician1")
        self.assertEqual(response.data["role_label"], "Clinician")


class LogoutTests(APITestCase):
    def setUp(self):
        self.user = StaffUser.objects.create_user(
            username="pharmacy1", password=PASSWORD, role=Role.PHARMACIST
        )
        self.login_url = reverse("queueapp:login")
        self.logout_url = reverse("queueapp:logout")
        self.refresh_url = reverse("queueapp:token-refresh")

    def _sign_in(self) -> dict:
        return self.client.post(
            self.login_url, {"username": "pharmacy1", "password": PASSWORD}
        ).data

    def test_a_revoked_refresh_token_cannot_be_used_again(self):
        """
        Terminals are shared between shifts, so signing out has to end the
        session on the server, not just in the browser.
        """
        tokens = self._sign_in()
        self.client.force_authenticate(self.user)

        logout = self.client.post(self.logout_url, {"refresh": tokens["refresh"]})
        self.assertEqual(logout.status_code, 205)

        self.client.force_authenticate(None)
        reused = self.client.post(self.refresh_url, {"refresh": tokens["refresh"]})
        self.assertEqual(reused.status_code, 401)

    def test_logging_out_twice_is_not_an_error(self):
        """A frontend must never be tempted to keep a token on a shared machine."""
        tokens = self._sign_in()
        self.client.force_authenticate(self.user)

        self.client.post(self.logout_url, {"refresh": tokens["refresh"]})
        second = self.client.post(self.logout_url, {"refresh": tokens["refresh"]})

        self.assertEqual(second.status_code, 205)

    def test_logout_requires_authentication(self):
        tokens = self._sign_in()
        response = self.client.post(self.logout_url, {"refresh": tokens["refresh"]})
        self.assertEqual(response.status_code, 401)


class TokenRotationTests(APITestCase):
    def setUp(self):
        StaffUser.objects.create_user(
            username="reception1", password=PASSWORD, role=Role.REGISTRATION_CLERK
        )
        self.login_url = reverse("queueapp:login")
        self.refresh_url = reverse("queueapp:token-refresh")

    def test_refreshing_retires_the_previous_refresh_token(self):
        tokens = self.client.post(
            self.login_url, {"username": "reception1", "password": PASSWORD}
        ).data

        refreshed = self.client.post(self.refresh_url, {"refresh": tokens["refresh"]})
        self.assertEqual(refreshed.status_code, 200)
        self.assertNotEqual(refreshed.data["refresh"], tokens["refresh"])

        reused = self.client.post(self.refresh_url, {"refresh": tokens["refresh"]})
        self.assertEqual(reused.status_code, 401)
