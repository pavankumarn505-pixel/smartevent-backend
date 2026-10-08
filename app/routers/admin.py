from datetime import datetime, date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Event, Booking, Ticket, Notification
from ..schemas import AdminRoleUpdate
from ..role_dependencies import require_admin


router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@router.get("/dashboard")
def admin_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    total_users = db.query(User).count()
    total_events = db.query(Event).count()
    total_bookings = db.query(Booking).count()

    # Only confirmed bookings count as sold tickets
    confirmed_bookings = (
        db.query(Booking)
        .filter(
            Booking.booking_status == "CONFIRMED"
        )
        .all()
    )

    total_tickets_sold = sum(
        booking.ticket_quantity
        for booking in confirmed_bookings
    )

    total_revenue = sum(
        booking.total_price
        for booking in confirmed_bookings
    )

    return {
        "admin": {
            "id": current_user.id,
            "username": current_user.username,
            "role": current_user.role
        },
        "platform_statistics": {
            "total_users": total_users,
            "total_events": total_events,
            "total_bookings": total_bookings,
            "total_tickets_sold": total_tickets_sold,
            "total_revenue": total_revenue
        }
    }


# =========================================================
# USER MANAGEMENT
# =========================================================

@router.get("/users")
def get_all_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    users = (
        db.query(User)
        .order_by(User.id.asc())
        .all()
    )

    return {
        "total_users": len(users),
        "users": [
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "created_at": user.created_at
            }
            for user in users
        ]
    }


@router.get("/users/{user_id}")
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "created_at": user.created_at
    }


@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    role_data: AdminRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    # Prevent admin from removing their own admin access
    if user.id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot change your own admin role"
        )

    user.role = role_data.role

    db.commit()
    db.refresh(user)

    return {
        "message": "User role updated successfully",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role
        }
    }


# =========================================================
# EVENT MANAGEMENT
# =========================================================

@router.get("/events")
def get_all_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    events = (
        db.query(Event)
        .order_by(Event.event_date.asc())
        .all()
    )

    return {
        "total_events": len(events),
        "events": [
            {
                "event_id": event.id,
                "title": event.title,
                "category": event.category,
                "location": event.location,
                "event_date": event.event_date,
                "ticket_price": event.ticket_price,
                "total_tickets": event.total_tickets,
                "available_tickets": event.available_tickets,
                "event_status": event.event_status,
                "organizer_id": event.organizer_id
            }
            for event in events
        ]
    }


@router.get("/events/{event_id}")
def get_single_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
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

    return {
        "event_id": event.id,
        "title": event.title,
        "description": event.description,
        "category": event.category,
        "location": event.location,
        "event_date": event.event_date,
        "ticket_price": event.ticket_price,
        "total_tickets": event.total_tickets,
        "available_tickets": event.available_tickets,
        "organizer_id": event.organizer_id,
        "event_status": event.event_status,
        "created_at": event.created_at
    }


@router.put("/events/{event_id}/cancel")
def admin_cancel_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
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

    if event.event_status == "CANCELLED":
        raise HTTPException(
            status_code=400,
            detail="Event is already cancelled"
        )

    event.event_status = "CANCELLED"

    # Find confirmed bookings
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

        if booking.user_id in notified_users:
            continue

        notification = Notification(
            user_id=booking.user_id,
            title="Event Cancelled",
            message=(
                f'The event "{event.title}" '
                f'has been cancelled by the administrator.'
            ),
            type="EVENT_CANCELLED",
            is_read=False
        )

        db.add(notification)
        notified_users.add(booking.user_id)

    db.commit()
    db.refresh(event)

    return {
        "message": "Event cancelled successfully",
        "event_id": event.id,
        "event_status": event.event_status
    }


@router.delete("/events/{event_id}")
def admin_delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
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

    booking_count = (
        db.query(Booking)
        .filter(
            Booking.event_id == event.id
        )
        .count()
    )

    if booking_count > 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot delete an event that has bookings. "
                "Cancel the event instead."
            )
        )

    db.delete(event)
    db.commit()

    return {
        "message": "Event deleted successfully",
        "event_id": event_id
    }


# =========================================================
# BOOKING MANAGEMENT
# =========================================================

@router.get("/bookings")
def get_all_bookings(
    status: str | None = Query(
        None,
        description=(
            "Filter by booking status: "
            "PENDING, CONFIRMED, or CANCELLED"
        )
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    query = db.query(Booking)

    if status:
        status = status.upper()

        if status not in [
            "PENDING",
            "CONFIRMED",
            "CANCELLED"
        ]:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid booking status. "
                    "Use PENDING, CONFIRMED, or CANCELLED."
                )
            )

        query = query.filter(
            Booking.booking_status == status
        )

    bookings = (
        query
        .order_by(Booking.created_at.desc())
        .all()
    )

    return {
        "total_bookings": len(bookings),
        "bookings": [
            {
                "booking_id": booking.id,
                "user_id": booking.user_id,
                "event_id": booking.event_id,
                "ticket_quantity": booking.ticket_quantity,
                "total_price": booking.total_price,
                "booking_status": booking.booking_status,
                "created_at": booking.created_at
            }
            for booking in bookings
        ]
    }


@router.get("/bookings/{booking_id}")
def get_single_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    booking = (
        db.query(Booking)
        .filter(Booking.id == booking_id)
        .first()
    )

    if booking is None:
        raise HTTPException(
            status_code=404,
            detail="Booking not found"
        )

    return {
        "booking_id": booking.id,
        "user_id": booking.user_id,
        "event_id": booking.event_id,
        "ticket_quantity": booking.ticket_quantity,
        "total_price": booking.total_price,
        "booking_status": booking.booking_status,
        "created_at": booking.created_at
    }


