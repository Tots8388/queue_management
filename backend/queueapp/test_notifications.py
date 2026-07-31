"""
Phase 7 tests: the optional SMS channel.

The most important assertions here are the negative ones. SMS is optional, it
is the only component that reaches outside the LAN, and nothing clinical may
depend on it — so the tests care most about what happens when it is switched
off, misconfigured, or broken.
"""

from unittest.mock import patch

from django.db import transaction
from django.test import TestCase, override_settings

from .models import NotificationContact, PharmacyOutcome, Role, StaffUser, Visit
from .services import notifications, operations

NUMBER = "+254700000123"


def staff(role, username=None):
    return StaffUser.objects.create_user(
        username=username or f"sms_{role}", password="x", role=role
    )


class Recorder:
    """A provider that records instead of sending."""

    name = "recorder"

    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    def send(self, to: str, message: str) -> None:
        self.sent.append((to, message))


class ProviderSelectionTests(TestCase):
    def test_sms_is_disabled_by_default(self):
        """The clinic may run permanently without it; that is not an error."""
        self.assertIsInstance(
            notifications.get_provider(), notifications.DisabledProvider
        )

    @override_settings(SMS_ENABLED=True, SMS_PROVIDER="console")
    def test_a_configured_provider_is_selected(self):
        self.assertIsInstance(
            notifications.get_provider(), notifications.ConsoleProvider
        )

    @override_settings(SMS_ENABLED=True, SMS_PROVIDER="carrier-pigeon")
    def test_an_unknown_provider_degrades_to_disabled(self):
        self.assertIsInstance(
            notifications.get_provider(), notifications.DisabledProvider
        )

    @override_settings(SMS_ENABLED=True, SMS_PROVIDER="africastalking")
    def test_missing_credentials_degrade_to_disabled_rather_than_raising(self):
        """
        Losing an optional message is a nuisance. Failing a stage completion
        because an API key is missing would be a clinical problem.
        """
        with patch.dict("os.environ", {"SMS_API_KEY": "", "SMS_USERNAME": ""}):
            self.assertIsInstance(
                notifications.get_provider(), notifications.DisabledProvider
            )

    @override_settings(SMS_ENABLED=True, SMS_PROVIDER="twilio")
    def test_twilio_is_available_as_the_alternative(self):
        with patch.dict(
            "os.environ",
            {
                "SMS_API_KEY": "sid",
                "SMS_API_SECRET": "token",
                "SMS_SENDER_ID": "+10000000000",
            },
        ):
            self.assertIsInstance(
                notifications.get_provider(), notifications.TwilioProvider
            )


class MessageContentTests(TestCase):
    def test_a_stage_message_carries_the_token_and_destination_only(self):
        message = notifications.stage_message("T-041", "Consultation Room 2")

        self.assertIn("T-041", message)
        self.assertIn("Consultation Room 2", message)

    def test_messages_disclose_no_clinical_or_priority_detail(self):
        """
        A text sits in an inbox and crosses a gateway the Medical Center does
        not control, so it says as little as it can while staying useful.
        """
        messages = [
            notifications.stage_message("T-041", "Pharmacy"),
            notifications.ready_message("T-041"),
        ]

        for message in messages:
            with self.subTest(message=message):
                lowered = message.lower()
                for term in [
                    "emergency",
                    "urgent",
                    "priority",
                    "diagnosis",
                    "prescription",
                    "symptom",
                ]:
                    self.assertNotIn(term, lowered)


