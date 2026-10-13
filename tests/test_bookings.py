
from datetime import datetime, timedelta, timezone

from app.main import app
from app.database import get_db
from app.models import User, Event, Booking, Ticket
from app.dependencies import get_current_user


def register_and_login(client, username, password="TestPass123"):
    response = client.post(
        "/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": password,
        },
    )
    assert response.status_code == 201, response.text

    response = client.post(
        "/auth/token",
        data={
            "username": username,
            "password": password,
        },
    )
    assert response.status_code == 200, response.text

    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_active_event(client, headers, total_tickets=10):
    event_date = datetime.now(timezone.utc) + timedelta(days=10)

    payload = {
        "title": "Booking Test Event",
        "description": "Event for booking tests",
        "category": "Tech",
        "location": "Bengaluru",
        "event_date": event_date.isoformat(),
        "ticket_price": 100,
        "total_tickets": total_tickets,
    }

    # Create the event through the API as an organizer.
    response = client.post(
        "/events/",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 201, response.text
    event_id = response.json()["id"]

    # The booking endpoint requires event_status == "ACTIVE".
    # Update only the test database record.
    TestingSessionLocal = app.state.TestingSessionLocal
    db = TestingSessionLocal()
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        assert event is not None
        event.event_status = "ACTIVE"
        db.commit()
    finally:
        db.close()

    return event_id


def make_organizer(client, username):
    headers = register_and_login(client, username)

    TestingSessionLocal = app.state.TestingSessionLocal
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        assert user is not None
        user.role = "ORGANIZER"
        db.commit()
    finally:
        db.close()

    # Log in again so the token is issued after the role change.
    response = client.post(
        "/auth/token",
        data={
            "username": username,
            "password": "TestPass123",
        },
    )
    assert response.status_code == 200, response.text

    return {
        "Authorization": f"Bearer {response.json()['access_token']}"
    }


def test_user_can_create_booking(client):
    organizer_headers = make_organizer(client, "organizer_booking1")
    event_id = create_active_event(client, organizer_headers)

    user_headers = register_and_login(client, "booking_user1")

    response = client.post(
        "/bookings/",
        json={"event_id": event_id, "ticket_quantity": 2},
        headers=user_headers,
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["event_id"] == event_id
    assert data["ticket_quantity"] == 2
    assert data["total_price"] == 200
    assert data["booking_status"] == "PENDING"


def test_booking_reduces_available_tickets(client):
    organizer_headers = make_organizer(client, "organizer_booking2")
    event_id = create_active_event(client, organizer_headers, total_tickets=5)

    user_headers = register_and_login(client, "booking_user2")

    response = client.post(
        "/bookings/",
        json={"event_id": event_id, "ticket_quantity": 2},
        headers=user_headers,
    )
    assert response.status_code == 201, response.text

    db = app.state.TestingSessionLocal()
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        assert event.available_tickets == 3
    finally:
        db.close()


def test_booking_rejected_when_tickets_insufficient(client):
    organizer_headers = make_organizer(client, "organizer_booking3")
    event_id = create_active_event(client, organizer_headers, total_tickets=2)

    user_headers = register_and_login(client, "booking_user3")

    response = client.post(
        "/bookings/",
        json={"event_id": event_id, "ticket_quantity": 3},
        headers=user_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Not enough tickets available"


def test_booking_rejects_zero_quantity(client):
    organizer_headers = make_organizer(client, "organizer_booking4")
    event_id = create_active_event(client, organizer_headers)

    user_headers = register_and_login(client, "booking_user4")

    response = client.post(
        "/bookings/",
        json={"event_id": event_id, "ticket_quantity": 0},
        headers=user_headers,
    )

    # Pydantic validates gt=0 before the route executes.
    assert response.status_code == 422


def test_booking_creates_ticket(client):
    organizer_headers = make_organizer(client, "organizer_booking5")
    event_id = create_active_event(client, organizer_headers)

    user_headers = register_and_login(client, "booking_user5")

    response = client.post(
        "/bookings/",
        json={"event_id": event_id, "ticket_quantity": 1},
        headers=user_headers,
    )
    assert response.status_code == 201, response.text
    booking_id = response.json()["id"]

    db = app.state.TestingSessionLocal()
    try:
        ticket = db.query(Ticket).filter(
            Ticket.booking_id == booking_id
        ).first()

        assert ticket is not None
        assert ticket.ticket_code
    finally:
        db.close()


def test_user_can_view_own_bookings(client):
    organizer_headers = make_organizer(client, "organizer_booking6")
    event_id = create_active_event(client, organizer_headers)

    user_headers = register_and_login(client, "booking_user6")

    create_response = client.post(
        "/bookings/",
        json={"event_id": event_id, "ticket_quantity": 1},
        headers=user_headers,
    )
    assert create_response.status_code == 201, create_response.text

    response = client.get(
        "/bookings/my-bookings",
        headers=user_headers,
    )

    assert response.status_code == 200, response.text
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == create_response.json()["id"]


def test_user_cannot_cancel_another_users_booking(client):
    organizer_headers = make_organizer(client, "organizer_booking7")
    event_id = create_active_event(client, organizer_headers)

    first_user_headers = register_and_login(client, "booking_owner7")
    second_user_headers = register_and_login(client, "booking_other7")

    booking_response = client.post(
        "/bookings/",
        json={"event_id": event_id, "ticket_quantity": 1},
        headers=first_user_headers,
    )
    assert booking_response.status_code == 201, booking_response.text
    booking_id = booking_response.json()["id"]

    response = client.post(
        f"/bookings/{booking_id}/cancel",
        headers=second_user_headers,
    )

    # The endpoint hides bookings owned by other users.
    assert response.status_code == 404
    assert response.json()["detail"] == "Booking not found"


def test_cancellation_restores_available_tickets(client):
    organizer_headers = make_organizer(client, "organizer_booking8")
    event_id = create_active_event(client, organizer_headers, total_tickets=5)

    user_headers = register_and_login(client, "booking_user8")

    booking_response = client.post(
        "/bookings/",
        json={"event_id": event_id, "ticket_quantity": 2},
        headers=user_headers,
    )
    assert booking_response.status_code == 201, booking_response.text
    booking_id = booking_response.json()["id"]

    cancel_response = client.post(
        f"/bookings/{booking_id}/cancel",
        headers=user_headers,
    )
    assert cancel_response.status_code == 200, cancel_response.text
    assert cancel_response.json()["booking_status"] == "CANCELLED"

    db = app.state.TestingSessionLocal()
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        assert event.available_tickets == 5

        ticket = db.query(Ticket).filter(
            Ticket.booking_id == booking_id
        ).first()
        assert ticket is None
    finally:
        db.close()
