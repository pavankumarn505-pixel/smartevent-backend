from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Ticket, Booking, User
from ..schemas import TicketResponse
from ..dependencies import get_current_user


router = APIRouter(
    prefix="/tickets",
    tags=["Tickets"]
)


# =========================================================
# GET MY TICKETS
# =========================================================

@router.get(
    "/my-tickets",
    response_model=list[TicketResponse]
)
def get_my_tickets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    tickets = (
        db.query(Ticket)
        .join(Booking, Ticket.booking_id == Booking.id)
        .filter(
            Booking.user_id == current_user.id
        )
        .order_by(
            Ticket.created_at.desc()
        )
        .all()
    )

    return tickets