@router.put("/bookings/{booking_id}/cancel")
def admin_cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    booking = (
        db.query(Booking)
        .filter(Booking.id == booking_id)
        .first()
    )

    if booking is None:
        raise HTTPException(
            status_code=404,
            detail="Booking not found"
        )

    if booking.booking_status == "CANCELLED":
        raise HTTPException(
            status_code=400,
            detail="Booking is already cancelled"
        )

    event = (
        db.query(Event)
        .filter(Event.id == booking.event_id)
        .first()
    )

    booking.booking_status = "CANCELLED"

    # Return reserved tickets to event inventory
    if event:
        event.available_tickets += booking.ticket_quantity

        # Prevent available tickets exceeding total tickets
        if event.available_tickets > event.total_tickets:
            event.available_tickets = event.total_tickets

    notification = Notification(
        user_id=booking.user_id,
        title="Booking Cancelled",
        message=(
            f"Your booking #{booking.id} "
            f"has been cancelled by the administrator."
        ),
        type="BOOKING_CANCELLED",
        is_read=False
    )

    db.add(notification)

    db.commit()
    db.refresh(booking)

    return {
        "message": "Booking cancelled successfully",
        "booking_id": booking.id,
        "booking_status": booking.booking_status
    }


# =========================================================
# PLATFORM ANALYTICS
# =========================================================

@router.get("/analytics")
def platform_analytics(
    start_date: date | None = Query(
        None,
        description="Start date YYYY-MM-DD"
    ),
    end_date: date | None = Query(
        None,
        description="End date YYYY-MM-DD"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    # Validate date range
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date cannot be after end_date"
        )

    # Only confirmed bookings are included in revenue analytics
    bookings_query = (
        db.query(Booking)
        .filter(
            Booking.booking_status == "CONFIRMED"
        )
    )

    if start_date:
        bookings_query = bookings_query.filter(
            Booking.created_at >= datetime.combine(
                start_date,
                datetime.min.time()
            )
        )

    if end_date:
        bookings_query = bookings_query.filter(
            Booking.created_at <= datetime.combine(
                end_date,
                datetime.max.time()
            )
        )

    confirmed_bookings = bookings_query.all()

    total_bookings = len(confirmed_bookings)

    total_tickets = sum(
        booking.ticket_quantity
        for booking in confirmed_bookings
    )

    total_revenue = sum(
        booking.total_price
        for booking in confirmed_bookings
    )

    # =====================================================
    # DAILY TICKET SALES
    # =====================================================

    daily_sales = {}

    for booking in confirmed_bookings:

        booking_date = (
            booking.created_at.date().isoformat()
        )

        if booking_date not in daily_sales:
            daily_sales[booking_date] = {
                "date": booking_date,
                "tickets_sold": 0,
                "bookings": 0,
                "revenue": 0
            }

        daily_sales[booking_date]["tickets_sold"] += (
            booking.ticket_quantity
        )

        daily_sales[booking_date]["bookings"] += 1

        daily_sales[booking_date]["revenue"] += (
            booking.total_price
        )

    # =====================================================
    # MONTHLY BOOKING TRENDS
    # =====================================================

    monthly_trends = {}

    for booking in confirmed_bookings:

        month = booking.created_at.strftime(
            "%Y-%m"
        )

        if month not in monthly_trends:
            monthly_trends[month] = {
                "month": month,
                "bookings": 0,
                "tickets_sold": 0,
                "revenue": 0
            }

        monthly_trends[month]["bookings"] += 1

        monthly_trends[month]["tickets_sold"] += (
            booking.ticket_quantity
        )

        monthly_trends[month]["revenue"] += (
            booking.total_price
        )

    # =====================================================
    # EVENT STATISTICS
    # =====================================================

    event_stats = {}

    for booking in confirmed_bookings:

        event_id = booking.event_id

        if event_id not in event_stats:
            event_stats[event_id] = {
                "event_id": event_id,
                "tickets_sold": 0,
                "bookings": 0,
                "revenue": 0
            }

        event_stats[event_id]["tickets_sold"] += (
            booking.ticket_quantity
        )

        event_stats[event_id]["bookings"] += 1

        event_stats[event_id]["revenue"] += (
            booking.total_price
        )

    # Add event titles
    for event_id, stats in event_stats.items():

        event = (
            db.query(Event)
            .filter(Event.id == event_id)
            .first()
        )

        if event:
            stats["event_title"] = event.title
        else:
            stats["event_title"] = "Unknown Event"

    # =====================================================
    # MOST POPULAR EVENTS
    # =====================================================

    popular_events = sorted(
        event_stats.values(),
        key=lambda x: x["tickets_sold"],
        reverse=True
    )

    # =====================================================
    # TOP REVENUE EVENTS
    # =====================================================

    top_revenue_events = sorted(
        event_stats.values(),
        key=lambda x: x["revenue"],
        reverse=True
    )

    # =====================================================
    # FINAL RESPONSE
    # =====================================================

    return {
        "filters": {
            "start_date": start_date,
            "end_date": end_date
        },

        "summary": {
            "total_bookings": total_bookings,
            "total_tickets_sold": total_tickets,
            "total_revenue": total_revenue
        },

        "daily_ticket_sales": sorted(
            daily_sales.values(),
            key=lambda x: x["date"]
        ),

        "monthly_booking_trends": sorted(
            monthly_trends.values(),
            key=lambda x: x["month"]
        ),

        "most_popular_events": popular_events,

        "top_revenue_events": top_revenue_events
    }