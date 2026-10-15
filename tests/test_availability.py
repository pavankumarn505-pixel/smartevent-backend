
from fastapi.testclient import TestClient

from app.main import app
from app.services.availability_manager import availability_manager


def test_availability_manager_broadcasts_to_connected_clients():
    import asyncio

    class FakeWebSocket:
        def __init__(self):
            self.messages = []

        async def send_json(self, message):
            self.messages.append(message)

    async def run_test():
        event_id = 987654
        websocket = FakeWebSocket()

        availability_manager.connections[event_id].add(websocket)

        try:
            await availability_manager.broadcast_availability(
                event_id=event_id,
                available_tickets=8,
            )

            assert websocket.messages == [
                {
                    "type": "ticket_availability",
                    "event_id": event_id,
                    "available_tickets": 8,
                }
            ]
        finally:
            availability_manager.disconnect(event_id, websocket)

    asyncio.run(run_test())


def test_availability_manager_removes_disconnected_client():
    import asyncio

    class FakeWebSocket:
        async def send_json(self, message):
            pass

    async def run_test():
        event_id = 987655
        websocket = FakeWebSocket()

        availability_manager.connections[event_id].add(websocket)
        availability_manager.disconnect(event_id, websocket)

        assert websocket not in availability_manager.connections.get(
            event_id, set()
        )

    asyncio.run(run_test())



def test_websocket_rejects_nonexistent_event():
    from starlette.websockets import WebSocketDisconnect

    client = TestClient(app)

    try:
        with client.websocket_connect(
            "/ws/events/999999/availability"
        ):
            assert False, "Expected the WebSocket connection to close"
    except WebSocketDisconnect as exc:
        assert exc.code == 1008
        assert exc.reason == "Event not found"
