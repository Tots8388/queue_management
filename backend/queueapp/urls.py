from django.urls import path

from . import views

app_name = "queueapp"

urlpatterns = [
    path("health/", views.HealthView.as_view(), name="health"),
    path("contracts/", views.ContractsView.as_view(), name="contracts"),
]
