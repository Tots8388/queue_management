"""
WebSocket routes.

Three channels share one authoritative queue state (spec: Architecture):

  ws/display/           public waiting-room board — anonymous token + destination
  ws/patient/<token>/   personal status — stage, people ahead, wait range
  ws/staff/<stage>/     role-based dashboard queue for one service stage

Only the staff route is authenticated: patients have no accounts, and the board
drives a screen on a wall.
"""

from django.urls import path

from queueapp import consumers

websocket_urlpatterns = [
    path("ws/display/", consumers.PublicDisplayConsumer.as_asgi()),
    path("ws/patient/<str:token>/", consumers.PatientStatusConsumer.as_asgi()),
    path("ws/staff/<str:stage>/", consumers.StaffQueueConsumer.as_asgi()),
]
