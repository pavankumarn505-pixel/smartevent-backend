from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Event

router = APIRouter(
    prefix="/events",
    tags=["Advanced Event Search"]
)


@router.get("/search")
def search_events(
    category: Optional[str] = Query(default=None),
    min_price: Optional[float] = Query(default=None, ge=0),
    max_price: Optional[float] = Query(default=None, ge=0),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    location: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    # 1. Start with all events
    query = db.query(Event)

    # 2. Filter by category
    if category:
        query = query.filter(
            Event.category.ilike(f"%{category.strip()}%")
        )

    # 3. Filter by minimum price
    if min_price is not None:
        query = query.filter(
            Event.ticket_price >= min_price
        )

    # 4. Filter by maximum price
    if max_price is not None:
        query = query.filter(
            Event.ticket_price <= max_price
        )

    # 5. Validate the date range
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date cannot be after end_date"
        )

    # 6. Filter by starting date
    if start_date:
        query = query.filter(
            Event.event_date >= datetime.combine(
                start_date, time.min
            )
        )

    # 7. Filter by ending date
    if end_date:
        query = query.filter(
            Event.event_date < datetime.combine(
                end_date + timedelta(days=1), time.min
            )
        )

    # 8. Filter by location
    if location:
        query = query.filter(
            Event.location.ilike(f"%{location.strip()}%")
        )

    # 9. Validate the price range
    if (
        min_price is not None
        and max_price is not None
        and min_price > max_price
    ):
        raise HTTPException(
            status_code=400,
            detail="min_price cannot be greater than max_price"
        )

    # 10. Count matching events before pagination
    total = query.count()

    # 11. Sort events by date, then apply pagination
    events = (
        query
        .order_by(Event.event_date.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    # 12. Return search results
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "filters": {
            "category": category,
            "min_price": min_price,
            "max_price": max_price,
            "start_date": (
                start_date.isoformat() if start_date else None
            ),
            "end_date": (
                end_date.isoformat() if end_date else None
            ),
            "location": location
        },
        "events": [
            {
                "id": event.id,
                "title": event.title,
                "description": event.description,
                "category": event.category,
                "location": event.location,
                "event_date": event.event_date,
                "ticket_price": event.ticket_price,
                "available_tickets": event.available_tickets,
                "banner_image": event.banner_image
            }
            for event in events
        ]
    }
