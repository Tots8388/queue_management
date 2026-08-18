"""
Queue data model.

Standing privacy constraint from the spec, which shapes every model below: the
queue database holds **no** names, diagnoses, symptoms or prescriptions. It
stores an internal ``visit_id`` and an anonymous, human-readable token. Mapping
a token back to a patient is done by authorised staff at a station, against
records kept outside this database. This system does not replace the medical
record. (Governance item G2.)

Vocabulary — roles, stages, statuses, priorities — comes from
``shared/contracts.json`` via ``contracts.py``, so the frontend and the database
cannot drift apart.
"""

import secrets
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.utils import timezone

from . import contracts

# ---------------------------------------------------------------------------
# Staff and roles
# ---------------------------------------------------------------------------


class Role(models.TextChoices):
    """
    The six least-privilege roles. Generated from the shared contracts so the
    set cannot diverge from what the frontend and permission classes use.
    """

    REGISTRATION_CLERK = "registration_clerk", "Registration Clerk"
    NURSE_VITALS = "nurse_vitals", "Nurse / Vitals"
    CLINICIAN = "clinician", "Clinician"
    PHARMACIST = "pharmacist", "Pharmacist"
    SUPERVISOR = "supervisor", "Supervisor / Management"
    IT_SUPPORT = "it_support", "IT / Support"


class StaffUser(AbstractUser):
    """
    A member of clinic staff.

    Patients never have an account here — a patient is identified only by the
    anonymous token on their visit. This model exists to attribute staff
    actions and to enforce least privilege.
    """

    role = models.CharField(
        max_length=32,
        choices=Role.choices,
        help_text="Determines which actions and dashboards this account can reach.",
    )
    # Which physical station this account is normally signed in at. Purely
    # operational — it pre-selects a queue, it is not a permission.
    default_counter = models.ForeignKey(
        "ServiceCounter",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="default_for_staff",
    )

    class Meta:
        verbose_name = "staff user"
        verbose_name_plural = "staff users"

    def __str__(self) -> str:
        return f"{self.get_username()} ({self.get_role_display()})"

    @property
    def is_clinical(self) -> bool:
        """Nurse/triage and clinicians. Reception and pharmacy are not."""
        return contracts.by_key("roles", self.role)["clinical"] if self.role else False

    @property
    def may_assign_priority(self) -> bool:
        """
        Spec FR3: only authorised clinical roles may set emergency or urgent.
        Enforced again in the permission classes — this property is convenience,
        not the security boundary.
        """
        return self.role in contracts.roles_that_may_assign_priority()


# ---------------------------------------------------------------------------
# Service points
# ---------------------------------------------------------------------------


class ServiceCounter(models.Model):
    """
    A physical service point — "Consultation Room 2", "Pharmacy Window 1".

    Gives the public display a concrete destination to show beside a token
    (spec FR8: "T-041 → Consultation") and lets a staff dashboard show one
    station's queue rather than the whole stage.
    """

    name = models.CharField(max_length=60, unique=True)
    stage = models.CharField(max_length=32, choices=contracts.choices("stages"))
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive counters keep their history but are not assigned new visits.",
    )

    class Meta:
        ordering = ["stage", "name"]

    def __str__(self) -> str:
        return self.name


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------


# A fixed Monday. Arbitrary, and it must never move: it is what every stored
# token_period was computed against.
TOKEN_EPOCH = date(2024, 1, 1)


