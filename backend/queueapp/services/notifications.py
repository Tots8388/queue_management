"""
Telling patients their visit has moved on.

Three channels, in the order the spec puts them:

* **Screen** — the patient status view. Core, always available.
* **Printed token** — the slip from reception. Core, works with no power at
  the patient's end and no phone at all.
* **SMS / phone** — optional, off by default.

SMS is the only part of this system that reaches outside the Medical Center's
LAN. Everything else — queue, dashboards, display board, patient view — works
with the internet unplugged, which is the point of the on-premise deployment
and of the offline fallback. So SMS is built to be *absent*: disabled by
default, dispatched off the request path, and incapable of failing a clinical
action.

What a message may contain is deliberately thin. It goes through a third-party
gateway and sits in a phone's inbox on a bus, so it carries the anonymous
token, the destination and nothing else. No name, no stage history, no
diagnosis, no medicine.
"""

from __future__ import annotations

import logging
import threading
from typing import Protocol

from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)

SENDER_NAME = "Kabarak Medical Center"


class SmsProvider(Protocol):
    """A gateway that can deliver a short text message."""

    name: str

    def send(self, to: str, message: str) -> None: ...


class DisabledProvider:
    """
    The default. Records the intent and sends nothing.

    Not an error state: the spec makes SMS optional, and the clinic may run
    permanently without it.
    """

    name = "disabled"

    def send(self, to: str, message: str) -> None:
        logger.info("SMS disabled; not sending to a patient contact.")


class ConsoleProvider:
    """
    Development and demonstration. Prints instead of sending.

    Logs the message but never the number — a phone number in a log file is
    the one identifying value this system holds.
    """

    name = "console"

    def send(self, to: str, message: str) -> None:
        logger.info("SMS (not sent — console provider): %s", message)


class AfricasTalkingProvider:
    """
    Africa's Talking — the default gateway proposed by the spec.

    Credentials come from the environment. A short timeout is deliberate: this
    call must never be the reason a member of staff is left waiting.
    """

    name = "africastalking"
    endpoint = "https://api.africastalking.com/version1/messaging"

    def __init__(self) -> None:
        import os

        self.api_key = os.environ.get("SMS_API_KEY", "")
        self.username = os.environ.get("SMS_USERNAME", "")
        self.sender_id = os.environ.get("SMS_SENDER_ID", "")

        if not (self.api_key and self.username):
            raise RuntimeError(
                "SMS_API_KEY and SMS_USERNAME are required for the Africa's "
                "Talking provider. Set them in the environment, never in the repo."
            )

    def send(self, to: str, message: str) -> None:
        import requests

        payload = {"username": self.username, "to": to, "message": message}
        if self.sender_id:
            payload["from"] = self.sender_id

        response = requests.post(
            self.endpoint,
            data=payload,
            headers={"apiKey": self.api_key, "Accept": "application/json"},
            timeout=settings.SMS_TIMEOUT_SECONDS,
        )
        response.raise_for_status()


class TwilioProvider:
    """The alternative named in the spec, behind the same interface."""

    name = "twilio"

    def __init__(self) -> None:
        import os

        self.account_sid = os.environ.get("SMS_API_KEY", "")
        self.auth_token = os.environ.get("SMS_API_SECRET", "")
        self.sender_id = os.environ.get("SMS_SENDER_ID", "")

        if not (self.account_sid and self.auth_token and self.sender_id):
            raise RuntimeError(
                "SMS_API_KEY, SMS_API_SECRET and SMS_SENDER_ID are required for "
                "the Twilio provider. Set them in the environment."
            )

    def send(self, to: str, message: str) -> None:
        import requests

        response = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json",
            data={"To": to, "From": self.sender_id, "Body": message},
            auth=(self.account_sid, self.auth_token),
            timeout=settings.SMS_TIMEOUT_SECONDS,
        )
        response.raise_for_status()


PROVIDERS = {
    "africastalking": AfricasTalkingProvider,
    "twilio": TwilioProvider,
    "console": ConsoleProvider,
    "disabled": DisabledProvider,
}


def get_provider() -> SmsProvider:
    """
    The configured gateway, or the disabled one.

    A misconfigured provider degrades to disabled rather than raising. Losing
    an optional text message is a nuisance; failing a stage completion because
    an API key is missing would be a clinical problem.
    """
    if not settings.SMS_ENABLED:
        return DisabledProvider()

    provider_class = PROVIDERS.get(settings.SMS_PROVIDER)
    if provider_class is None:
        logger.error(
            "Unknown SMS provider %r — SMS is disabled. Known providers: %s",
            settings.SMS_PROVIDER,
            ", ".join(sorted(PROVIDERS)),
        )
        return DisabledProvider()

    try:
        return provider_class()
    except Exception:  # noqa: BLE001
        logger.exception(
            "Could not configure the %s SMS provider — SMS is disabled for now.",
            settings.SMS_PROVIDER,
        )
        return DisabledProvider()


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


def stage_message(token: str, destination: str) -> str:
    """
    What a patient is told. Token and destination only.

    A message sits in an inbox and passes through a gateway the Medical Center
    does not control, so it says as little as possible while still being useful.
    """
    return (
        f"{SENDER_NAME}: token {token} — please go to {destination}. "
        "Do not reply to this message."
    )


def ready_message(token: str) -> str:
    return (
        f"{SENDER_NAME}: token {token} — your medicine is ready for collection "
        "at the pharmacy. Do not reply to this message."
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def _deliver(provider: SmsProvider, to: str, message: str) -> None:
    try:
        provider.send(to, message)
    except Exception:  # noqa: BLE001
        # Never log the number. Never re-raise: this runs detached from the
        # request, and an optional notification failing is not an incident.
        logger.exception("Could not deliver an SMS via %s.", provider.name)


def send_sms(to: str, message: str) -> None:
    """
    Dispatch a message without making anybody wait for it.

    A separate thread, not the request thread: a gateway having a slow morning
    must not make a staff dashboard feel broken. The trade-off is that there is
    no retry and an in-flight message is lost if the process restarts — which
    is acceptable precisely because this channel is optional. If SMS ever
    becomes something the clinic depends on, it needs a real task queue and a
    delivery record, not this.

    ``SMS_SYNCHRONOUS`` sends inline instead. Tests use it so dispatch is
    deterministic, and it is a reasonable choice for anyone who would rather
    see a gateway failure surface immediately than disappear into a thread.
    """
    provider = get_provider()
    if isinstance(provider, DisabledProvider):
        provider.send(to, message)
        return

    if settings.SMS_SYNCHRONOUS:
        _deliver(provider, to, message)
        return

    threading.Thread(
        target=_deliver, args=(provider, to, message), daemon=True
    ).start()


def notify_stage_change(visit) -> None:
    """
    Tell a patient their visit moved on, if they asked to be told by SMS.

    Called after a stage transition. Queued with ``on_commit`` so a message is
    never sent about a change that then rolls back — a patient walking to a
    room they were never sent to would be worse than no message.
    """
    if visit.notification_preference != "sms":
        return

    contact = getattr(visit, "notification_contact", None)
    if contact is None:
        return

    if visit.current_stage == "complete":
        return

    message = stage_message(visit.token, visit.public_destination)
    number = contact.phone_number

    transaction.on_commit(lambda: send_sms(number, message))


def notify_medicine_ready(visit) -> None:
    if visit.notification_preference != "sms":
        return

    contact = getattr(visit, "notification_contact", None)
    if contact is None:
        return

    message = ready_message(visit.token)
    number = contact.phone_number

    transaction.on_commit(lambda: send_sms(number, message))
