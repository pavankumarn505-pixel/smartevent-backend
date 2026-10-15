from datetime import datetime, date, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from ..database import get_db
from ..dependencies import get_current_user
from ..models import User, Event, Booking
from ..services.chatbot_service import (
    classify_query,
    generate_support_reply,
)

router = APIRouter(prefix="/chatbot", tags=["AI Chatbot"])


class ChatbotRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class ChatbotResponse(BaseModel):
    intent: str
    reply: str
    data: list[dict] = []


@router.post("/chat", response_model=ChatbotResponse)
def chat_with_assistant(
    request: ChatbotRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    message = request.message.strip()

    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    try:
        query_info = classify_query(message)
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="The AI service is temporarily unavailable.",
        )

    intent = query_info["intent"]

    # 1. Event discovery
    if intent == "events":
        query = db.query(Event)

        query = query.filter(
            Event.event_status.notin_(["CANCELLED", "COMPLETED"])
        )

        category = query_info.get("category")
        location = query_info.get("location")

        if category:
            query = query.filter(Event.category.ilike(f"%{category}%"))

        if location:
            query = query.filter(Event.location.ilike(f"%{location}%"))

        start_date = query_info.get("start_date")
        end_date = query_info.get("end_date")

        if start_date:
            try:
                start = date.fromisoformat(start_date)
                query = query.filter(
                    Event.event_date >= datetime.combine(start, time.min)
                )
            except ValueError:
                pass

        if end_date:
            try:
                end = date.fromisoformat(end_date)
                query = query.filter(
                    Event.event_date < datetime.combine(
                        end + timedelta(days=1), time.min
                    )
                )
            except ValueError:
                pass

        events = query.order_by(Event.event_date.asc()).limit(10).all()

        results = [
            {
                "id": event.id,
                "title": event.title,
                "category": event.category,
                "location": event.location,
                "event_date": (
                    event.event_date.isoformat()
                    if event.event_date else None
                ),
                "ticket_price": float(event.ticket_price),
                "available_tickets": event.available_tickets,
                "event_status": event.event_status,
            }
            for event in events
        ]

        return ChatbotResponse(
            intent="events",
            reply=(
                f"I found {len(results)} matching event(s)."
                if results
                else "I couldn't find matching events. Try another category, "
                     "location, or date range."
            ),
            data=results,
        )

    # 2. The logged-in user's bookings only
    if intent == "bookings":
        bookings = (
            db.query(Booking)
            .filter(Booking.user_id == current_user.id)
            .order_by(Booking.created_at.desc())
            .limit(20)
            .all()
        )

        results = [
            {
                "booking_id": booking.id,
                "event_id": booking.event_id,
                "event_title": (
                    booking.event.title if booking.event else None
                ),
                "ticket_quantity": booking.ticket_quantity,
                "booking_status": booking.booking_status,
                "total_price": (
                    float(booking.final_amount)
                    if booking.final_amount is not None
                    else float(booking.total_price)
                ),
                "created_at": (
                    booking.created_at.isoformat()
                    if booking.created_at else None
                ),
            }
            for booking in bookings
        ]

        return ChatbotResponse(
            intent="bookings",
            reply=(
                f"You have {len(results)} booking record(s) in your recent "
                "booking history."
                if results
                else "I couldn't find any bookings for your account."
            ),
            data=results,
        )

    # 3. General ticket support
    try:
        reply = generate_support_reply(message)
    except Exception:
        reply = (
            "Please check your booking details and booking status. "
            "If you have a payment or missing-ticket issue, contact "
            "SmartEvent support with your booking reference."
        )

    return ChatbotResponse(
        intent="support",
        reply=reply,
        data=[],
    )