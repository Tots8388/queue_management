"""
Seed the prototype with fictional data.

The spec requires that all prototype records be fictional. Nothing here is
derived from a real patient, a real member of staff or a real phone number, and
nothing in this command should ever be pointed at a database holding real data —
``--reset`` refuses to run outside DEBUG for that reason.

    python manage.py seed_demo
    python manage.py seed_demo --reset       # clear fictional data first
    python manage.py seed_demo --visits 40
"""

import random
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from queueapp.models import (
    NotificationContact,
    PharmacyOutcome,
    PriorityChange,
    Role,
    ServiceCounter,
    StageEvent,
    StaffUser,
    TokenSequence,
    Visit,
)

# Fictional staff. Names are invented; the password is a well-known development
# placeholder and the command refuses to create these accounts in production.
DEMO_PASSWORD = "prototype-demo-only"

DEMO_STAFF = [
    ("reception1", "Achieng", "Odhiambo", Role.REGISTRATION_CLERK),
    ("nurse1", "Wanjiru", "Kamau", Role.NURSE_VITALS),
    ("clinician1", "Kiprop", "Cheruiyot", Role.CLINICIAN),
    ("pharmacy1", "Nasirumbi", "Wekesa", Role.PHARMACIST),
    ("supervisor1", "Atieno", "Ochieng", Role.SUPERVISOR),
    ("itsupport1", "Mutiso", "Kilonzo", Role.IT_SUPPORT),
]

DEMO_COUNTERS = [
    ("Reception Desk 1", "registration"),
    ("Reception Desk 2", "registration"),
    ("Vitals Room", "vitals"),
    ("Consultation Room 1", "consultation"),
    ("Consultation Room 2", "consultation"),
    ("Pharmacy Window 1", "pharmacy"),
]

# Non-sensitive categories only — no diagnoses, no symptoms.
PRIORITY_REASONS = [
    "Clinical assessment at triage",
    "Referred urgently by clinician",
    "Escalated during vital signs",
]

# Typical minutes spent at each stage, used to lay out plausible history so the
# rolling-median wait range (Phase 6) has something to work with.
STAGE_MINUTES = {
    "registration": (2, 6),
    "vitals": (4, 10),
    "consultation": (8, 20),
    "pharmacy": (3, 9),
}

STAGE_ORDER = ["registration", "vitals", "consultation", "pharmacy", "complete"]