def token_period_start(on_date=None):
    """
    The first day of the period a token issued on ``on_date`` belongs to.

    Tokens are reserved for a period rather than a day, and the period is what
    a token is unique within. Periods are counted from a fixed epoch rather
    than from the ISO week, so changing ``PERIOD_DAYS`` does not silently move
    every boundary in the past.
    """
    on_date = on_date or timezone.localdate()
    days = settings.TOKEN["PERIOD_DAYS"]
    elapsed = (on_date - TOKEN_EPOCH).days
    return TOKEN_EPOCH + timedelta(days=(elapsed // days) * days)


def generate_token() -> str:
    """
    A random token: one letter, then digits — ``K492``.

    Random rather than sequential on purpose. The waiting-room board shows
    every patient in the clinic, and a sequential token would publish the order
    people arrived in and how many have been through, neither of which is the
    board's business. ``secrets`` rather than ``random`` because this is the
    only thing standing between a stranger and a patient's queue position.

    Uniqueness is not this function's job — it can and will return a token
    already in use. ``Visit.check_in`` retries against the database constraint,
    which is the only check that cannot race.
    """
    config = settings.TOKEN
    letter = secrets.choice(config["ALPHABET"])
    number = secrets.randbelow(10 ** config["DIGITS"])
    return f"{letter}{number:0{config['DIGITS']}d}"


# ---------------------------------------------------------------------------
# Visits
# ---------------------------------------------------------------------------


class Visit(models.Model):
    """
    One outpatient visit, carrying a single anonymous token across all stages.

    Not per-stage tickets: the token issued at reception is the same token the
    pharmacy calls. That is what lets a patient follow their own progress
    without ever being named.
    """

    class StageStatus(models.TextChoices):
        WAITING = "waiting", "Waiting"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETE = "complete", "Complete"

    class Priority(models.TextChoices):
        EMERGENCY = "emergency", "Emergency"
        URGENT = "urgent", "Urgent"
        ROUTINE = "routine", "Routine"

    class Presence(models.TextChoices):
        WAITING = "waiting", "Waiting"
        CALLED = "called", "Called"
        RECALLED = "recalled", "Recalled"
        TEMPORARILY_AWAY = "temporarily_away", "Temporarily away"
        MISSED_TURN = "missed_turn", "Missed turn"
        RESUMED = "resumed", "Resumed"

    # The anonymous, patient-facing identifier. Unique within its period, not
    # for all time: tokens are deliberately reused once a period has passed, so
    # the pair is what must be unique.
    token = models.CharField(max_length=16, db_index=True)
    # The day this token was issued — the record of when, and never a lookup
    # key. `token_period` is the key, and the two are not the same thing: a
    # visit that runs past midnight keeps the period it was issued in.
    token_date = models.DateField(default=timezone.localdate, db_index=True)
    token_period = models.DateField(default=token_period_start, db_index=True)

    check_in_time = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="Recorded at registration. Never changes — it is the record.",
    )
    # The working sort key for routine ordering. It starts equal to
    # check_in_time and is only ever moved by a manual reorder, which requires a
    # logged reason. Keeping the two apart means a reorder cannot quietly
    # rewrite what time the patient actually arrived.
    queue_order_time = models.DateTimeField(default=timezone.now, db_index=True)

    current_stage = models.CharField(
        max_length=32,
        choices=contracts.choices("stages"),
        default="registration",
        db_index=True,
    )
    stage_status = models.CharField(
        max_length=16, choices=StageStatus.choices, default=StageStatus.WAITING
    )
    priority = models.CharField(
        max_length=16,
        choices=Priority.choices,
        default=Priority.ROUTINE,
        help_text="Set only by authorised clinical roles. Never shown publicly.",
    )
    presence_status = models.CharField(
        max_length=24, choices=Presence.choices, default=Presence.WAITING
    )
    notification_preference = models.CharField(
        max_length=16,
        choices=contracts.choices("notification_preferences"),
        default="screen",
    )

    assigned_counter = models.ForeignKey(
        ServiceCounter,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="visits",
        help_text="The destination shown beside this token on the public display.",
    )

    # Set when the clinician sends a patient for tests, so the return-after-tests
    # path (FR13) can restore them without losing prior stage history.
    awaiting_tests = models.BooleanField(default=False)

    last_updated = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["token_period", "token"], name="unique_token_per_period"
            ),
        ]
        indexes = [
            # The queue query: everyone waiting at one stage, most urgent first,
            # then in check-in order. Ordering is applied in the queue engine;
            # this index is what keeps it cheap at peak.
            models.Index(
                fields=[
                    "current_stage",
                    "stage_status",
                    "priority",
                    "queue_order_time",
                ],
                name="visit_queue_order_idx",
            ),
        ]
        ordering = ["check_in_time"]

    def __str__(self) -> str:
        return f"{self.token} ({self.get_current_stage_display()})"

    # Enough attempts that exhausting them means the period's pool is genuinely
    # full, not that two terminals collided. With 22,000 tokens and a clinic
    # holding a few hundred at once, a single collision is already unlikely.
    TOKEN_ATTEMPTS = 12

    @classmethod
    def check_in(cls, **fields) -> "Visit":
        """
        Issue a token and start a visit (spec FR1).

        Tokens are random, so two reception terminals can draw the same one at
        the same moment. The database's unique constraint is what settles that
        — not a check-then-insert, which is exactly the race the clinic's
        several terminals would lose. Each attempt gets its own transaction so
        a collision does not poison the caller's.
        """
        today = timezone.localdate()
        period = token_period_start(today)

        for _ in range(cls.TOKEN_ATTEMPTS):
            try:
                with transaction.atomic():
                    visit = cls.objects.create(
                        token=generate_token(),
                        token_date=today,
                        token_period=period,
                        **fields,
                    )
            except IntegrityError:
                continue

            if visit.queue_order_time != visit.check_in_time:
                visit.queue_order_time = visit.check_in_time
                visit.save(update_fields=["queue_order_time"])
            return visit

        raise RuntimeError(
            "Could not issue a unique token after "
            f"{cls.TOKEN_ATTEMPTS} attempts. The token pool for this period is "
            "effectively full — widen TOKEN_DIGITS or shorten TOKEN_PERIOD_DAYS."
        )

    @property
    def is_complete(self) -> bool:
        return self.current_stage == "complete"

    @property
    def public_destination(self) -> str:
        """
        What the waiting-room board shows beside this token.

        The only visit information that may ever appear on a public screen, with
        the token itself (spec FR8) — no name, no priority, no medical detail.
        """
        if self.assigned_counter:
            return self.assigned_counter.name
        return self.get_current_stage_display()


