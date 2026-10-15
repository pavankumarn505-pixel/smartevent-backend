from pathlib import Path
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
)
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models import User, Booking
from ..schemas import (
    UserProfileUpdate,
    UserProfileResponse,
    ProfilePictureResponse,
    BookingSummaryResponse,
)


router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


# =========================================================
# PROFILE PICTURE CONFIGURATION
# =========================================================

PROFILE_PICTURE_DIR = Path("profile_pictures")
PROFILE_PICTURE_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


# =========================================================
# VIEW MY PROFILE
# GET /users/me
# =========================================================

@router.get(
    "/me",
    response_model=UserProfileResponse,
)
def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    return current_user


# =========================================================
# UPDATE MY PROFILE
# PUT /users/me
# =========================================================

@router.put(
    "/me",
    response_model=UserProfileResponse,
)
def update_my_profile(
    profile_data: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    update_data = profile_data.model_dump(exclude_unset=True)

    for field in ("username", "email"):
        if field in update_data and update_data[field] is None:
            raise HTTPException(
                status_code=400,
                detail=f"{field} cannot be empty.",
            )

    if update_data.get("username") is not None:
        existing_user = (
            db.query(User)
            .filter(
                User.username == update_data["username"],
                User.id != current_user.id,
            )
            .first()
        )

        if existing_user:
            raise HTTPException(
                status_code=409,
                detail="Username already exists.",
            )

    if update_data.get("email") is not None:
        update_data["email"] = str(update_data["email"])

        existing_user = (
            db.query(User)
            .filter(
                User.email == update_data["email"],
                User.id != current_user.id,
            )
            .first()
        )

        if existing_user:
            raise HTTPException(
                status_code=409,
                detail="Email already exists.",
            )

    for field, value in update_data.items():
        setattr(current_user, field, value)

    try:
        db.commit()
        db.refresh(current_user)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to update profile.",
        )

    return current_user


# =========================================================
# UPLOAD PROFILE PICTURE
# POST /users/me/profile-picture
# =========================================================

@router.post(
    "/me/profile-picture",
    response_model=ProfilePictureResponse,
)
async def upload_profile_picture(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    extension = ALLOWED_IMAGE_TYPES.get(file.content_type or "")

    if extension is None:
        raise HTTPException(
            status_code=400,
            detail="Only JPEG, PNG, and WEBP images are allowed.",
        )

    contents = await file.read(MAX_IMAGE_SIZE + 1)

    if not contents:
        raise HTTPException(
            status_code=400,
            detail="The uploaded image is empty.",
        )

    if len(contents) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Image size must not exceed 5 MB.",
        )

    valid_signature = (
        extension == ".jpg"
        and contents.startswith(b"\xff\xd8\xff")
    ) or (
        extension == ".png"
        and contents.startswith(b"\x89PNG\r\n\x1a\n")
    ) or (
        extension == ".webp"
        and len(contents) >= 12
        and contents.startswith(b"RIFF")
        and contents[8:12] == b"WEBP"
    )

    if not valid_signature:
        raise HTTPException(
            status_code=400,
            detail="The file content does not match the image type.",
        )

    filename = f"{current_user.id}_{uuid4().hex}{extension}"
    destination = PROFILE_PICTURE_DIR / filename

    try:
        destination.write_bytes(contents)

        current_user.profile_picture = (
            f"/profile_pictures/{filename}"
        )

        db.commit()
        db.refresh(current_user)

    except Exception:
        db.rollback()

        if destination.exists():
            destination.unlink()

        raise HTTPException(
            status_code=500,
            detail="Unable to save profile picture.",
        )

    return ProfilePictureResponse(
        message="Profile picture uploaded successfully.",
        profile_picture=current_user.profile_picture,
    )


# =========================================================
# MY BOOKING SUMMARY
# GET /users/me/booking-summary
# =========================================================

@router.get(
    "/me/booking-summary",
    response_model=BookingSummaryResponse,
)
def get_my_booking_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bookings = (
        db.query(Booking)
        .filter(Booking.user_id == current_user.id)
        .all()
    )

    confirmed_statuses = {"CONFIRMED", "COMPLETED", "SUCCESS"}
    pending_statuses = {"PENDING"}
    cancelled_statuses = {"CANCELLED", "CANCELED", "REFUNDED"}

    confirmed = 0
    pending = 0
    cancelled = 0
    total_tickets = 0
    total_spent = 0.0

    for booking in bookings:
        status = (booking.booking_status or "").upper()

        if status in confirmed_statuses:
            confirmed += 1
            total_tickets += booking.ticket_quantity

            amount = (
                booking.final_amount
                if booking.final_amount is not None
                else booking.total_price
            )
            total_spent += float(amount or 0)

        elif status in pending_statuses:
            pending += 1

        elif status in cancelled_statuses:
            cancelled += 1

    return BookingSummaryResponse(
        total_bookings=len(bookings),
        confirmed_bookings=confirmed,
        pending_bookings=pending,
        cancelled_bookings=cancelled,
        total_tickets=total_tickets,
        total_spent=round(total_spent, 2),
    )
