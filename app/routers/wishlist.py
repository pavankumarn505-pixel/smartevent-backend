
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User, Event, Wishlist

router = APIRouter(
    prefix="/wishlist",
    tags=["Wishlist"]
)


@router.post("/{event_id}")
def add_to_wishlist(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    event = db.query(Event).filter(Event.id == event_id).first()

    if not event:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    existing_item = db.query(Wishlist).filter(
        Wishlist.user_id == current_user.id,
        Wishlist.event_id == event_id
    ).first()

    if existing_item:
        raise HTTPException(
            status_code=409,
            detail="Event is already in your wishlist"
        )

    wishlist_item = Wishlist(
        user_id=current_user.id,
        event_id=event_id
    )

    db.add(wishlist_item)
    db.commit()
    db.refresh(wishlist_item)

    return {
        "message": "Event added to wishlist successfully",
        "wishlist_id": wishlist_item.id,
        "event_id": wishlist_item.event_id
    }


@router.get("/")
def get_my_wishlist(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    wishlist_items = (
        db.query(Wishlist, Event)
        .join(Event, Wishlist.event_id == Event.id)
        .filter(Wishlist.user_id == current_user.id)
        .order_by(Wishlist.created_at.desc())
        .all()
    )

    return [
        {
            "wishlist_id": item.id,
            "event_id": event.id,
            "title": event.title,
            "category": event.category,
            "location": event.location,
            "event_date": event.event_date,
            "ticket_price": event.ticket_price,
            "created_at": item.created_at
        }
        for item, event in wishlist_items
    ]


@router.delete("/{event_id}")
def remove_from_wishlist(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    wishlist_item = db.query(Wishlist).filter(
        Wishlist.user_id == current_user.id,
        Wishlist.event_id == event_id
    ).first()

    if not wishlist_item:
        raise HTTPException(
            status_code=404,
            detail="Event not found in your wishlist"
        )

    db.delete(wishlist_item)
    db.commit()

    return {
        "message": "Event removed from wishlist successfully"
    }
