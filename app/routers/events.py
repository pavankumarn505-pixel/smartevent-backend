from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Event, Booking, User, Notification
from ..schemas import EventCreate, EventUpdate, EventResponse
from ..role_dependencies import require_organizer
from ..services.event_service import update_event_status


router = APIRouter(
    prefix="/events",
    tags=["Events"],
)


# =========================================================
# HELPER: REFRESH EVENT STATUSES
# =========================================================

def refresh_event_statuses(db: Session, events: list[Event]) -> None:
    changed = False

    for event in events:
        new_status = update_event_status(event)

        if event.event_status != new_status:
            event.event_status = new_status
            changed = True

    if changed:
        db.commit()


# =========================================================
# HELPER: NOTIFY USERS WITH CONFIRMED BOOKINGS
# =========================================================

def notify_booked_users(
    db: Session,
    event: Event,
    title: str,
    message: str,
    notification_type: str,
) -> None:
    bookings = (
        db.query(Booking)
        .filter(
            Booking.event_id == event.id,
            Booking.booking_status == "CONFIRMED",
        )
        .all()
    )

    notified_users = set()

    for booking in bookings:
        if booking.user_id in notified_users:
            continue

        db.add(
            Notification(
                user_id=booking.user_id,
                title=title,
                message=message,
                type=notification_type,
                is_read=False,
            )
        )
        notified_users.add(booking.user_id)


# =========================================================
# CREATE EVENT
# =========================================================

@router.post("/", response_model=EventResponse, status_code=201)
def create_event(
    event_data: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organizer),
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
        event_status="UPCOMING",
    )

    db.add(new_event)
    db.commit()
    db.refresh(new_event)

    return new_event


# =========================================================
# ADVANCED SEARCH, FILTERING, SORTING AND PAGINATION
# GET /events/
# =========================================================

@router.get("/", response_model=list[EventResponse])
def get_all_events(
    title: str | None = Query(None, min_length=1, max_length=200),
    category: str | None = Query(None, min_length=1, max_length=50),
    location: str | None = Query(None, min_length=1, max_length=255),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    sort_by: str = Query(
        "date",
        pattern="^(date|price_asc|price_desc|popularity)$",
    ),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if min_price is not None and max_price is not None:
        if min_price > max_price:
            raise HTTPException(
                status_code=400,
                detail="min_price cannot be greater than max_price.",
            )

    if start_date is not None and end_date is not None:
        if start_date > end_date:
            raise HTTPException(
                status_code=400,
                detail="start_date cannot be after end_date.",
            )

    query = db.query(Event)

    # Search by event title.
    if title:
        query = query.filter(
            Event.title.ilike(f"%{title.strip()}%")
        )

    # Filter by category.
    if category:
        query = query.filter(
            Event.category.ilike(category.strip())
        )

    # Search by location.
    if location:
        query = query.filter(
            Event.location.ilike(f"%{location.strip()}%")
        )

    # Filter by ticket price.
    if min_price is not None:
        query = query.filter(
            Event.ticket_price >= min_price
        )

    if max_price is not None:
        query = query.filter(
            Event.ticket_price <= max_price
        )

    # Filter by event date.
    if start_date is not None:
        query = query.filter(
            Event.event_date >= start_date
        )

    if end_date is not None:
        query = query.filter(
            Event.event_date <= end_date
        )

    # Sort results.
    if sort_by == "price_asc":
        query = query.order_by(
            Event.ticket_price.asc(),
            Event.id.asc(),
        )

    elif sort_by == "price_desc":
        query = query.order_by(
            Event.ticket_price.desc(),
            Event.id.asc(),
        )

    elif sort_by == "popularity":
        popularity = (
            db.query(
                Booking.event_id.label("event_id"),
                func.count(Booking.id).label("booking_count"),
            )
            .filter(Booking.booking_status == "CONFIRMED")
            .group_by(Booking.event_id)
            .subquery()
        )

        query = (
            query.outerjoin(
                popularity,
                Event.id == popularity.c.event_id,
            )
            .order_by(
                func.coalesce(
                    popularity.c.booking_count, 0
                ).desc(),
                Event.event_date.asc(),
                Event.id.asc(),
            )
        )

    else:
        query = query.order_by(
            Event.event_date.asc(),
            Event.id.asc(),
        )

    # Pagination.
    offset = (page - 1) * limit

    events = query.offset(offset).limit(limit).all()

    refresh_event_statuses(db, events)

    return events


# =========================================================
# SEARCH EVENTS BY TITLE (EXISTING ENDPOINT)
# =========================================================

@router.get("/search", response_model=list[EventResponse])
def search_events(
    title: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    events = (
        db.query(Event)
        .filter(Event.title.ilike(f"%{title.strip()}%"))
        .order_by(Event.event_date.asc())
        .all()
    )

    refresh_event_statuses(db, events)

    return events


# =========================================================
# GET EVENTS BY CATEGORY (EXISTING ENDPOINT)
# =========================================================

@router.get(
    "/category/{category}",
    response_model=list[EventResponse],
)
def get_events_by_category(
    category: str,
    db: Session = Depends(get_db),
):
    events = (
        db.query(Event)
        .filter(Event.category.ilike(category))
        .order_by(Event.event_date.asc())
        .all()
    )

    refresh_event_statuses(db, events)

    return events


# =========================================================
# GET CURRENT ORGANIZER'S EVENTS
# =========================================================

@router.get("/my-events", response_model=list[EventResponse])
def get_my_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organizer),
):
    events = (
        db.query(Event)
        .filter(Event.organizer_id == current_user.id)
        .order_by(Event.event_date.asc())
        .all()
    )

    refresh_event_statuses(db, events)

    return events