class DispatchTests(TestCase):
    def setUp(self):
        self.clerk = staff(Role.REGISTRATION_CLERK)
        self.recorder = Recorder()

    def _sms_visit(self) -> Visit:
        visit = operations.check_in(
            actor=self.clerk, notification_preference="sms", phone_number=NUMBER
        )
        return visit

    def test_a_patient_who_asked_for_sms_is_notified_on_a_stage_change(self):
        visit = self._sms_visit()

        # Dispatch is deferred to commit, which a TestCase never reaches on its
        # own — so run the queued callbacks explicitly.
        with patch.object(
            notifications, "get_provider", return_value=self.recorder
        ):
            with self.captureOnCommitCallbacks(execute=True):
                operations.complete_stage(visit, actor=self.clerk)

        self.assertEqual(len(self.recorder.sent), 1)
        to, message = self.recorder.sent[0]
        self.assertEqual(to, NUMBER)
        self.assertIn(visit.token, message)
        self.assertIn("Vital signs", message)

    def test_a_patient_on_the_screen_channel_is_not_texted(self):
        visit = operations.check_in(actor=self.clerk)

        with patch.object(
            notifications, "get_provider", return_value=self.recorder
        ):
            with self.captureOnCommitCallbacks(execute=True):
                operations.complete_stage(visit, actor=self.clerk)

        self.assertEqual(self.recorder.sent, [])

    def test_no_message_is_sent_when_there_is_no_contact_on_file(self):
        visit = operations.check_in(actor=self.clerk)
        visit.notification_preference = "sms"
        visit.save()

        with patch.object(
            notifications, "get_provider", return_value=self.recorder
        ):
            with self.captureOnCommitCallbacks(execute=True):
                operations.complete_stage(visit, actor=self.clerk)

        self.assertEqual(self.recorder.sent, [])

    def test_medicine_ready_notifies_the_patient(self):
        visit = self._sms_visit()
        visit.current_stage = "pharmacy"
        visit.save()

        with patch.object(
            notifications, "get_provider", return_value=self.recorder
        ):
            with self.captureOnCommitCallbacks(execute=True):
                operations.record_pharmacy_outcome(
                    visit,
                    state=PharmacyOutcome.State.READY,
                    actor=staff(Role.PHARMACIST),
                )

        self.assertEqual(len(self.recorder.sent), 1)
        self.assertIn("ready", self.recorder.sent[0][1].lower())

    def test_completing_a_visit_sends_no_message(self):
        """Nobody needs a text telling them to go to "Complete"."""
        visit = self._sms_visit()
        visit.current_stage = "pharmacy"
        visit.save()

        with patch.object(
            notifications, "get_provider", return_value=self.recorder
        ):
            with self.captureOnCommitCallbacks(execute=True):
                operations.record_pharmacy_outcome(
                    visit,
                    state=PharmacyOutcome.State.ISSUED,
                    actor=staff(Role.PHARMACIST, username="sms_pharm2"),
                )

        self.assertEqual(self.recorder.sent, [])


class ResilienceTests(TestCase):
    """Nothing clinical may depend on the optional channel."""

    def setUp(self):
        self.clerk = staff(Role.REGISTRATION_CLERK)

    def test_the_core_flow_is_unaffected_with_sms_switched_off(self):
        visit = operations.check_in(
            actor=self.clerk, notification_preference="sms", phone_number=NUMBER
        )

        for _ in range(3):
            visit = operations.complete_stage(visit, actor=self.clerk)

        self.assertEqual(visit.current_stage, "pharmacy")
        self.assertEqual(visit.stage_events.count(), 4)

    def test_a_gateway_failure_does_not_break_the_stage_completion(self):
        class BrokenProvider:
            name = "broken"

            def send(self, to, message):
                raise RuntimeError("gateway unreachable")

        visit = operations.check_in(
            actor=self.clerk, notification_preference="sms", phone_number=NUMBER
        )

        with patch.object(
            notifications, "get_provider", return_value=BrokenProvider()
        ):
            with self.captureOnCommitCallbacks(execute=True):
                visit = operations.complete_stage(visit, actor=self.clerk)

        self.assertEqual(visit.current_stage, "vitals")

    def test_a_message_is_not_sent_for_a_change_that_rolls_back(self):
        """
        A patient walking to a room they were never sent to would be worse
        than no message at all, so dispatch waits for the commit.
        """
        recorder = Recorder()
        visit = operations.check_in(
            actor=self.clerk, notification_preference="sms", phone_number=NUMBER
        )

        with patch.object(notifications, "get_provider", return_value=recorder):
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                try:
                    with transaction.atomic():
                        operations.complete_stage(visit, actor=self.clerk)
                        raise RuntimeError("something went wrong afterwards")
                except RuntimeError:
                    pass

        # The rolled-back block queued nothing that survived it.
        self.assertEqual(callbacks, [])
        self.assertEqual(recorder.sent, [])


class ContactPrivacyTests(TestCase):
    def test_the_number_is_never_written_to_a_log_line(self):
        """The phone number is the one identifying value this system holds."""
        visit = Visit.check_in(notification_preference="sms")
        contact = NotificationContact.objects.create(
            visit=visit, phone_number=NUMBER
        )

        with self.assertLogs("queueapp.services.notifications", level="INFO") as logs:
            notifications.DisabledProvider().send(contact.phone_number, "hello")

        self.assertNotIn(NUMBER, "\n".join(logs.output))
