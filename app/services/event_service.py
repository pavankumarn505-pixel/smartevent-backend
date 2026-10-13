
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

    now = datetime.now(timezone.utc)
    event_date = event.event_date

    # SQLite may return a datetime without timezone information.
    if event_date.tzinfo is None:
        event_date = event_date.replace(tzinfo=timezone.utc)
    else:
        event_date = event_date.astimezone(timezone.utc)

    # Compare calendar dates in UTC.
    today = now.date()
    scheduled_date = event_date.date()

    if scheduled_date > today:
        return "UPCOMING"

    if scheduled_date == today:
        return "ONGOING"

    return "COMPLETED"
