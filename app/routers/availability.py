
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Event
from app.services.availability_manager import availability_manager

router = APIRouter(tags=["Real-Time Availability"])


@router.websocket("/ws/events/{event_id}/availability")
async def event_availability_websocket(
    websocket: WebSocket,
    event_id: int,
):
    db: Session = SessionLocal()

    try:
        # Check whether the requested event exists.
        event = db.query(Event).filter(Event.id == event_id).first()

        if event is None:
            await websocket.close(
                code=1008,
                reason="Event not found",
            )
            return

        # Accept the connection and register the client.
        await availability_manager.connect(event_id, websocket)

        # Send the current availability immediately.
        await websocket.send_json(
            {
                "type": "ticket_availability",
                "event_id": event_id,
                "available_tickets": event.available_tickets,
            }
        )

        # Keep the connection open until the client disconnects.
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass

    except Exception:
        # Avoid leaving the client registered after an error.
        pass

    finally:
        # Remove the client if it was registered.
        availability_manager.disconnect(event_id, websocket)
        db.close()
