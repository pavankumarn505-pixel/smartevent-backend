from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Event, Booking, User, Notification
from ..schemas import EventCreate, EventUpdate, EventResponse
from ..role_dependencies import require_organizer
from ..services.event_service import update_event_status

router = APIRouter(
    prefix="/events",
    tags=["Events"]
)


# =========================================================
# HELPER: CREATE EVENT UPDATE NOTIFICATIONS
# =========================================================

def notify_booked_users(
    db: Session,
    event: Event,
    title: str,
    message: str,
    notification_type: str
):
    bookings = (
        db.query(Booking)
        .filter(
            Booking.event_id == event.id,
            Booking.booking_status == "CONFIRMED"
        )
        .all()
    )

    notified_users = set()

    for booking in bookings:

        # Avoid duplicate notifications if the same user
        # has multiple bookings for the same event.
        if booking.user_id in notified_users:
            continue

        notification = Notification(
            user_id=booking.user_id,
            title=title,
            message=message,
            type=notification_type,
            is_read=False
        )

        db.add(notification)
        notified_users.add(booking.user_id)


# =========================================================
# CREATE EVENT
# =========================================================

@router.post("/", response_model=EventResponse, status_code=201)
def create_event(
    event_data: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organizer)
):
    new_event = Event(
        title=event_data.title,
        description=event_data.description,
        category=event_data.category,
        location=event_data.location,
        event_date=event_data.event_date,
        ticket_price=event_data.ticket_price,
        banner_image=event_data.banner_image,
        total_tickets=event_data.total_tickets,
        available_tickets=event_data.total_tickets,
        organizer_id=current_user.id,
        event_status="UPCOMING"
    )

    db.add(new_event)
    db.commit()
    db.refresh(new_event)

    return new_event


# =========================================================
# GET ALL EVENTS
# =========================================================

@router.get("/", response_model=list[EventResponse])
def get_all_events(
    db: Session = Depends(get_db)
):
    events = (
        db.query(Event)
        .order_by(Event.event_date.asc())
        .all()
    )

    for event in events:
        new_status = update_event_status(event)

        if event.event_status != new_status:
            event.event_status = new_status

    db.commit()

    return events


# =========================================================
# SEARCH EVENTS
# =========================================================

@router.get("/search", response_model=list[EventResponse])
def search_events(
    title: str = Query(..., min_length=1),
    db: Session = Depends(get_db)
):
    events = (
        db.query(Event)
        .filter(Event.title.ilike(f"%{title}%"))
        .order_by(Event.event_date.asc())
        .all()
    )

    for event in events:
        new_status = update_event_status(event)

        if event.event_status != new_status:
            event.event_status = new_status

    db.commit()

    return events


# =========================================================
# GET EVENTS BY CATEGORY
# =========================================================

@router.get("/category/{category}", response_model=list[EventResponse])
def get_events_by_category(
    category: str,
    db: Session = Depends(get_db)
):
    events = (
        db.query(Event)
        .filter(Event.category.ilike(category))
        .order_by(Event.event_date.asc())
        .all()
    )

    for event in events:
        new_status = update_event_status(event)

        if event.event_status != new_status:
            event.event_status = new_status

    db.commit()

    return events


# =========================================================
# GET ORGANIZER'S EVENTS
# =========================================================

@router.get("/my-events", response_model=list[EventResponse])
def get_my_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organizer)
):
    events = (
        db.query(Event)
        .filter(Event.organizer_id == current_user.id)
        .order_by(Event.event_date.asc())
        .all()
    )

    for event in events:
        new_status = update_event_status(event)

        if event.event_status != new_status:
            event.event_status = new_status

    db.commit()

    return events


# =========================================================
# UPDATE EVENT
# =========================================================

@router.put("/{event_id}", response_model=EventResponse)
def update_event(
    event_id: int,
    event_data: EventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organizer)
):
    event = (
        db.query(Event)
        .filter(Event.id == event_id)
        .first()
    )

    if event is None:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    if event.organizer_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only update your own events"
        )

    if event.event_status == "CANCELLED":
        raise HTTPException(
            status_code=400,
            detail="Cancelled events cannot be updated"
        )

    update_data = event_data.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():

        if field == "total_tickets":
            tickets_sold = (
                event.total_tickets -
                event.available_tickets
            )

            if value < tickets_sold:
                raise HTTPException(
                    status_code=400,
                    detail="Total tickets cannot be less than tickets already sold"
                )

            event.available_tickets = value - tickets_sold

        setattr(event, field, value)

    # Recalculate event status
    event.event_status = update_event_status(event)

    # Notify users only if there are confirmed bookings
    notify_booked_users(
        db=db,
        event=event,
        title="Event Updated",
        message=f'The event "{event.title}" has been updated. Please check the latest event details.',
        notification_type="EVENT_UPDATE"
    )

    db.commit()
    db.refresh(event)

    return event


# =========================================================
# CANCEL EVENT
# =========================================================

@router.put("/{event_id}/cancel")
def cancel_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organizer)
):
    event = (
        db.query(Event)
        .filter(Event.id == event_id)
        .first()
    )

    if event is None:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    if event.organizer_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only cancel your own events"
        )

    if event.event_status == "CANCELLED":
        raise HTTPException(
            status_code=400,
            detail="Event is already cancelled"
        )

    event.event_status = "CANCELLED"

    # Notify confirmed ticket holders
    notify_booked_users(
        db=db,
        event=event,
        title="Event Cancelled",
        message=f'The event "{event.title}" has been cancelled.',
        notification_type="EVENT_CANCELLED"
    )

    db.commit()
    db.refresh(event)

    return {
        "message": "Event cancelled successfully",
        "event_id": event.id,
        "event_status": event.event_status
    }


# =========================================================
# GET BOOKINGS FOR ORGANIZER EVENT
# =========================================================

@router.get("/{event_id}/bookings")
def get_event_bookings(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organizer)
):
    event = (
        db.query(Event)
        .filter(Event.id == event_id)
        .first()
    )

    if event is None:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    if event.organizer_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only view bookings for your own events"
        )

    bookings = (
        db.query(Booking)
        .filter(Booking.event_id == event.id)
        .order_by(Booking.created_at.desc())
        .all()
    )

    return {
        "event_id": event.id,
        "event_title": event.title,
        "total_bookings": len(bookings),
        "bookings": [
            {
                "booking_id": booking.id,
                "user_id": booking.user_id,
                "ticket_quantity": booking.ticket_quantity,
                "total_price": booking.total_price,
                "booking_status": booking.booking_status,
                "created_at": booking.created_at
            }
            for booking in bookings
        ]
    }


# =========================================================
# GET SINGLE EVENT
# =========================================================

@router.get("/{event_id}", response_model=EventResponse)
def get_event(
    event_id: int,
    db: Session = Depends(get_db)
):
    event = (
        db.query(Event)
        .filter(Event.id == event_id)
        .first()
    )

    if event is None:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    new_status = update_event_status(event)

    if event.event_status != new_status:
        event.event_status = new_status
        db.commit()
        db.refresh(event)

    return event