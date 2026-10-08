from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Booking, Event, User, Ticket, Notification
from ..schemas import BookingCreate, BookingResponse
from ..dependencies import get_current_user
from ..services.qr_service import (
    generate_ticket_code,
    generate_qr_code
)

router = APIRouter(
    prefix="/bookings",
    tags=["Bookings"]
)


@router.post("/", response_model=BookingResponse, status_code=201)
def create_booking(
    booking_data: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    # Find event
    event = db.query(Event).filter(
        Event.id == booking_data.event_id
    ).first()

    if event is None:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    # Validate ticket quantity
    if booking_data.ticket_quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="Ticket quantity must be greater than 0"
        )

    # Check availability
    if booking_data.ticket_quantity > event.available_tickets:
        raise HTTPException(
            status_code=400,
            detail="Not enough tickets available"
        )

    # Calculate total price
    total_price = (
        event.ticket_price *
        booking_data.ticket_quantity
    )

    # Create booking
    new_booking = Booking(
        user_id=current_user.id,
        event_id=booking_data.event_id,
        ticket_quantity=booking_data.ticket_quantity,
        total_price=total_price,
        booking_status="CONFIRMED"
    )

    # Reduce available tickets
    event.available_tickets -= booking_data.ticket_quantity

    db.add(new_booking)

    # Get booking ID before creating ticket
    db.flush()

    # Generate ticket code
    ticket_code = generate_ticket_code()

    # Generate QR code
    qr_code_url = generate_qr_code(ticket_code)

    # Create ticket
    new_ticket = Ticket(
        booking_id=new_booking.id,
        ticket_code=ticket_code,
        qr_code_url=qr_code_url
    )

    db.add(new_ticket)

    # Create notification
    notification = Notification(
        user_id=current_user.id,
        title="Booking Confirmed",
        message=(
            f"Your booking for '{event.title}' has been confirmed. "
            f"You booked {booking_data.ticket_quantity} ticket(s)."
        ),
        type="BOOKING",
        is_read=False
    )

    db.add(notification)

    # Save everything
    db.commit()

    db.refresh(new_booking)

    return new_booking


@router.get(
    "/my-bookings",
    response_model=list[BookingResponse]
)
def get_my_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    bookings = (
        db.query(Booking)
        .filter(
            Booking.user_id == current_user.id
        )
        .order_by(
            Booking.created_at.desc()
        )
        .all()
    )

    return bookings