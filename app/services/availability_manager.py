
from collections import defaultdict
from typing import Dict, Set

from fastapi import WebSocket


class AvailabilityManager:
    def __init__(self):
        # Each event can have multiple connected clients.
        self.connections: Dict[int, Set[WebSocket]] = defaultdict(set)

    async def connect(self, event_id: int, websocket: WebSocket):
        await websocket.accept()
        self.connections[event_id].add(websocket)

    def disconnect(self, event_id: int, websocket: WebSocket):
        connections = self.connections.get(event_id)

        if connections is not None:
            connections.discard(websocket)

            if not connections:
                self.connections.pop(event_id, None)

    async def broadcast_availability(
        self,
        event_id: int,
        available_tickets: int,
    ):
        message = {
            "type": "ticket_availability",
            "event_id": event_id,
            "available_tickets": available_tickets,
        }

        connections = list(self.connections.get(event_id, set()))

        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception:
                self.disconnect(event_id, websocket)


availability_manager = AvailabilityManager()
