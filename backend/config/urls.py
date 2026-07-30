"""
URL routing for the Digital Queue & Patient-Flow Management System.

All application endpoints live under /api/. Queue, auth and dashboard routes are
added in later phases; Phase 0 exposes only infrastructure endpoints.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("queueapp.urls")),
]
