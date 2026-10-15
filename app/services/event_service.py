from datetime import datetime, timezone

from ..models import Event


def update_event_status(event: Event) -> str:
    """
    Automatically determine an event's status.

    Rules:
    - CANCELLED stays CANCELLED.
    - Future calendar date = UPCOMING.
    - Today's calendar date = ONGOING.
    - Past calendar date = COMPLETED.
    """

    # A cancelled event must never be automatically reactivated.
    if event.event_status == "CANCELLED":
        return "CANCELLED"

    # Get the event date.
    event_date = event.event_date

    # Handle missing event dates safely.
    if event_date is None:
        raise ValueError("Event date cannot be None.")

    # Get the current UTC time.
    now = datetime.now(timezone.utc)

    # SQLite may return a datetime without timezone information.
    if event_date.tzinfo is None:
        event_date = event_date.replace(tzinfo=timezone.utc)
    else:
        event_date = event_date.astimezone(timezone.utc)

    # Compare calendar dates in UTC.
    today = now.date()
    scheduled_date = event_date.date()

    # Future event.
    if scheduled_date > today:
        return "UPCOMING"

    # Event scheduled for today.
    if scheduled_date == today:
        return "ONGOING"

    # Event date has passed.
    return "COMPLETED"