# =========================================================
# UPDATE EVENT
# =========================================================

@router.put("/{event_id}", response_model=EventResponse)
def update_event(
    event_id: int,
    event_data: EventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organizer),
):
    event = db.query(Event).filter(Event.id == event_id).first()

    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.organizer_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only update your own events",
        )

    if event.event_status == "CANCELLED":
        raise HTTPException(
            status_code=400,
            detail="Cancelled events cannot be updated",
        )

    update_data = event_data.model_dump(exclude_unset=True)

    for field in ("organizer_id", "available_tickets", "event_status"):
        update_data.pop(field, None)

    if "total_tickets" in update_data:
        new_total = update_data["total_tickets"]

        if new_total is not None:
            tickets_sold = event.total_tickets - event.available_tickets

            if new_total < tickets_sold:
                raise HTTPException(
                    status_code=400,
                    detail="Total tickets cannot be less than tickets already sold",
                )

            event.available_tickets = new_total - tickets_sold

    for field, value in update_data.items():
        setattr(event, field, value)

    event.event_status = update_event_status(event)

    notify_booked_users(
        db=db,
        event=event,
        title="Event Updated",
        message=(
            f'The event "{event.title}" has been updated. '
            "Please check the latest event details."
        ),
        notification_type="EVENT_UPDATE",
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
    current_user: User = Depends(require_organizer),
):
    event = db.query(Event).filter(Event.id == event_id).first()

    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.organizer_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only cancel your own events",
        )

    if event.event_status == "CANCELLED":
        raise HTTPException(
            status_code=400,
            detail="Event is already cancelled",
        )

    event.event_status = "CANCELLED"

    notify_booked_users(
        db=db,
        event=event,
        title="Event Cancelled",
        message=f'The event "{event.title}" has been cancelled.',
        notification_type="EVENT_CANCELLED",
    )

    db.commit()
    db.refresh(event)

    return {
        "message": "Event cancelled successfully",
        "event_id": event.id,
        "event_status": event.event_status,
    }


# =========================================================
# GET BOOKINGS FOR AN ORGANIZER'S EVENT
# =========================================================

@router.get("/{event_id}/bookings")
def get_event_bookings(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organizer),
):
    event = db.query(Event).filter(Event.id == event_id).first()

    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.organizer_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only view bookings for your own events",
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
                "created_at": booking.created_at,
            }
            for booking in bookings
        ],
    }


# =========================================================
# GET A SINGLE EVENT
# =========================================================

@router.get("/{event_id}", response_model=EventResponse)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
):
    event = db.query(Event).filter(Event.id == event_id).first()

    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    refresh_event_statuses(db, [event])

    return event