from datetime import datetime, date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    User,
    Event,
    Booking,
    Ticket,
    Notification,
    AuditLog,
)
from ..schemas import AdminRoleUpdate
from ..role_dependencies import require_admin
from ..services.audit_service import create_audit_log


router = APIRouter(prefix="/admin", tags=["Admin"])


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

    confirmed_bookings = (
        db.query(Booking)
        .filter(Booking.booking_status == "CONFIRMED")
        .all()
    )

    return {
        "admin": {
            "id": current_user.id,
            "username": current_user.username,
            "role": current_user.role,
        },
        "platform_statistics": {
            "total_users": total_users,
            "total_events": total_events,
            "total_bookings": total_bookings,
            "total_tickets_sold": sum(
                b.ticket_quantity for b in confirmed_bookings
            ),
            "total_revenue": sum(
                b.total_price for b in confirmed_bookings
            ),
        },
    }


# =========================================================
# USER MANAGEMENT
# =========================================================

@router.get("/users")
def get_all_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    users = db.query(User).order_by(User.id.asc()).all()

    return {
        "total_users": len(users),
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "role": u.role,
                "created_at": u.created_at,
            }
            for u in users
        ],
    }


@router.get("/users/{user_id}")
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "created_at": user.created_at,
    }


@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    role_data: AdminRoleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot change your own admin role",
        )

    old_role = user.role
    user.role = role_data.role

    create_audit_log(
        db=db,
        user_id=current_user.id,
        action="UPDATE_USER_ROLE",
        description=(
            f"Admin changed user {user.id} role "
            f"from {old_role} to {role_data.role}"
        ),
        resource_type="User",
        resource_id=user.id,
        ip_address=request.client.host if request.client else None,
    )

    db.commit()
    db.refresh(user)

    return {
        "message": "User role updated successfully",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
        },
    }


# =========================================================
# EVENT MANAGEMENT
# =========================================================

@router.get("/events")
def get_all_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    events = db.query(Event).order_by(Event.event_date.asc()).all()

    return {
        "total_events": len(events),
        "events": [
            {
                "event_id": e.id,
                "title": e.title,
                "category": e.category,
                "location": e.location,
                "event_date": e.event_date,
                "ticket_price": e.ticket_price,
                "total_tickets": e.total_tickets,
                "available_tickets": e.available_tickets,
                "event_status": e.event_status,
                "organizer_id": e.organizer_id,
            }
            for e in events
        ],
    }


@router.get("/events/{event_id}")
def get_single_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    event = db.query(Event).filter(Event.id == event_id).first()

    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

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
        "created_at": event.created_at,
    }


@router.put("/events/{event_id}/cancel")
def admin_cancel_event(
    event_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    event = db.query(Event).filter(Event.id == event_id).first()

    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.event_status == "CANCELLED":
        raise HTTPException(
            status_code=400,
            detail="Event is already cancelled",
        )

    event.event_status = "CANCELLED"

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
                title="Event Cancelled",
                message=(
                    f'The event "{event.title}" '
                    "has been cancelled by the administrator."
                ),
                type="EVENT_CANCELLED",
                is_read=False,
            )
        )
        notified_users.add(booking.user_id)

    create_audit_log(
        db=db,
        user_id=current_user.id,
        action="CANCEL_EVENT",
        description=f"Admin cancelled event: {event.title}",
        resource_type="Event",
        resource_id=event.id,
        ip_address=request.client.host if request.client else None,
    )

    db.commit()
    db.refresh(event)

    return {
        "message": "Event cancelled successfully",
        "event_id": event.id,
        "event_status": event.event_status,
    }


@router.delete("/events/{event_id}")
def admin_delete_event(
    event_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    event = db.query(Event).filter(Event.id == event_id).first()

    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    booking_count = (
        db.query(Booking)
        .filter(Booking.event_id == event.id)
        .count()
    )

    if booking_count > 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot delete an event that has bookings. "
                "Cancel the event instead."
            ),
        )

    # Save the title before deleting the event.
    event_title = event.title
    event_id_to_log = event.id

    db.delete(event)

    create_audit_log(
        db=db,
        user_id=current_user.id,
        action="DELETE_EVENT",
        description=f"Admin deleted event: {event_title}",
        resource_type="Event",
        resource_id=event_id_to_log,
        ip_address=request.client.host if request.client else None,
    )

    db.commit()

    return {
        "message": "Event deleted successfully",
        "event_id": event_id,
    }


# =========================================================
# BOOKING MANAGEMENT
# =========================================================

@router.get("/bookings")
def get_all_bookings(
    status: str | None = Query(
        None,
        description="Filter by booking status: PENDING, CONFIRMED, or CANCELLED",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    query = db.query(Booking)

    if status:
        status = status.upper()

        if status not in ["PENDING", "CONFIRMED", "CANCELLED"]:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid booking status. "
                    "Use PENDING, CONFIRMED, or CANCELLED."
                ),
            )

        query = query.filter(Booking.booking_status == status)

    bookings = query.order_by(Booking.created_at.desc()).all()

    return {
        "total_bookings": len(bookings),
        "bookings": [
            {
                "booking_id": b.id,
                "user_id": b.user_id,
                "event_id": b.event_id,
                "ticket_quantity": b.ticket_quantity,
                "total_price": b.total_price,
                "booking_status": b.booking_status,
                "created_at": b.created_at,
            }
            for b in bookings
        ],
    }


@router.get("/bookings/{booking_id}")
def get_single_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()

    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")

    return {
        "booking_id": booking.id,
        "user_id": booking.user_id,
        "event_id": booking.event_id,
        "ticket_quantity": booking.ticket_quantity,
        "total_price": booking.total_price,
        "booking_status": booking.booking_status,
        "created_at": booking.created_at,
    }


