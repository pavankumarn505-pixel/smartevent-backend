
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import case, update
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    Booking,
    Event,
    User,
    Ticket,
    Notification,
    Coupon,
    Payment,
)
from ..schemas import BookingCreate, BookingResponse
from ..dependencies import get_current_user
from ..services.qr_service import (
    generate_ticket_code,
    generate_qr_code,
)
from ..services.availability_manager import availability_manager


router = APIRouter(
    prefix="/bookings",
    tags=["Bookings"],
)


def get_current_time():
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def broadcast_availability(event_id: int, available_tickets: int):
    """Broadcast the committed ticket count to connected WebSocket clients."""
    await availability_manager.broadcast_availability(
        event_id,
        available_tickets,
    )


def check_coupon(coupon: Coupon, booking_amount: float):
    if not coupon.is_active:
        raise HTTPException(status_code=400, detail="Coupon is inactive")

    expiry = coupon.expiry_date
    if expiry.tzinfo is not None:
        expiry = expiry.astimezone(timezone.utc).replace(tzinfo=None)

    if expiry <= get_current_time():
        raise HTTPException(status_code=400, detail="Coupon has expired")

    if coupon.used_count >= coupon.usage_limit:
        raise HTTPException(
            status_code=400,
            detail="Coupon usage limit reached",
        )

    if booking_amount < coupon.minimum_booking_amount:
        raise HTTPException(
            status_code=400,
            detail=(
                "Booking amount must be at least "
                f"{coupon.minimum_booking_amount}"
            ),
        )

    if coupon.discount_type == "PERCENTAGE":
        if coupon.discount_value > 100:
            raise HTTPException(
                status_code=400,
                detail="Invalid coupon percentage",
            )
        discount = booking_amount * coupon.discount_value / 100

    elif coupon.discount_type == "FIXED":
        discount = coupon.discount_value

    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid coupon discount type",
        )

    discount = round(min(discount, booking_amount), 2)
    final_amount = round(booking_amount - discount, 2)

    return discount, final_amount


# =========================================================
# CREATE BOOKING - ATOMIC TICKET RESERVATION
# =========================================================

@router.post("/", response_model=BookingResponse, status_code=201)
def create_booking(
    booking_data: BookingCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        if booking_data.ticket_quantity <= 0:
            raise HTTPException(
                status_code=400,
                detail="Ticket quantity must be greater than 0",
            )

        event = (
            db.query(Event)
            .filter(Event.id == booking_data.event_id)
            .first()
        )

        if event is None:
            raise HTTPException(
                status_code=404,
                detail="Event not found",
            )

        if event.event_status != "ACTIVE":
            raise HTTPException(
                status_code=400,
                detail="This event is not available for booking",
            )

        event_id = event.id
        ticket_quantity = booking_data.ticket_quantity
        event_title = event.title
        ticket_price = float(event.ticket_price)

        # Atomically reserve tickets only if the event is active
        # and enough tickets remain.
        reservation = db.execute(
            update(Event)
            .where(
                Event.id == event_id,
                Event.event_status == "ACTIVE",
                Event.available_tickets >= ticket_quantity,
            )
            .values(
                available_tickets=(
                    Event.available_tickets - ticket_quantity
                )
            )
            .execution_options(synchronize_session=False)
        )

        if reservation.rowcount != 1:
            # Preserve the exact error expected by existing tests.
            current_event = (
                db.query(Event)
                .filter(Event.id == event_id)
                .first()
            )

            if current_event is None:
                raise HTTPException(
                    status_code=404,
                    detail="Event not found",
                )

            if current_event.event_status != "ACTIVE":
                raise HTTPException(
                    status_code=400,
                    detail="This event is not available for booking",
                )

            raise HTTPException(
                status_code=400,
                detail="Not enough tickets available",
            )

        total_price = round(ticket_price * ticket_quantity, 2)

        coupon = None
        discount_amount = 0.0
        final_amount = total_price

        if booking_data.coupon_code:
            code = booking_data.coupon_code.strip().upper()

            coupon = (
                db.query(Coupon)
                .filter(Coupon.coupon_code == code)
                .first()
            )

            if coupon is None:
                raise HTTPException(
                    status_code=404,
                    detail="Coupon not found",
                )

            discount_amount, final_amount = check_coupon(
                coupon,
                total_price,
            )

            # Atomically reserve one coupon use.
            coupon_result = db.execute(
                update(Coupon)
                .where(
                    Coupon.id == coupon.id,
                    Coupon.is_active.is_(True),
                    Coupon.used_count < Coupon.usage_limit,
                    Coupon.expiry_date > get_current_time(),
                )
                .values(used_count=Coupon.used_count + 1)
                .execution_options(synchronize_session=False)
            )

            if coupon_result.rowcount != 1:
                raise HTTPException(
                    status_code=400,
                    detail="Coupon is no longer available",
                )

        new_booking = Booking(
            user_id=current_user.id,
            event_id=event_id,
            ticket_quantity=ticket_quantity,
            total_price=total_price,
            coupon_id=coupon.id if coupon else None,
            discount_amount=discount_amount,
            final_amount=final_amount,
            booking_status="PENDING",
        )

        db.add(new_booking)
        db.flush()

        ticket_code = generate_ticket_code()
        qr_code_url = generate_qr_code(ticket_code)

        new_ticket = Ticket(
            booking_id=new_booking.id,
            ticket_code=ticket_code,
            qr_code_url=qr_code_url,
        )
        db.add(new_ticket)

        notification = Notification(
            user_id=current_user.id,
            title="Booking Created",
            message=(
                f"Your booking for '{event_title}' has been created. "
                f"Tickets: {ticket_quantity}. "
                f"Original amount: {total_price:.2f}. "
                f"Discount: {discount_amount:.2f}. "
                f"Amount payable: {final_amount:.2f}. "
                "Your booking is pending payment."
            ),
            type="BOOKING",
            is_read=False,
        )
        db.add(notification)

        # Commit inventory and related booking records together.
        db.commit()
        db.refresh(new_booking)

        # Query the committed value rather than using a stale ORM object.
        available_tickets = (
            db.query(Event.available_tickets)
            .filter(Event.id == event_id)
            .scalar()
        )

        if available_tickets is not None:
            background_tasks.add_task(
                broadcast_availability,
                event_id,
                available_tickets,
            )

        return new_booking

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Booking could not be created. Please try again.",
        )


