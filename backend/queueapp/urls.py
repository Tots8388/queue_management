from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import auth_views, oversight_views, queue_views, views

app_name = "queueapp"

urlpatterns = [
    # Infrastructure
    path("health/", views.HealthView.as_view(), name="health"),
    path("contracts/", views.ContractsView.as_view(), name="contracts"),
    # Staff authentication
    path("auth/login/", auth_views.LoginView.as_view(), name="login"),
    path("auth/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/me/", auth_views.CurrentUserView.as_view(), name="current-user"),
    # Reception
    path("visits/check-in/", queue_views.CheckInView.as_view(), name="check-in"),
    path(
        "visits/reconcile-fallback/",
        queue_views.FallbackReconciliationView.as_view(),
        name="reconcile-fallback",
    ),
    # Staff queue
    path(
        "queue/<str:stage>/",
        queue_views.StageQueueView.as_view(),
        name="stage-queue",
    ),
    path(
        "visits/<str:token>/start/",
        queue_views.StartServingView.as_view(),
        name="start-serving",
    ),
    path(
        "visits/<str:token>/complete/",
        queue_views.CompleteStageView.as_view(),
        name="complete-stage",
    ),
    path(
        "visits/<str:token>/presence/",
        queue_views.PresenceView.as_view(),
        name="presence",
    ),
    # Clinical
    path(
        "visits/<str:token>/priority/",
        queue_views.PriorityView.as_view(),
        name="priority",
    ),
    path(
        "visits/<str:token>/reorder/",
        queue_views.ReorderView.as_view(),
        name="reorder",
    ),
    path(
        "visits/<str:token>/send-for-tests/",
        queue_views.SendForTestsView.as_view(),
        name="send-for-tests",
    ),
    path(
        "visits/<str:token>/return-after-tests/",
        queue_views.ReturnAfterTestsView.as_view(),
        name="return-after-tests",
    ),
    path(
        "visits/<str:token>/pharmacy/",
        queue_views.PharmacyOutcomeView.as_view(),
        name="pharmacy-outcome",
    ),
    # Management review — capabilities nobody holds until G4 is settled
    path("audit/", oversight_views.AuditLogView.as_view(), name="audit-log"),
    path("reports/", oversight_views.ReportsView.as_view(), name="reports"),
    # Patient and public channels — no authentication
    path(
        "patient/<str:token>/",
        queue_views.PatientStatusView.as_view(),
        name="patient-status",
    ),
    path("display/", queue_views.PublicDisplayView.as_view(), name="public-display"),
]
