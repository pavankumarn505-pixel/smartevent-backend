
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import engine, Base
from . import models

from .routers import (
    auth,
    users,
    events,
    bookings,
    tickets,
    notifications,
    payments,
    organizer,
    admin,
    coupons,
    availability,
    recommendations,
    wishlist,
    event_search,
    chatbot,  # Module 24: AI Chatbot Assistant
)


# =========================================================
# CREATE REQUIRED DIRECTORIES
# =========================================================

Path("qr_codes").mkdir(parents=True, exist_ok=True)
Path("profile_pictures").mkdir(parents=True, exist_ok=True)


# =========================================================
# CREATE DATABASE TABLES
# =========================================================

Base.metadata.create_all(bind=engine)


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="SmartEvent API",
    description="Event Discovery and Ticket Booking System",
    version="1.0.0",
)


# =========================================================
# QR CODE STATIC FILES
# =========================================================

app.mount(
    "/qr_codes",
    StaticFiles(directory="qr_codes"),
    name="qr_codes",
)


# =========================================================
# PROFILE PICTURE STATIC FILES
# =========================================================

app.mount(
    "/profile_pictures",
    StaticFiles(directory="profile_pictures"),
    name="profile_pictures",
)


# =========================================================
# CORS CONFIGURATION
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# REGISTER ROUTERS
# =========================================================

# Authentication
app.include_router(auth.router)

# User profiles and booking summaries
app.include_router(users.router)

# Event discovery and management
app.include_router(events.router)

# Booking management
app.include_router(bookings.router)

# Ticket management
app.include_router(tickets.router)

# Notifications
app.include_router(notifications.router)

# Payments
app.include_router(payments.router)

# Organizer features
app.include_router(organizer.router)

# Admin features and analytics
app.include_router(admin.router)

# Coupons and discounts
app.include_router(coupons.router)

# Module 18: Real-Time Ticket Availability
app.include_router(availability.router)

# Module 19: Personalized Event Recommendations
app.include_router(recommendations.router)

# Module 20: Wishlist
app.include_router(wishlist.router)

# Module 23: Advanced Search & Smart Filters
app.include_router(event_search.router)

# Module 24: AI Chatbot Assistant
app.include_router(chatbot.router)


# =========================================================
# HOME
# =========================================================

@app.get("/")
def home():
    return {
        "message": "Welcome to SmartEvent API",
        "status": "Backend is running",
    }


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health_check():
    return {
        "status": "OK",
    }
