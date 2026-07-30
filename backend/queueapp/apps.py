from django.apps import AppConfig


class QueueAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "queueapp"
    verbose_name = "Queue and patient flow"
