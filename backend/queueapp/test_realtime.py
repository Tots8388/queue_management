"""
Phase 4 tests: real-time propagation across the patient, staff and public
channels.

These run against the ASGI application through ``WebsocketCommunicator``, so
they exercise routing, authentication and the consumers together rather than
the consumer classes in isolation.
"""

from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase
from rest_framework_simplejwt.tokens import AccessToken

from config.asgi import application

from .models import Role, ServiceCounter, StaffUser, Visit
from .services import broadcast, operations


@database_sync_to_async
def make_staff(role, username=None):
    return StaffUser.objects.create_user(
        username=username or f"ws_{role}", password="x", role=role
    )


@database_sync_to_async
def make_visit(**fields):
    stage = fields.pop("current_stage", None)
    visit = Visit.check_in(**fields)
    if stage:
        visit.current_stage = stage
        visit.save()
    return visit


@database_sync_to_async
def access_token_for(user) -> str:
    return str(AccessToken.for_user(user))


@database_sync_to_async
def run(function, *args, **kwargs):
    return function(*args, **kwargs)


class PublicDisplayChannelTests(TransactionTestCase):
    """Spec FR8 — the board, and what it must never carry."""

    async def test_a_screen_receives_the_board_on_connect(self):
        """
        A display switched on mid-morning must show the current board at once,
        not wait for the next patient to be called.
        """
        communicator = WebsocketCommunicator(application, "/ws/display/")
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        message = await communicator.receive_json_from()
        self.assertEqual(message["channel"], "display")
        self.assertEqual(message["rows"], [])

        await communicator.disconnect()

    async def test_calling_a_patient_reaches_the_board(self):
        counter = await database_sync_to_async(ServiceCounter.objects.create)(
            name="Consultation Room 2", stage="consultation"
        )
        nurse = await make_staff(Role.NURSE_VITALS)
        visit = await make_visit(current_stage="consultation")
        visit.assigned_counter = counter
        await database_sync_to_async(visit.save)()

        communicator = WebsocketCommunicator(application, "/ws/display/")
        await communicator.connect()
        await communicator.receive_json_from()  # initial state

        await run(
            operations.set_presence,
            visit,
            presence=Visit.Presence.CALLED,
            actor=nurse,
        )

        message = await communicator.receive_json_from()
        self.assertEqual(len(message["rows"]), 1)
        self.assertEqual(message["rows"][0]["token"], visit.token)
        self.assertEqual(message["rows"][0]["destination"], "Consultation Room 2")

        await communicator.disconnect()

    async def test_the_board_payload_carries_no_priority_or_identity(self):
        nurse = await make_staff(Role.NURSE_VITALS, username="ws_nurse_priv")
        visit = await make_visit(current_stage="consultation")

        await run(
            operations.set_priority,
            visit,
            priority=Visit.Priority.EMERGENCY,
            actor=nurse,
            reason="Clinical assessment at triage",
        )
        await run(
            operations.set_presence,
            visit,
            presence=Visit.Presence.CALLED,
            actor=nurse,
        )

        communicator = WebsocketCommunicator(application, "/ws/display/")
        await communicator.connect()
        message = await communicator.receive_json_from()

        self.assertEqual(
            set(message["rows"][0]), {"token", "stage", "destination", "called"}
        )
        body = str(message).lower()
        for term in ["emergency", "urgent", "priority", "reason"]:
            with self.subTest(term=term):
                self.assertNotIn(term, body)

        await communicator.disconnect()


