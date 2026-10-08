from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Event, Booking, User
from ..role_dependencies import require_organizer


router = APIRouter(
    prefix="/organizer",
    tags=["Organizer Analytics"]
)


# =========================================================
# ORGANIZER EVENT ANALYTICS
# =========================================================

@router.get("/analytics")
def get_organizer_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organizer)
):

    events = (
        db.query(Event)
        .filter(
            Event.organizer_id == current_user.id
        )
        .order_by(Event.event_date.asc())
        .all()
    )

    event_analytics = []

    total_tickets_sold = 0
    total_revenue = 0.0
    total_bookings = 0

    for event in events:

        # -------------------------------------------------
        # Only confirmed bookings count as sales
        # -------------------------------------------------

        bookings = (
            db.query(Booking)
            .filter(
                Booking.event_id == event.id,
                Booking.booking_status == "CONFIRMED"
            )
            .all()
        )

        booking_count = len(bookings)

        tickets_sold = sum(
            booking.ticket_quantity
            for booking in bookings
        )

        revenue = sum(
            booking.total_price
            for booking in bookings
        )

        remaining_tickets = event.available_tickets

        # -------------------------------------------------
        # Overall totals
        # -------------------------------------------------

        total_tickets_sold += tickets_sold
        total_revenue += revenue
        total_bookings += booking_count

        # -------------------------------------------------
        # Event analytics
        # -------------------------------------------------

        event_analytics.append(
            {
                "event_id": event.id,
                "event_title": event.title,
                "event_status": event.event_status,
                "event_date": event.event_date,

                "total_tickets": event.total_tickets,
                "tickets_sold": tickets_sold,
                "remaining_tickets": remaining_tickets,

                "booking_count": booking_count,
                "total_revenue": revenue
            }
        )

    return {
        "organizer_id": current_user.id,
        "organizer_username": current_user.username,

        "summary": {
            "total_events": len(events),
            "total_tickets_sold": total_tickets_sold,
            "total_bookings": total_bookings,
            "total_revenue": total_revenue
        },

        "events": event_analytics
    }


# =========================================================
# SINGLE EVENT ANALYTICS
# =========================================================

@router.get("/events/{event_id}/analytics")
def get_single_event_analytics(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organizer)
):

    event = (
        db.query(Event)
        .filter(
            Event.id == event_id
        )
        .first()
    )

    if event is None:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    # -----------------------------------------------------
    # Ownership validation
    # -----------------------------------------------------

    if event.organizer_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only view analytics for your own events"
        )

    # -----------------------------------------------------
    # Confirmed bookings only
    # -----------------------------------------------------

    bookings = (
        db.query(Booking)
        .filter(
            Booking.event_id == event.id,
            Booking.booking_status == "CONFIRMED"
        )
        .all()
    )

    booking_count = len(bookings)

    tickets_sold = sum(
        booking.ticket_quantity
        for booking in bookings
    )

    total_revenue = sum(
        booking.total_price
        for booking in bookings
    )

    return {
        "event_id": event.id,
        "event_title": event.title,
        "event_status": event.event_status,

        "total_tickets": event.total_tickets,
        "tickets_sold": tickets_sold,
        "remaining_tickets": event.available_tickets,

        "booking_count": booking_count,
        "total_revenue": total_revenue
    }