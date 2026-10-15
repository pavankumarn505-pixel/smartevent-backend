from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    ConfigDict,
)


# =========================================================
# USER SCHEMAS
# =========================================================

class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=72)


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str


# =========================================================
# USER PROFILE SCHEMAS - MODULE 22
# =========================================================

class UserProfileUpdate(BaseModel):
    """
    Fields a logged-in user can update in their profile.
    All fields are optional so users can update individual fields.
    """

    username: str | None = Field(
        default=None,
        min_length=3,
        max_length=50,
    )

    email: EmailStr | None = None

    full_name: str | None = Field(
        default=None,
        max_length=150,
    )

    phone: str | None = Field(
        default=None,
        max_length=20,
    )


class UserProfileResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: str
    full_name: str | None = None
    phone: str | None = None
    profile_picture: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProfilePictureResponse(BaseModel):
    message: str
    profile_picture: str


class BookingSummaryResponse(BaseModel):
    """
    Summary of bookings belonging to the logged-in user.
    """

    total_bookings: int = 0
    confirmed_bookings: int = 0
    pending_bookings: int = 0
    cancelled_bookings: int = 0
    total_tickets: int = 0
    total_spent: float = 0.0


# =========================================================
# EVENT SCHEMAS
# =========================================================

class EventCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: str | None = None

    category: Literal["Music", "Tech", "Sports", "Business"]

    location: str = Field(..., min_length=2, max_length=255)
    event_date: datetime
    ticket_price: float = Field(..., ge=0)
    banner_image: str | None = None
    total_tickets: int = Field(..., gt=0)


class EventUpdate(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=3,
        max_length=200,
    )

    description: str | None = None

    category: Literal[
        "Music",
        "Tech",
        "Sports",
        "Business",
    ] | None = None

    location: str | None = Field(
        default=None,
        min_length=2,
        max_length=255,
    )

    event_date: datetime | None = None
    ticket_price: float | None = Field(default=None, ge=0)
    banner_image: str | None = None
    total_tickets: int | None = Field(default=None, gt=0)


class EventResponse(BaseModel):
    id: int
    title: str
    description: str | None
    category: str
    location: str
    event_date: datetime
    ticket_price: float
    banner_image: str | None
    total_tickets: int
    available_tickets: int
    organizer_id: int | None
    event_status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# BOOKING SCHEMAS
# =========================================================

class BookingCreate(BaseModel):
    event_id: int = Field(..., gt=0)
    ticket_quantity: int = Field(..., gt=0)

    coupon_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )


class BookingResponse(BaseModel):
    id: int
    user_id: int
    event_id: int
    ticket_quantity: int
    total_price: float
    booking_status: str
    created_at: datetime

    # Module 13: Coupon discount details
    coupon_id: int | None = None
    discount_amount: float = 0.0
    final_amount: float | None = None

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# TICKET SCHEMA
# =========================================================

class TicketResponse(BaseModel):
    id: int
    booking_id: int
    ticket_code: str
    qr_code_url: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# NOTIFICATION SCHEMA
# =========================================================

class NotificationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    type: str
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# ADMIN SCHEMAS
# =========================================================

class AdminRoleUpdate(BaseModel):
    role: Literal["USER", "ORGANIZER", "ADMIN"]


# =========================================================
# PAYMENT SCHEMAS - MODULE 12 AND MODULE 14
# =========================================================

class PaymentCreate(BaseModel):
    booking_id: int = Field(..., gt=0)
    payment_method: Literal["SIMULATED"] = "SIMULATED"


class PaymentResponse(BaseModel):
    id: int
    booking_id: int
    payment_method: str
    payment_status: str
    transaction_id: str | None = None
    amount: float
    created_at: datetime

    # Module 14: Simulated refund tracking
    refund_status: str = "NONE"
    refund_amount: float = 0.0
    refund_transaction_id: str | None = None
    refunded_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# COUPON SCHEMAS - MODULE 13
# =========================================================

class CouponCreate(BaseModel):
    coupon_code: str = Field(
        ...,
        min_length=3,
        max_length=50,
    )

    discount_type: Literal["PERCENTAGE", "FIXED"]
    discount_value: float = Field(..., gt=0)

    minimum_booking_amount: float = Field(
        default=0,
        ge=0,
    )

    expiry_date: datetime
    usage_limit: int = Field(..., gt=0)


class CouponResponse(BaseModel):
    id: int
    coupon_code: str
    discount_type: str
    discount_value: float
    minimum_booking_amount: float
    expiry_date: datetime
    usage_limit: int
    used_count: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CouponValidateRequest(BaseModel):
    coupon_code: str = Field(
        ...,
        min_length=1,
        max_length=50,
    )

    booking_amount: float = Field(..., gt=0)


class CouponValidateResponse(BaseModel):
    coupon_code: str
    discount_type: str
    discount_value: float
    booking_amount: float
    discount_amount: float
    final_amount: float
    message: str
