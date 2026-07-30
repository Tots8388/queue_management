"""
WebSocket routes.

Three channels share one authoritative queue state (spec: Architecture):

  ws/patient/<token>/   personal status — token, stage, people ahead, wait range
  ws/staff/<stage>/     role-based dashboard queue for one service stage
  ws/display/           public waiting-room board — anonymous token + destination

Consumers are implemented in Phase 4. This module exists now so the ASGI
application is wired end to end and the transport can be verified.
"""

websocket_urlpatterns: list = []
