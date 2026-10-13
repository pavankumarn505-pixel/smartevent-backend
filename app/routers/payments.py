
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    Booking,
    Payment,
    Ticket,
    Notification,
    User,
)
from ..dependencies import get_current_user
from ..schemas import PaymentResponse
from ..services.qr_service import (
    generate_ticket_code,
    generate_qr_code,
)

router = APIRouter(
    prefix="/payments",
    tags=["Payments"],
)


@router.post(
    "/simulate/{booking_id}",
    response_model=PaymentResponse,
)
def simulate_payment(
    booking_id: int,
    outcome: str = "SUCCESS",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    outcome = outcome.upper()

    if outcome not in ["SUCCESS", "FAILED"]:
        raise HTTPException(
            status_code=400,
            detail="Outcome must be SUCCESS or FAILED",
        )

    booking = (
        db.query(Booking)
        .filter(
            Booking.id == booking_id,
            Booking.user_id == current_user.id,
        )
        .first()
    )

    if booking is None:
        raise HTTPException(
            status_code=404,
            detail="Booking not found",
        )

    if booking.booking_status == "CANCELLED":
        raise HTTPException(
            status_code=400,
            detail="Cancelled bookings cannot be paid",
        )

    if booking.booking_status == "CONFIRMED":
        raise HTTPException(
            status_code=400,
            detail="Booking is already confirmed",
        )

    successful_payment = (
        db.query(Payment)
        .filter(
            Payment.booking_id == booking.id,
            Payment.payment_status == "SUCCESS",
        )
        .first()
    )

    if successful_payment:
        raise HTTPException(
            status_code=400,
            detail="A successful payment already exists",
        )

    # Use the discounted amount when available.
    # Fall back to total_price for older bookings.
    payable_amount = (
        booking.final_amount
        if booking.final_amount is not None
        else booking.total_price
    )

    try:
        payment = Payment(
            booking_id=booking.id,
            payment_method="SIMULATED",
            payment_status="PENDING",
            amount=payable_amount,
        )

        db.add(payment)
        db.flush()

        payment.transaction_id = (
            f"SIM-{uuid.uuid4().hex.upper()}"
        )
        payment.payment_status = outcome

        if outcome == "SUCCESS":
            booking.booking_status = "CONFIRMED"

            # Create a ticket only if one does not already exist.
            ticket = (
                db.query(Ticket)
                .filter(Ticket.booking_id == booking.id)
                .first()
            )

            if ticket is None:
                ticket_code = generate_ticket_code()
                qr_url = generate_qr_code(ticket_code)

                ticket = Ticket(
                    booking_id=booking.id,
                    ticket_code=ticket_code,
                    qr_code_url=qr_url,
                )
                db.add(ticket)

            # Send the notification even if the ticket
            # was created earlier during booking.
            notification = Notification(
                user_id=current_user.id,
                title="Payment Successful",
                message=(
                    f"Payment of {payable_amount:.2f} successful "
                    f"for booking #{booking.id}. "
                    "Your booking is confirmed and your ticket is ready."
                ),
                type="PAYMENT_SUCCESS",
                is_read=False,
            )
            db.add(notification)

        else:
            notification = Notification(
                user_id=current_user.id,
                title="Payment Failed",
                message=(
                    f"Payment of {payable_amount:.2f} failed "
                    f"for booking #{booking.id}. Please try again."
                ),
                type="PAYMENT_FAILED",
                is_read=False,
            )
            db.add(notification)

        db.commit()
        db.refresh(payment)

        return payment

    except Exception as exc:
        db.rollback()

        print(f"Payment processing error: {exc}")

        raise HTTPException(
            status_code=500,
            detail=(
                "Payment processing failed. Check the "
                "backend terminal for details."
            ),
        )


@router.get(
    "/my-payments",
    response_model=list[PaymentResponse],
)
def get_my_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payments = (
        db.query(Payment)
        .join(
            Booking,
            Payment.booking_id == Booking.id,
        )
        .filter(
            Booking.user_id == current_user.id,
        )
        .order_by(Payment.created_at.desc())
        .all()
    )

    return payments
