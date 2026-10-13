
# tests/test_payments.py

from datetime import datetime, timedelta

from app import models


def register_user(client, username, role="USER"):
    """Register a user, assign a role, and return an access token."""
    response = client.post(
        "/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "testpass123",
        },
    )
    assert response.status_code in (200, 201), response.text

    # Assign the role in the isolated test database.
    db = client.app.state.TestingSessionLocal()
    try:
        user = (
            db.query(models.User)
            .filter(models.User.username == username)
            .first()
        )
        assert user is not None
        user.role = role
        db.commit()
    finally:
        db.close()

    login_response = client.post(
        "/auth/login",
        json={
            "username": username,
            "password": "testpass123",
        },
    )
    assert login_response.status_code == 200, login_response.text

    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_active_event(client, organizer_headers):
    """Create an event and make it available for booking."""
    response = client.post(
        "/events/",
        headers=organizer_headers,
        json={
            "title": "Payment Test Event",
            "description": "An event for payment tests",
            "category": "Tech",
            "location": "Bengaluru",
            "event_date": (
                datetime.now() + timedelta(days=30)
            ).isoformat(),
            "ticket_price": 500.0,
            "total_tickets": 20,
        },
    )
    assert response.status_code in (200, 201), response.text

    event_id = response.json()["id"]

    db = client.app.state.TestingSessionLocal()
    try:
        event = db.query(models.Event).filter(
            models.Event.id == event_id
        ).first()
        assert event is not None
        event.event_status = "ACTIVE"
        db.commit()
    finally:
        db.close()

    return event_id