# =========================================================
# GET MY BOOKINGS
# =========================================================

@router.get("/my-bookings", response_model=list[BookingResponse])
def get_my_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Booking)
        .filter(Booking.user_id == current_user.id)
        .order_by(Booking.created_at.desc())
        .all()
    )


# =========================================================
# CANCEL BOOKING + SIMULATED REFUND
# =========================================================

@router.post("/{booking_id}/cancel", response_model=BookingResponse)
def cancel_booking(
    booking_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        booking = (
            db.query(Booking)
            .filter(
                Booking.id == booking_id,
                Booking.user_id == current_user.id,
            )
            .with_for_update()
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
                detail="Booking is already cancelled",
            )

        if booking.booking_status not in ("PENDING", "CONFIRMED"):
            raise HTTPException(
                status_code=400,
                detail="This booking cannot be cancelled",
            )

        event_id = booking.event_id
        quantity_to_restore = booking.ticket_quantity

        event = (
            db.query(Event)
            .filter(Event.id == event_id)
            .first()
        )

        if event is None:
            raise HTTPException(
                status_code=404,
                detail="Associated event not found",
            )

        successful_payments = (
            db.query(Payment)
            .filter(
                Payment.booking_id == booking.id,
                Payment.payment_status == "SUCCESS",
            )
            .all()
        )

        if len(successful_payments) > 1:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Multiple successful payments were found. "
                    "Please review this booking before cancelling."
                ),
            )

        refund_amount = 0.0

        if successful_payments:
            payment = successful_payments[0]

            if getattr(payment, "refund_status", "NONE") == "REFUNDED":
                raise HTTPException(
                    status_code=409,
                    detail="This payment has already been refunded",
                )

            refund_amount = round(float(payment.amount), 2)
            payment.refund_status = "REFUNDED"
            payment.refund_amount = refund_amount
            payment.refund_transaction_id = (
                f"SIM-REFUND-{uuid.uuid4().hex[:16].upper()}"
            )
            payment.refunded_at = get_current_time()

        # Restore inventory atomically and cap it at total capacity.
        restore_result = db.execute(
            update(Event)
            .where(Event.id == event_id)
            .values(
                available_tickets=case(
                    (
                        Event.available_tickets + quantity_to_restore
                        <= Event.total_tickets,
                        Event.available_tickets + quantity_to_restore,
                    ),
                    else_=Event.total_tickets,
                )
            )
            .execution_options(synchronize_session=False)
        )

        if restore_result.rowcount != 1:
            raise HTTPException(
                status_code=409,
                detail="Could not restore tickets for this event",
            )

        if booking.coupon_id is not None:
            coupon = (
                db.query(Coupon)
                .filter(Coupon.id == booking.coupon_id)
                .first()
            )

            if coupon is not None:
                coupon.used_count = max(0, coupon.used_count - 1)

        ticket = (
            db.query(Ticket)
            .filter(Ticket.booking_id == booking.id)
            .first()
        )

        if ticket is not None:
            db.delete(ticket)

        booking.booking_status = "CANCELLED"

        refund_message = (
            f"Simulated refund recorded: {refund_amount:.2f}. "
            "No real money was transferred."
            if successful_payments
            else "No successful payment was found; no refund was recorded."
        )

        notification = Notification(
            user_id=current_user.id,
            title="Booking Cancelled",
            message=(
                f"Booking #{booking.id} has been cancelled. "
                f"{refund_message}"
            ),
            type="BOOKING",
            is_read=False,
        )
        db.add(notification)

        db.commit()
        db.refresh(booking)

        available_tickets = (
            db.query(Event.available_tickets)
            .filter(Event.id == event_id)
            .scalar()
        )

        if available_tickets is not None:
            background_tasks.add_task(
                broadcast_availability,
                event_id,
                available_tickets,
            )

        return booking

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Booking cancellation failed. Please try again.",
        )