class PatientChannelTests(TransactionTestCase):
    """Spec FR7."""

    async def test_a_patient_receives_their_status_on_connect(self):
        visit = await make_visit(current_stage="vitals")

        communicator = WebsocketCommunicator(
            application, f"/ws/patient/{visit.token}/"
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        message = await communicator.receive_json_from()
        self.assertEqual(message["channel"], "patient")
        self.assertEqual(message["token"], visit.token)
        self.assertEqual(message["stage_label"], "Vital signs")

        await communicator.disconnect()

    async def test_a_stage_change_reaches_the_patient(self):
        clerk = await make_staff(Role.REGISTRATION_CLERK)
        visit = await make_visit()

        communicator = WebsocketCommunicator(
            application, f"/ws/patient/{visit.token}/"
        )
        await communicator.connect()
        await communicator.receive_json_from()

        await run(operations.complete_stage, visit, actor=clerk)

        message = await communicator.receive_json_from()
        self.assertEqual(message["current_stage"], "vitals")

        await communicator.disconnect()

    async def test_the_patient_channel_never_carries_a_priority_category(self):
        nurse = await make_staff(Role.NURSE_VITALS, username="ws_nurse_patient")
        visit = await make_visit(current_stage="consultation")

        await run(
            operations.set_priority,
            visit,
            priority=Visit.Priority.EMERGENCY,
            actor=nurse,
            reason="Clinical assessment at triage",
        )

        communicator = WebsocketCommunicator(
            application, f"/ws/patient/{visit.token}/"
        )
        await communicator.connect()
        message = await communicator.receive_json_from()

        body = str(message).lower()
        self.assertNotIn("emergency", body)
        self.assertNotIn("priority", body)

        await communicator.disconnect()

    async def test_an_unknown_token_is_closed(self):
        communicator = WebsocketCommunicator(application, "/ws/patient/T-999/")
        await communicator.connect()

        message = await communicator.receive_output()
        self.assertEqual(message["type"], "websocket.close")
        self.assertEqual(message["code"], 4404)

        await communicator.disconnect()

    async def test_a_client_can_ask_for_a_resync(self):
        """After a sleep/wake a client cannot tell whether it missed anything."""
        visit = await make_visit()

        communicator = WebsocketCommunicator(
            application, f"/ws/patient/{visit.token}/"
        )
        await communicator.connect()
        await communicator.receive_json_from()

        await communicator.send_json_to({"action": "resync"})
        message = await communicator.receive_json_from()

        self.assertEqual(message["token"], visit.token)

        await communicator.disconnect()


class StaffChannelTests(TransactionTestCase):
    """A socket must not be a way around a permission."""

    async def test_a_nurse_can_watch_the_vitals_queue(self):
        nurse = await make_staff(Role.NURSE_VITALS)
        token = await access_token_for(nurse)

        communicator = WebsocketCommunicator(
            application, f"/ws/staff/vitals/?token={token}"
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        message = await communicator.receive_json_from()
        self.assertEqual(message["channel"], "staff")
        self.assertEqual(message["stage"], "vitals")

        await communicator.disconnect()

    async def test_an_unauthenticated_connection_is_refused(self):
        communicator = WebsocketCommunicator(application, "/ws/staff/vitals/")
        connected, code = await communicator.connect()

        self.assertFalse(connected)
        self.assertEqual(code, 4403)

    async def test_an_invalid_token_is_refused(self):
        communicator = WebsocketCommunicator(
            application, "/ws/staff/vitals/?token=not-a-real-token"
        )
        connected, code = await communicator.connect()

        self.assertFalse(connected)
        self.assertEqual(code, 4403)

    async def test_an_oversight_role_is_refused_while_g4_is_pending(self):
        supervisor = await make_staff(Role.SUPERVISOR)
        token = await access_token_for(supervisor)

        communicator = WebsocketCommunicator(
            application, f"/ws/staff/vitals/?token={token}"
        )
        connected, code = await communicator.connect()

        self.assertFalse(connected)
        self.assertEqual(code, 4403)

    async def test_a_deactivated_account_is_refused(self):
        nurse = await make_staff(Role.NURSE_VITALS, username="ws_nurse_off")
        token = await access_token_for(nurse)
        nurse.is_active = False
        await database_sync_to_async(nurse.save)()

        communicator = WebsocketCommunicator(
            application, f"/ws/staff/vitals/?token={token}"
        )
        connected, code = await communicator.connect()

        self.assertFalse(connected)
        self.assertEqual(code, 4403)

    async def test_a_check_in_reaches_the_reception_dashboard(self):
        clerk = await make_staff(Role.REGISTRATION_CLERK)
        token = await access_token_for(clerk)

        communicator = WebsocketCommunicator(
            application, f"/ws/staff/registration/?token={token}"
        )
        await communicator.connect()
        first = await communicator.receive_json_from()
        self.assertEqual(first["summary"]["waiting"], 0)

        await run(operations.check_in, actor=clerk)

        message = await communicator.receive_json_from()
        self.assertEqual(len(message["visits"]), 1)
        self.assertEqual(message["summary"]["waiting"], 1)

        await communicator.disconnect()

    async def test_a_transfer_updates_both_stages(self):
        """
        The stage left must stop showing the patient and the stage joined must
        start, or two dashboards disagree about where someone is.
        """
        clerk = await make_staff(Role.REGISTRATION_CLERK)
        nurse = await make_staff(Role.NURSE_VITALS)
        clerk_token = await access_token_for(clerk)
        nurse_token = await access_token_for(nurse)

        visit = await run(operations.check_in, actor=clerk)

        reception = WebsocketCommunicator(
            application, f"/ws/staff/registration/?token={clerk_token}"
        )
        vitals = WebsocketCommunicator(
            application, f"/ws/staff/vitals/?token={nurse_token}"
        )
        await reception.connect()
        await vitals.connect()
        await reception.receive_json_from()
        await vitals.receive_json_from()

        await run(operations.complete_stage, visit, actor=clerk)

        reception_state = await reception.receive_json_from()
        vitals_state = await vitals.receive_json_from()

        self.assertEqual(reception_state["visits"], [])
        self.assertEqual(len(vitals_state["visits"]), 1)
        self.assertEqual(vitals_state["visits"][0]["token"], visit.token)

        await reception.disconnect()
        await vitals.disconnect()

    async def test_the_staff_channel_does_show_priority(self):
        """
        The counterpart to the public-channel rule: priority tags belong on
        staff screens, and only there.
        """
        nurse = await make_staff(Role.NURSE_VITALS, username="ws_nurse_prio")
        token = await access_token_for(nurse)
        visit = await make_visit(current_stage="vitals")

        await run(
            operations.set_priority,
            visit,
            priority=Visit.Priority.URGENT,
            actor=nurse,
            reason="Escalated during vital signs",
        )

        communicator = WebsocketCommunicator(
            application, f"/ws/staff/vitals/?token={token}"
        )
        await communicator.connect()
        message = await communicator.receive_json_from()

        self.assertEqual(message["visits"][0]["priority"], "urgent")

        await communicator.disconnect()


class BroadcastResilienceTests(TransactionTestCase):
    async def test_a_failed_broadcast_does_not_break_the_queue_operation(self):
        """
        The authoritative state is in the database. A real-time update failing
        must never roll back the clinical action that triggered it.
        """
        clerk = await make_staff(Role.REGISTRATION_CLERK)

        class BrokenLayer:
            async def group_send(self, group, message):
                raise RuntimeError("channel layer unavailable")

        # Patch the layer, not the send helper: the point is to exercise the
        # protection inside _send, not to replace it.
        original = broadcast.get_channel_layer
        broadcast.get_channel_layer = lambda: BrokenLayer()
        try:
            visit = await run(operations.check_in, actor=clerk)
        finally:
            broadcast.get_channel_layer = original

        self.assertIsNotNone(visit.pk)
        exists = await database_sync_to_async(
            Visit.objects.filter(token=visit.token).exists
        )()
        self.assertTrue(exists)
