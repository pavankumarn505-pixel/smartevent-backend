
from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import User, Event, Booking
from app.dependencies import get_current_user


router = APIRouter(
    prefix="/recommendations",
    tags=["Event Recommendations"],
)


def get_popularity_counts(db: Session):
    """Count confirmed bookings for each event."""
    results = (
        db.query(
            Booking.event_id,
            func.count(Booking.id).label("booking_count"),
        )
        .filter(
            Booking.booking_status == "CONFIRMED"
        )
        .group_by(Booking.event_id)
        .all()
    )

    return {
        row.event_id: row.booking_count
        for row in results
    }


@router.get("/")
def get_personalized_recommendations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Recommend available events using booking categories,
    previous locations, and event popularity.
    """

    user_bookings = (
        db.query(Booking)
        .filter(
            Booking.user_id == current_user.id,
            Booking.booking_status.in_(["CONFIRMED", "COMPLETED"]),
        )
        .all()
    )

    booked_event_ids = {
        booking.event_id for booking in user_bookings
    }

    categories = Counter()
    locations = Counter()

    for booking in user_bookings:
        event = booking.event

        if event:
            categories[event.category] += 1

            if event.location:
                locations[event.location.strip().lower()] += 1

    popularity = get_popularity_counts(db)

    events = (
        db.query(Event)
        .filter(
            Event.event_status == "ACTIVE",
            Event.available_tickets > 0,
        )
        .all()
    )

    recommendations = []

    for event in events:
        # Do not recommend an event already booked by the user.
        if event.id in booked_event_ids:
            continue

        category_score = categories.get(event.category, 0)

        location_key = (
            event.location.strip().lower()
            if event.location
            else ""
        )
        location_score = locations.get(location_key, 0)

        popularity_score = popularity.get(event.id, 0)

        score = (
            category_score * 3
            + location_score * 2
            + popularity_score
        )

        recommendations.append(
            {
                "event_id": event.id,
                "title": event.title,
                "description": event.description,
                "category": event.category,
                "location": event.location,
                "event_date": event.event_date,
                "ticket_price": event.ticket_price,
                "available_tickets": event.available_tickets,
                "banner_image": event.banner_image,
                "popularity": popularity_score,
                "recommendation_score": score,
            }
        )

    recommendations.sort(
        key=lambda item: (
            item["recommendation_score"],
            item["popularity"],
        ),
        reverse=True,
    )

    return {
        "message": "Personalized recommendations retrieved successfully",
        "total": len(recommendations),
        "recommendations": recommendations,
    }


@router.get("/popular")
def get_popular_events(
    db: Session = Depends(get_db),
):
    """Return available active events ranked by confirmed bookings."""

    popularity = get_popularity_counts(db)

    events = (
        db.query(Event)
        .filter(
            Event.event_status == "ACTIVE",
            Event.available_tickets > 0,
        )
        .all()
    )

    events.sort(
        key=lambda event: popularity.get(event.id, 0),
        reverse=True,
    )

    return {
        "message": "Popular events retrieved successfully",
        "total": len(events),
        "events": [
            {
                "event_id": event.id,
                "title": event.title,
                "category": event.category,
                "location": event.location,
                "event_date": event.event_date,
                "ticket_price": event.ticket_price,
                "available_tickets": event.available_tickets,
                "popularity": popularity.get(event.id, 0),
            }
            for event in events
        ],
    }


@router.get("/similar/{event_id}")
def get_similar_events(
    event_id: int,
    db: Session = Depends(get_db),
):
    """Find available events with a similar category or location."""

    target_event = (
        db.query(Event)
        .filter(Event.id == event_id)
        .first()
    )

    if target_event is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail="Event not found",
        )

    events = (
        db.query(Event)
        .filter(
            Event.id != event_id,
            Event.event_status == "ACTIVE",
            Event.available_tickets > 0,
        )
        .all()
    )

    popularity = get_popularity_counts(db)

    similar_events = []

    for event in events:
        same_category = (
            event.category.lower() == target_event.category.lower()
        )

        same_location = (
            event.location.strip().lower()
            == target_event.location.strip().lower()
        )

        if not same_category and not same_location:
            continue

        score = (
            (3 if same_category else 0)
            + (2 if same_location else 0)
            + popularity.get(event.id, 0)
        )

        similar_events.append(
            {
                "event_id": event.id,
                "title": event.title,
                "category": event.category,
                "location": event.location,
                "event_date": event.event_date,
                "ticket_price": event.ticket_price,
                "available_tickets": event.available_tickets,
                "popularity": popularity.get(event.id, 0),
                "similarity_score": score,
            }
        )

    similar_events.sort(
        key=lambda item: item["similarity_score"],
        reverse=True,
    )

    return {
        "message": "Similar events retrieved successfully",
        "total": len(similar_events),
        "events": similar_events,
    }