class Command(BaseCommand):
    help = "Populate the database with fictional prototype data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--visits", type=int, default=24, help="How many fictional visits to create."
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing visits, counters and demo staff first.",
        )
        parser.add_argument(
            "--seed", type=int, default=20260730, help="Random seed, for repeatable data."
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "seed_demo refuses to run with DEBUG off. It writes fictional "
                "records and must never touch a real deployment."
            )

        random.seed(options["seed"])

        with transaction.atomic():
            if options["reset"]:
                self._reset()
            counters = self._create_counters()
            self._create_staff(counters)
            self._create_visits(options["visits"], counters)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSeeded {Visit.objects.count()} fictional visits and "
                f"{StaffUser.objects.count()} staff accounts."
            )
        )
        self.stdout.write(
            f"Sign in as any of: {', '.join(u for u, *_ in DEMO_STAFF)} "
            f"(password: {DEMO_PASSWORD})"
        )
        self.stdout.write(
            self.style.WARNING("All records are fictional. Not for clinical use.")
        )

    def _reset(self) -> None:
        self.stdout.write("Clearing existing fictional data...")
        # Stage events, priority changes, pharmacy outcomes and notification
        # contacts all cascade from Visit.
        Visit.objects.all().delete()
        TokenSequence.objects.all().delete()
        StaffUser.objects.filter(
            username__in=[username for username, *_ in DEMO_STAFF]
        ).delete()
        ServiceCounter.objects.all().delete()

    def _create_counters(self) -> dict[str, list[ServiceCounter]]:
        by_stage: dict[str, list[ServiceCounter]] = {}
        for name, stage in DEMO_COUNTERS:
            counter, created = ServiceCounter.objects.get_or_create(
                name=name, defaults={"stage": stage}
            )
            by_stage.setdefault(stage, []).append(counter)
            if created:
                self.stdout.write(f"  counter: {name}")
        return by_stage

    def _create_staff(self, counters: dict[str, list[ServiceCounter]]) -> None:
        stage_for_role = {
            Role.REGISTRATION_CLERK: "registration",
            Role.NURSE_VITALS: "vitals",
            Role.CLINICIAN: "consultation",
            Role.PHARMACIST: "pharmacy",
        }
        for username, first_name, last_name, role in DEMO_STAFF:
            stage = stage_for_role.get(role)
            user, created = StaffUser.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "role": role,
                    "default_counter": counters.get(stage, [None])[0] if stage else None,
                    # Only IT/Support gets the Django admin; the others work
                    # entirely through their role dashboard.
                    "is_staff": role == Role.IT_SUPPORT,
                },
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save(update_fields=["password"])
                self.stdout.write(f"  staff:   {username} ({role.label})")

    def _create_visits(
        self, count: int, counters: dict[str, list[ServiceCounter]]
    ) -> None:
        """
        Lay out visits along the journey: some finished, some mid-flow, some
        still waiting — so every dashboard has something realistic to show and
        the wait-range calculation has completed services to draw a median from.
        """
        now = timezone.now()

        for index in range(count):
            # Check-ins spread backwards through the morning, oldest first.
            minutes_ago = (count - index) * random.randint(3, 7)
            check_in = now - timedelta(minutes=minutes_ago)

            visit = Visit.check_in(check_in_time=check_in)

            # Older visits have progressed further.
            progress = index / max(count - 1, 1)
            if progress < 0.35:
                target = "complete"
            elif progress < 0.55:
                target = "pharmacy"
            elif progress < 0.8:
                target = "consultation"
            else:
                target = "vitals"

            cursor = check_in
            for stage in STAGE_ORDER[: STAGE_ORDER.index(target)]:
                low, high = STAGE_MINUTES[stage]
                completed = cursor + timedelta(minutes=random.randint(low, high))
                StageEvent.objects.create(
                    visit=visit,
                    stage=stage,
                    entered_at=cursor,
                    completed_at=completed,
                    completed_by_role=self._role_for_stage(stage),
                )
                cursor = completed + timedelta(minutes=random.randint(1, 4))

            visit.current_stage = target
            if target == "complete":
                visit.stage_status = Visit.StageStatus.COMPLETE
                visit.closed_at = cursor
            else:
                # The stage they are now at has been entered but not finished.
                StageEvent.objects.create(
                    visit=visit, stage=target, entered_at=cursor
                )
                visit.stage_status = Visit.StageStatus.WAITING
                stage_counters = counters.get(target, [])
                if stage_counters:
                    visit.assigned_counter = random.choice(stage_counters)

            self._maybe_add_priority(visit)
            self._maybe_add_presence(visit)
            self._maybe_add_pharmacy(visit, cursor)
            self._maybe_add_contact(visit)

            visit.save()

        self.stdout.write(f"  visits:  {count}")

    @staticmethod
    def _role_for_stage(stage: str) -> str:
        return {
            "registration": Role.REGISTRATION_CLERK,
            "vitals": Role.NURSE_VITALS,
            "consultation": Role.CLINICIAN,
            "pharmacy": Role.PHARMACIST,
        }[stage]

    def _maybe_add_priority(self, visit: Visit) -> None:
        """A small minority are urgent, fewer still emergency — as in a clinic."""
        roll = random.random()
        if roll < 0.08:
            new_priority = Visit.Priority.EMERGENCY
        elif roll < 0.22:
            new_priority = Visit.Priority.URGENT
        else:
            return

        PriorityChange.objects.create(
            visit=visit,
            previous_priority=visit.priority,
            new_priority=new_priority,
            # Only clinical roles may set priority (FR3).
            changed_by_role=random.choice([Role.NURSE_VITALS, Role.CLINICIAN]),
            non_sensitive_reason=random.choice(PRIORITY_REASONS),
            timestamp=visit.check_in_time + timedelta(minutes=random.randint(1, 10)),
        )
        visit.priority = new_priority

    def _maybe_add_presence(self, visit: Visit) -> None:
        """Some patients step away or miss a call — the recovery path (FR9)."""
        if visit.current_stage == "complete":
            return
        roll = random.random()
        if roll < 0.08:
            visit.presence_status = Visit.Presence.TEMPORARILY_AWAY
        elif roll < 0.14:
            visit.presence_status = Visit.Presence.MISSED_TURN
        elif roll < 0.2:
            visit.presence_status = Visit.Presence.CALLED

    def _maybe_add_pharmacy(self, visit: Visit, cursor) -> None:
        if visit.current_stage not in {"pharmacy", "complete"}:
            return
        if visit.current_stage == "complete":
            state = PharmacyOutcome.State.ISSUED
        else:
            state = random.choice(
                [
                    PharmacyOutcome.State.READY,
                    PharmacyOutcome.State.READY,
                    # Medicine unavailable is an exceptional path the interface
                    # must handle, so the fixtures include it.
                    PharmacyOutcome.State.UNAVAILABLE,
                ]
            )
        PharmacyOutcome.objects.create(
            visit=visit,
            state=state,
            by_role=Role.PHARMACIST,
            timestamp=cursor,
        )

    def _maybe_add_contact(self, visit: Visit) -> None:
        """Fictional numbers only, in Kenya's reserved-for-drama 07xx range."""
        if random.random() > 0.3:
            return
        visit.notification_preference = "sms"
        NotificationContact.objects.create(
            visit=visit,
            phone_number=f"+2547{random.randint(10, 99)}000{random.randint(100, 999)}",
        )