def create_booking(client, user_headers, event_id, quantity=2):
    """Create a booking and return its ID."""
    response = client.post(
        "/bookings/",
        headers=user_headers,
        json={
            "event_id": event_id,
            "ticket_quantity": quantity,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def get_db_record(client, model, record_id):
    """Read a record from the isolated test database."""
    db = client.app.state.TestingSessionLocal()
    try:
        return db.query(model).filter(
            model.id == record_id
        ).first()
    finally:
        db.close()


def prepare_booking(client, username="paymentuser"):
    """Create organizer, customer, event, and pending booking."""
    organizer_headers = register_user(
        client, f"{username}_organizer", "ORGANIZER"
    )
    user_headers = register_user(client, username, "USER")

    event_id = create_active_event(client, organizer_headers)
    booking_id = create_booking(client, user_headers, event_id)

    return user_headers, event_id, booking_id


def test_successful_payment_confirms_booking_and_creates_ticket(client):
    user_headers, _, booking_id = prepare_booking(client)

    response = client.post(
        f"/payments/simulate/{booking_id}?outcome=SUCCESS",
        headers=user_headers,
    )

    assert response.status_code == 200, response.text
    payment = response.json()

    assert payment["booking_id"] == booking_id
    assert payment["payment_status"] == "SUCCESS"
    assert payment["payment_method"] == "SIMULATED"
    assert payment["amount"] == 1000.0
    assert payment["transaction_id"].startswith("SIM-")
    assert payment["refund_status"] == "NONE"

    booking = get_db_record(client, models.Booking, booking_id)
    assert booking.booking_status == "CONFIRMED"

    db = client.app.state.TestingSessionLocal()
    try:
        tickets = db.query(models.Ticket).filter(
            models.Ticket.booking_id == booking_id
        ).all()
        assert len(tickets) == 1
    finally:
        db.close()


def test_failed_payment_does_not_confirm_booking(client):
    user_headers, _, booking_id = prepare_booking(
        client, "failedpaymentuser"
    )

    response = client.post(
        f"/payments/simulate/{booking_id}?outcome=FAILED",
        headers=user_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["payment_status"] == "FAILED"

    booking = get_db_record(client, models.Booking, booking_id)
    assert booking.booking_status == "PENDING"


def test_invalid_payment_outcome_returns_400(client):
    user_headers, _, booking_id = prepare_booking(
        client, "invalidpaymentuser"
    )

    response = client.post(
        f"/payments/simulate/{booking_id}?outcome=UNKNOWN",
        headers=user_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Outcome must be SUCCESS or FAILED"
    )


def test_user_cannot_pay_for_another_users_booking(client):
    user_headers, _, booking_id = prepare_booking(
        client, "bookingowner"
    )
    other_user_headers = register_user(client, "otherpaymentuser")

    response = client.post(
        f"/payments/simulate/{booking_id}?outcome=SUCCESS",
        headers=other_user_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Booking not found"

    booking = get_db_record(client, models.Booking, booking_id)
    assert booking.booking_status == "PENDING"


def test_successful_payment_cannot_be_repeated(client):
    user_headers, _, booking_id = prepare_booking(
        client, "duplicatepaymentuser"
    )

    first_response = client.post(
        f"/payments/simulate/{booking_id}?outcome=SUCCESS",
        headers=user_headers,
    )
    assert first_response.status_code == 200, first_response.text

    second_response = client.post(
        f"/payments/simulate/{booking_id}?outcome=SUCCESS",
        headers=user_headers,
    )

    assert second_response.status_code == 400
    assert second_response.json()["detail"] == (
        "Booking is already confirmed"
    )


def test_cancelled_booking_cannot_be_paid(client):
    user_headers, _, booking_id = prepare_booking(
        client, "cancelledpaymentuser"
    )

    cancel_response = client.post(
        f"/bookings/{booking_id}/cancel",
        headers=user_headers,
    )
    assert cancel_response.status_code == 200, cancel_response.text

    payment_response = client.post(
        f"/payments/simulate/{booking_id}?outcome=SUCCESS",
        headers=user_headers,
    )

    assert payment_response.status_code == 400
    assert payment_response.json()["detail"] == (
        "Cancelled bookings cannot be paid"
    )


def test_payment_history_only_contains_current_users_payments(client):
    user_headers, _, booking_id = prepare_booking(
        client, "historypaymentuser"
    )

    payment_response = client.post(
        f"/payments/simulate/{booking_id}?outcome=SUCCESS",
        headers=user_headers,
    )
    assert payment_response.status_code == 200

    other_headers = register_user(client, "historyotheruser")

    response = client.get(
        "/payments/my-payments",
        headers=other_headers,
    )

    assert response.status_code == 200
    assert response.json() == []

    own_response = client.get(
        "/payments/my-payments",
        headers=user_headers,
    )

    assert own_response.status_code == 200
    assert len(own_response.json()) == 1
    assert own_response.json()[0]["booking_id"] == booking_id


def test_cancelling_paid_booking_records_simulated_refund(client):
    user_headers, event_id, booking_id = prepare_booking(
        client, "refundpaymentuser"
    )

    payment_response = client.post(
        f"/payments/simulate/{booking_id}?outcome=SUCCESS",
        headers=user_headers,
    )
    assert payment_response.status_code == 200

    payment_id = payment_response.json()["id"]

    cancel_response = client.post(
        f"/bookings/{booking_id}/cancel",
        headers=user_headers,
    )

    assert cancel_response.status_code == 200, cancel_response.text
    assert cancel_response.json()["booking_status"] == "CANCELLED"

    payment = get_db_record(client, models.Payment, payment_id)

    assert payment.payment_status == "SUCCESS"
    assert payment.refund_status == "REFUNDED"
    assert payment.refund_amount == 1000.0
    assert payment.refund_transaction_id.startswith("SIM-REFUND-")
    assert payment.refunded_at is not None

    event = get_db_record(client, models.Event, event_id)
    assert event.available_tickets == event.total_tickets

    db = client.app.state.TestingSessionLocal()
    try:
        ticket = db.query(models.Ticket).filter(
            models.Ticket.booking_id == booking_id
        ).first()
        assert ticket is None
    finally:
        db.close()


def test_cancelling_unpaid_booking_does_not_record_refund(client):
    user_headers, _, booking_id = prepare_booking(
        client, "unpaidrefunduser"
    )

    cancel_response = client.post(
        f"/bookings/{booking_id}/cancel",
        headers=user_headers,
    )
    assert cancel_response.status_code == 200

    db = client.app.state.TestingSessionLocal()
    try:
        payments = db.query(models.Payment).filter(
            models.Payment.booking_id == booking_id
        ).all()
        assert payments == []
    finally:
        db.close()