class NotificationContact(models.Model):
    """
    A phone number for a patient who asked for SMS updates (spec FR11).

    Kept in its own table rather than on ``Visit`` for a reason: a phone number
    identifies a person, and everything else in the queue database is
    deliberately anonymous. Isolating it means it can be purged on its own
    schedule, and that a query over visits does not carry it around by default.

    Retention is a governance matter (G5). Until that is approved, this holds
    fictional numbers only.
    """

    visit = models.OneToOneField(
        Visit, on_delete=models.CASCADE, related_name="notification_contact"
    )
    phone_number = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "notification contact"
        verbose_name_plural = "notification contacts"

    def __str__(self) -> str:
        # Never render the number itself in logs, admin lists or reprs.
        return f"contact for {self.visit.token}"


# ---------------------------------------------------------------------------
# Visit history
# ---------------------------------------------------------------------------


class StageEvent(models.Model):
    """
    One visit's passage through one stage (spec FR6).

    History is append-only and never overwritten, which is what makes
    return-after-tests (FR13) safe: a patient sent back to the clinician gets a
    new consultation event, and the earlier one still stands.

    Records the acting *role*, not the individual. Identifiable attribution
    lives in ``AuditLogEntry`` for accountability actions only — the two-layer
    model the spec sets out (G3).
    """

    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name="stage_events")
    stage = models.CharField(max_length=32, choices=contracts.choices("stages"))
    entered_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by_role = models.CharField(
        max_length=32, choices=Role.choices, blank=True
    )

    class Meta:
        ordering = ["entered_at", "id"]
        indexes = [
            # Feeds the rolling-median service time per stage (Phase 6).
            models.Index(
                fields=["stage", "completed_at"], name="stage_completed_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.visit.token} — {self.get_stage_display()}"

    @property
    def duration_seconds(self) -> float | None:
        """Service time for this stage, or None while it is still in progress."""
        if not self.completed_at:
            return None
        return (self.completed_at - self.entered_at).total_seconds()


class PriorityChange(models.Model):
    """
    A clinical priority decision (spec FR3, FR5).

    The system records the decision; it never makes it. Only authorised
    clinical roles may create one, and every change carries a role, a timestamp
    and a non-sensitive reason category.
    """

    visit = models.ForeignKey(
        Visit, on_delete=models.CASCADE, related_name="priority_changes"
    )
    previous_priority = models.CharField(
        max_length=16, choices=Visit.Priority.choices, blank=True
    )
    new_priority = models.CharField(max_length=16, choices=Visit.Priority.choices)
    changed_by_role = models.CharField(max_length=32, choices=Role.choices)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    # A category, not free clinical text — the queue database holds no clinical
    # detail, and a free-text box is where such detail would end up.
    non_sensitive_reason = models.CharField(
        max_length=120,
        help_text="Non-sensitive category for the change. Never a diagnosis or symptom.",
    )

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self) -> str:
        return f"{self.visit.token} → {self.get_new_priority_display()}"

    def clean(self) -> None:
        if self.changed_by_role not in contracts.roles_that_may_assign_priority():
            raise ValidationError(
                {
                    "changed_by_role": (
                        "Only authorised clinical roles may assign clinical "
                        "priority (spec FR3)."
                    )
                }
            )


class PharmacyOutcome(models.Model):
    """
    A pharmacy state change for a visit (spec FR10).

    Records only that medicine is ready, issued or unavailable. What the
    medicine is would be a prescription, which this database does not hold.
    """

    class State(models.TextChoices):
        READY = "medicine_ready", "Medicine ready"
        ISSUED = "medicine_issued", "Medicine issued"
        UNAVAILABLE = "medicine_unavailable", "Medicine unavailable"

    visit = models.ForeignKey(
        Visit, on_delete=models.CASCADE, related_name="pharmacy_outcomes"
    )
    state = models.CharField(max_length=32, choices=State.choices)
    by_role = models.CharField(max_length=32, choices=Role.choices)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["timestamp", "id"]

    def __str__(self) -> str:
        return f"{self.visit.token} — {self.get_state_display()}"


class AuditLogEntry(models.Model):
    """
    Identifiable trail for accountability actions — emergency overrides, manual
    reorders, key completions (spec FR14).

    Two details worth keeping in mind:

    * ``visit_token`` is a plain string, not a foreign key. Live queue tokens
      are purged at end of day; the audit trail is retained far longer. A
      foreign key would either cascade the history away or block the purge.
    * ``actor_staff_user`` is nullable with ``SET_NULL`` so an entry survives a
      staff account being removed, while ``actor_role`` keeps the record
      meaningful afterwards.

    Nothing writes to this table yet. The write path and the de-identified
    reporting layer are Phase 8, behind governance item G3.
    """

    actor_staff_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_entries",
    )
    actor_role = models.CharField(max_length=32, choices=Role.choices)
    action = models.CharField(max_length=64, db_index=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    visit_token = models.CharField(max_length=16, blank=True, db_index=True)
    non_sensitive_detail = models.TextField(
        blank=True,
        help_text="Never a diagnosis, symptom, prescription or patient identifier.",
    )

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "audit log entry"
        verbose_name_plural = "audit log entries"

    def __str__(self) -> str:
        return f"{self.timestamp:%Y-%m-%d %H:%M} {self.action} ({self.actor_role})"
