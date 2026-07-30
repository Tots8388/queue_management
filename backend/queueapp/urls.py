from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import auth_views, views

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
]
