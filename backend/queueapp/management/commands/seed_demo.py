"""
Seed the prototype with the fictional staff accounts and service counters.

No patients are created. Every visit in the database is one somebody checked in
through the interface, so what a dashboard shows is always real use of the
system rather than fabricated history.

The spec requires that all prototype records be fictional. The staff names here
are invented, the password is a well-known development placeholder, and nothing
in this command should ever be pointed at a database holding real data —
it refuses to run outside DEBUG for that reason.

    python manage.py seed_demo
    python manage.py seed_demo --reset          # clear seeded staff and counters
    python manage.py seed_demo --clear-visits   # delete every patient record
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from queueapp.models import (
    Role,
    ServiceCounter,
    StaffUser,
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


class Command(BaseCommand):
    help = "Create the fictional staff accounts and service counters. No patients."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete the seeded staff and counters first.",
        )
        parser.add_argument(
            "--clear-visits",
            action="store_true",
            help=(
                "Delete every visit and reset the token sequence, so the queue "
                "starts empty. Implied by --reset."
            ),
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "seed_demo refuses to run with DEBUG off. It writes fictional "
                "records and must never touch a real deployment."
            )

        with transaction.atomic():
            if options["reset"] or options["clear_visits"]:
                self._clear_visits()
            if options["reset"]:
                self._reset()
            counters = self._create_counters()
            self._create_staff(counters)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSeeded {StaffUser.objects.count()} staff accounts and "
                f"{ServiceCounter.objects.count()} counters. "
                f"Visits in the database: {Visit.objects.count()}."
            )
        )
        self.stdout.write(
            f"Sign in as any of: {', '.join(u for u, *_ in DEMO_STAFF)} "
            f"(password: {DEMO_PASSWORD})"
        )
        self.stdout.write(
            "Patients are not seeded - check them in at /staff/reception."
        )
        self.stdout.write(
            self.style.WARNING("All records are fictional. Not for clinical use.")
        )

    def _clear_visits(self) -> None:
        """
        Remove every patient record.

        Stage events, priority changes, pharmacy outcomes and notification
        contacts all cascade from Visit; the audit log deliberately does not,
        because its entries outlive the visit they describe.
        """
        self.stdout.write("Clearing visits...")
        Visit.objects.all().delete()

    def _reset(self) -> None:
        self.stdout.write("Clearing seeded staff and counters...")
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
