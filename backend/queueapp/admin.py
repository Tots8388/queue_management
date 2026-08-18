"""
Django admin.

Intended for IT/Support account management and for inspecting the prototype's
fictional data — not as a clinical tool. Staff do their work through the
role-based dashboards, which enforce the queue policy; the admin does not.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    AuditLogEntry,
    NotificationContact,
    PharmacyOutcome,
    PriorityChange,
    ServiceCounter,
    StageEvent,
    StaffUser,
    Visit,
)


@admin.register(StaffUser)
class StaffUserAdmin(UserAdmin):
    list_display = ("username", "role", "default_counter", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff")
    fieldsets = UserAdmin.fieldsets + (
        ("Clinic role", {"fields": ("role", "default_counter")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Clinic role", {"fields": ("role", "default_counter")}),
    )


@admin.register(ServiceCounter)
class ServiceCounterAdmin(admin.ModelAdmin):
    list_display = ("name", "stage", "is_active")
    list_filter = ("stage", "is_active")


class StageEventInline(admin.TabularInline):
    model = StageEvent
    extra = 0
    readonly_fields = ("entered_at",)


class PriorityChangeInline(admin.TabularInline):
    model = PriorityChange
    extra = 0
    readonly_fields = ("timestamp",)


class PharmacyOutcomeInline(admin.TabularInline):
    model = PharmacyOutcome
    extra = 0
    readonly_fields = ("timestamp",)


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = (
        "token",
        "token_date",
        "current_stage",
        "stage_status",
        "priority",
        "presence_status",
        "check_in_time",
    )
    list_filter = ("token_period", "token_date", "current_stage", "stage_status", "priority")
    search_fields = ("token",)
    date_hierarchy = "check_in_time"
    inlines = [StageEventInline, PriorityChangeInline, PharmacyOutcomeInline]


@admin.register(AuditLogEntry)
class AuditLogEntryAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "action", "actor_role", "actor_staff_user", "visit_token")
    list_filter = ("action", "actor_role")
    search_fields = ("visit_token", "action")
    date_hierarchy = "timestamp"

    # The audit trail is evidence. It is written by the system and read by
    # authorised reviewers; nobody edits or deletes it through the admin.
    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(NotificationContact)
class NotificationContactAdmin(admin.ModelAdmin):
    # The phone number is the one identifying field in the database. It is not
    # listed, searchable or filterable here — reaching it takes a deliberate act.
    list_display = ("visit", "created_at")
    readonly_fields = ("created_at",)



admin.site.site_header = "Queue & patient flow — administration"
admin.site.site_title = "Queue administration"
admin.site.index_title = "Prototype data (fictional records only)"
