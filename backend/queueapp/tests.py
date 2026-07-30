"""
Phase 0 tests: the scaffold is wired up and the shared contracts load.
"""

from django.test import TestCase
from django.urls import reverse

from . import contracts


class HealthEndpointTests(TestCase):
    def test_health_reports_ok_and_needs_no_authentication(self):
        """Staff must be able to see whether the server is up before login."""
        response = self.client.get(reverse("queueapp:health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertTrue(response.json()["database"]["connected"])


class ContractsTests(TestCase):
    def test_endpoint_serves_the_shared_vocabulary(self):
        response = self.client.get(reverse("queueapp:contracts"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("roles", response.json())

    def test_six_roles_exist_as_specified(self):
        self.assertEqual(
            contracts.keys("roles"),
            [
                "registration_clerk",
                "nurse_vitals",
                "clinician",
                "pharmacist",
                "supervisor",
                "it_support",
            ],
        )

    def test_only_clinical_roles_may_assign_priority(self):
        """Spec FR3: reception and pharmacy cannot set emergency/urgent."""
        self.assertEqual(
            contracts.roles_that_may_assign_priority(),
            ["nurse_vitals", "clinician"],
        )

    def test_stages_cover_the_full_outpatient_journey(self):
        self.assertEqual(
            contracts.keys("stages"),
            ["registration", "vitals", "consultation", "pharmacy", "complete"],
        )

    def test_public_display_exposes_token_and_destination_only(self):
        """Spec FR8: no names, priority category or medical detail in public."""
        self.assertEqual(
            contracts.public_display_allowed_fields(), ["token", "destination"]
        )