@router.put("/bookings/{booking_id}/cancel")
def admin_cancel_booking(
    booking_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()

    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.booking_status == "CANCELLED":
        raise HTTPException(
            status_code=400,
            detail="Booking is already cancelled",
        )

    event = db.query(Event).filter(Event.id == booking.event_id).first()

    booking.booking_status = "CANCELLED"

    if event:
        event.available_tickets += booking.ticket_quantity
        if event.available_tickets > event.total_tickets:
            event.available_tickets = event.total_tickets

    db.add(
        Notification(
            user_id=booking.user_id,
            title="Booking Cancelled",
            message=(
                f"Your booking #{booking.id} "
                "has been cancelled by the administrator."
            ),
            type="BOOKING_CANCELLED",
            is_read=False,
        )
    )

    create_audit_log(
        db=db,
        user_id=current_user.id,
        action="CANCEL_BOOKING",
        description=f"Admin cancelled booking #{booking.id}",
        resource_type="Booking",
        resource_id=booking.id,
        ip_address=request.client.host if request.client else None,
    )

    db.commit()
    db.refresh(booking)

    return {
        "message": "Booking cancelled successfully",
        "booking_id": booking.id,
        "booking_status": booking.booking_status,
    }


# =========================================================
# PLATFORM ANALYTICS
# =========================================================

@router.get("/analytics")
def platform_analytics(
    start_date: date | None = Query(
        None,
        description="Start date YYYY-MM-DD",
    ),
    end_date: date | None = Query(
        None,
        description="End date YYYY-MM-DD",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date cannot be after end_date",
        )

    bookings_query = (
        db.query(Booking)
        .filter(Booking.booking_status == "CONFIRMED")
    )

    if start_date:
        bookings_query = bookings_query.filter(
            Booking.created_at >= datetime.combine(
                start_date, datetime.min.time()
            )
        )

    if end_date:
        bookings_query = bookings_query.filter(
            Booking.created_at <= datetime.combine(
                end_date, datetime.max.time()
            )
        )

    confirmed_bookings = bookings_query.all()

    daily_sales = {}
    monthly_trends = {}
    event_stats = {}

    for booking in confirmed_bookings:
        booking_date = booking.created_at.date().isoformat()
        month = booking.created_at.strftime("%Y-%m")
        event_id = booking.event_id

        if booking_date not in daily_sales:
            daily_sales[booking_date] = {
                "date": booking_date,
                "tickets_sold": 0,
                "bookings": 0,
                "revenue": 0,
            }

        daily_sales[booking_date]["tickets_sold"] += booking.ticket_quantity
        daily_sales[booking_date]["bookings"] += 1
        daily_sales[booking_date]["revenue"] += booking.total_price

        if month not in monthly_trends:
            monthly_trends[month] = {
                "month": month,
                "bookings": 0,
                "tickets_sold": 0,
                "revenue": 0,
            }

        monthly_trends[month]["bookings"] += 1
        monthly_trends[month]["tickets_sold"] += booking.ticket_quantity
        monthly_trends[month]["revenue"] += booking.total_price

        if event_id not in event_stats:
            event_stats[event_id] = {
                "event_id": event_id,
                "tickets_sold": 0,
                "bookings": 0,
                "revenue": 0,
            }

        event_stats[event_id]["tickets_sold"] += booking.ticket_quantity
        event_stats[event_id]["bookings"] += 1
        event_stats[event_id]["revenue"] += booking.total_price

    for event_id, stats in event_stats.items():
        event = db.query(Event).filter(Event.id == event_id).first()
        stats["event_title"] = event.title if event else "Unknown Event"

    popular_events = sorted(
        event_stats.values(),
        key=lambda item: item["tickets_sold"],
        reverse=True,
    )

    top_revenue_events = sorted(
        event_stats.values(),
        key=lambda item: item["revenue"],
        reverse=True,
    )

    return {
        "filters": {
            "start_date": start_date,
            "end_date": end_date,
        },
        "summary": {
            "total_bookings": len(confirmed_bookings),
            "total_tickets_sold": sum(
                b.ticket_quantity for b in confirmed_bookings
            ),
            "total_revenue": sum(
                b.total_price for b in confirmed_bookings
            ),
        },
        "daily_ticket_sales": sorted(
            daily_sales.values(),
            key=lambda item: item["date"],
        ),
        "monthly_booking_trends": sorted(
            monthly_trends.values(),
            key=lambda item: item["month"],
        ),
        "most_popular_events": popular_events,
        "top_revenue_events": top_revenue_events,
    }


# =========================================================
# AUDIT LOGS - MODULE 21
# =========================================================

@router.get("/audit-logs")
def get_audit_logs(
    user_id: int | None = Query(None, description="Filter by admin user ID"),
    action: str | None = Query(None, description="Filter by action"),
    resource_type: str | None = Query(
        None, description="Filter by resource type"
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    query = db.query(AuditLog)

    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)

    if action and action.strip():
        query = query.filter(
            AuditLog.action.ilike(f"%{action.strip()}%")
        )

    if resource_type and resource_type.strip():
        query = query.filter(
            AuditLog.resource_type.ilike(
                f"%{resource_type.strip()}%"
            )
        )

    total = query.count()

    logs = (
        query
        .order_by(
            AuditLog.created_at.desc(),
            AuditLog.id.desc(),
        )
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "audit_logs": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "action": log.action,
                "description": log.description,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "ip_address": log.ip_address,
                "created_at": log.created_at,
            }
            for log in logs
        ],
    }
