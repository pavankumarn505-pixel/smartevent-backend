from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Notification, User, Booking, Event
from ..schemas import NotificationResponse
from ..dependencies import get_current_user


router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"]
)


# =========================================================
# GET MY NOTIFICATIONS
# =========================================================

@router.get(
    "/",
    response_model=list[NotificationResponse]
)
def get_my_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    notifications = (
        db.query(Notification)
        .filter(
            Notification.user_id == current_user.id
        )
        .order_by(
            Notification.created_at.desc()
        )
        .all()
    )

    return notifications


# =========================================================
# GET UNREAD COUNT
# =========================================================

@router.get("/unread-count")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    count = (
        db.query(Notification)
        .filter(
            Notification.user_id == current_user.id,
            Notification.is_read == False
        )
        .count()
    )

    return {
        "unread_count": count
    }


# =========================================================
# MARK NOTIFICATION AS READ
# =========================================================

@router.put("/{notification_id}/read")
def mark_notification_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id == current_user.id
        )
        .first()
    )

    if notification is None:
        raise HTTPException(
            status_code=404,
            detail="Notification not found"
        )

    notification.is_read = True

    db.commit()
    db.refresh(notification)

    return {
        "message": "Notification marked as read",
        "notification_id": notification.id,
        "is_read": notification.is_read
    }


# =========================================================
# CREATE EVENT REMINDER
# =========================================================

@router.post("/event-reminders")
def create_event_reminders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    now = datetime.now()

    reminder_time = now + timedelta(days=1)

    bookings = (
        db.query(Booking)
        .join(Event, Booking.event_id == Event.id)
        .filter(
            Booking.user_id == current_user.id,
            Booking.booking_status == "CONFIRMED",
            Event.event_date <= reminder_time,
            Event.event_date >= now
        )
        .all()
    )

    created_notifications = []

    for booking in bookings:

        event = booking.event

        # Check whether reminder already exists
        existing_notification = (
            db.query(Notification)
            .filter(
                Notification.user_id == current_user.id,
                Notification.type == "EVENT_REMINDER",
                Notification.message.like(
                    f"%{event.title}%"
                )
            )
            .first()
        )

        if existing_notification:
            continue

        notification = Notification(
            user_id=current_user.id,
            title="Event Reminder",
            message=(
                f"Reminder: Your event "
                f"'{event.title}' is happening soon."
            ),
            type="EVENT_REMINDER",
            is_read=False
        )

        db.add(notification)

        created_notifications.append(
            event.title
        )

    db.commit()

    return {
        "message": "Event reminders processed",
        "created_notifications": created_notifications
    }