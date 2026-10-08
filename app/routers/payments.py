from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Booking, User
from ..dependencies import get_current_user
from ..services.stripe_service import create_checkout_session


router = APIRouter(
    prefix="/payments",
    tags=["Payments"]
)


@router.post("/create-checkout/{booking_id}")
def create_payment_checkout(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    # Find booking
    booking = (
        db.query(Booking)
        .filter(
            Booking.id == booking_id,
            Booking.user_id == current_user.id
        )
        .first()
    )

    if booking is None:
        raise HTTPException(
            status_code=404,
            detail="Booking not found"
        )

    # Check booking status
    if booking.booking_status == "CONFIRMED":
        raise HTTPException(
            status_code=400,
            detail="Booking is already confirmed"
        )

    # Create Stripe Checkout Session
    session = create_checkout_session(
        event_title=booking.event.title,
        ticket_price=booking.event.ticket_price,
        ticket_quantity=booking.ticket_quantity,
        booking_id=booking.id
    )

    return {
        "message": "Stripe checkout created",
        "booking_id": booking.id,
        "checkout_url": session.url,
        "session_id": session.id
    }