from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


# =========================================================
# USER SCHEMAS
# =========================================================

class UserRegister(BaseModel):
    username: str = Field(
        ...,
        min_length=3,
        max_length=50
    )

    email: EmailStr

    password: str = Field(
        ...,
        min_length=6,
        max_length=72
    )


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


# =========================================================
# EVENT SCHEMAS
# =========================================================

class EventCreate(BaseModel):

    title: str = Field(
        ...,
        min_length=3,
        max_length=200
    )

    description: str | None = None

    category: Literal[
        "Music",
        "Tech",
        "Sports",
        "Business"
    ]

    location: str = Field(
        ...,
        min_length=2,
        max_length=255
    )

    event_date: datetime

    ticket_price: float = Field(
        ...,
        ge=0
    )

    banner_image: str | None = None

    total_tickets: int = Field(
        ...,
        gt=0
    )


# =========================================================
# EVENT UPDATE
# =========================================================

class EventUpdate(BaseModel):

    title: str | None = Field(
        None,
        min_length=3,
        max_length=200
    )

    description: str | None = None

    category: Literal[
        "Music",
        "Tech",
        "Sports",
        "Business"
    ] | None = None

    location: str | None = Field(
        None,
        min_length=2,
        max_length=255
    )

    event_date: datetime | None = None

    ticket_price: float | None = Field(
        None,
        ge=0
    )

    banner_image: str | None = None

    total_tickets: int | None = Field(
        None,
        gt=0
    )


# =========================================================
# EVENT RESPONSE
# =========================================================

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

    class Config:
        from_attributes = True


# =========================================================
# BOOKING SCHEMAS
# =========================================================

class BookingCreate(BaseModel):

    event_id: int = Field(
        ...,
        gt=0
    )

    ticket_quantity: int = Field(
        ...,
        gt=0
    )


class BookingResponse(BaseModel):

    id: int

    user_id: int

    event_id: int

    ticket_quantity: int

    total_price: float

    booking_status: str

    created_at: datetime

    class Config:
        from_attributes = True


# =========================================================
# TICKET SCHEMA
# =========================================================

class TicketResponse(BaseModel):

    id: int

    booking_id: int

    ticket_code: str

    qr_code_url: str | None

    created_at: datetime

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


# =========================================================
# ADMIN SCHEMAS
# =========================================================

class AdminRoleUpdate(BaseModel):

    role: Literal[
        "USER",
        "ORGANIZER",
        "ADMIN"
    ]