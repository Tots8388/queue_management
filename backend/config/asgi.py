"""
ASGI entry point.

The system serves HTTP and WebSockets from one application: staff dashboards,
the patient status view and the public display all subscribe to the same queue
state over Channels. ``ProtocolTypeRouter`` splits the two protocols.

WebSocket routes are registered in ``config/routing.py`` (populated in Phase 4).
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Initialise Django before importing anything that touches the app registry.
django_asgi_application = get_asgi_application()

from config.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_application,
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)
