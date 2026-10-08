from datetime import datetime, timezone

from ..models import Event


def update_event_status(event: Event) -> str:
    """
    Automatically determine the current status of an event.

    Rules:
    - CANCELLED stays CANCELLED
    - Future event = UPCOMING
    - Event happening today = ONGOING
    - Past event = COMPLETED
    """

    # Cancelled events should never change automatically
    if event.event_status == "CANCELLED":
        return "CANCELLED"

    now = datetime.now(timezone.utc)

    # Handle SQLite datetimes that may be timezone-naive
    event_date = event.event_date

    if event_date.tzinfo is None:
        event_date = event_date.replace(tzinfo=timezone.utc)

    # Future event
    if event_date.date() > now.date():
        return "UPCOMING"

    # Event is happening today
    if event_date.date() == now.date():
        return "ONGOING"

    # Event date has passed
    return "COMPLETED"