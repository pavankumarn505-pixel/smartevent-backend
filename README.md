# SmartEvent – Event Discovery & Ticket Booking System

SmartEvent is a **FastAPI-based backend API** for discovering events, booking tickets, managing events, and viewing booking analytics.

## Features

* User Registration & Login
* JWT Authentication
* Role-Based Access Control

  * USER
  * ORGANIZER
  * ADMIN
* Event Creation & Management
* Event Search & Category Filtering
* Ticket Booking
* QR Code Tickets
* Notifications
* Stripe Checkout Integration
* Organizer Analytics
* Admin Dashboard & Analytics

## Tech Stack

* **Backend:** Python, FastAPI
* **Database:** SQLite, SQLAlchemy
* **Authentication:** JWT
* **Validation:** Pydantic
* **Payment:** Stripe
* **API Testing:** Swagger UI

## Project Structure

```text
smartevent-backend/
├── app/
│   ├── routers/
│   ├── services/
│   ├── main.py
│   ├── models.py
│   ├── schemas.py
│   ├── auth.py
│   └── database.py
├── qr_codes/
├── .env
├── requirements.txt
└── README.md
```

## Setup

```powershell
cd C:\smartevent-backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create a `.env` file with your JWT and Stripe configuration.

## Run the Project

```powershell
uvicorn app.main:app --reload
```

API:

```text
http://127.0.0.1:8000
```

Swagger Documentation:

```text
http://127.0.0.1:8000/docs
```

## Main API Modules

* `/auth` – Authentication
* `/events` – Event management
* `/bookings` – Ticket bookings
* `/tickets` – QR tickets
* `/notifications` – User notifications
* `/payments` – Stripe checkout
* `/organizer` – Organizer analytics
* `/admin` – Admin management & analytics

## Roles

**USER:** Browse events and book tickets.

**ORGANIZER:** Create/manage events and view event analytics.

**ADMIN:** Manage users, events, bookings, and platform analytics.

## Project Status

SmartEvent backend Phase 1 and Phase 2 features are implemented using FastAPI and SQLAlchemy.
