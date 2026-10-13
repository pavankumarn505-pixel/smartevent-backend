
from datetime import datetime, timedelta

from app import models


# =========================================================
# TEST HELPERS
# =========================================================

def register_user(client, username, role="USER"):
    response = client.post(
        "/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "testpass123",
        },
    )
    assert response.status_code in (200, 201), response.text

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

    response = client.post(
        "/auth/login",
        json={
            "username": username,
            "password": "testpass123",
        },
    )
    assert response.status_code == 200, response.text

    return {
        "Authorization": f"Bearer {response.json()['access_token']}"
    }


def create_active_event(client, organizer_headers, title="Test Event"):
    response = client.post(
        "/events/",
        headers=organizer_headers,
        json={
            "title": title,
            "description": "Test event description",
            "category": "Tech",
            "location": "Bengaluru",
            "event_date": (
                datetime.now() + timedelta(days=2)
            ).isoformat(),
            "ticket_price": 500.0,
            "total_tickets": 10,
        },
    )
    assert response.status_code in (200, 201), response.text

    event_id = response.json()["id"]

    db = client.app.state.TestingSessionLocal()
    try:
        event = db.query(models.Event).filter(
            models.Event.id == event_id
        ).first()
        event.event_status = "ACTIVE"
        db.commit()
    finally:
        db.close()

    return event_id


def create_booking(client, user_headers, event_id):
    response = client.post(
        "/bookings/",
        headers=user_headers,
        json={
            "event_id": event_id,
            "ticket_quantity": 2,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_notification(client, user_headers, title="Test Notification"):
    """Insert a notification for the authenticated user."""
    # Get the user ID from the test database using the username
    # represented by the supplied test token is unnecessary here;
    # this helper receives the username explicitly below instead.
    raise NotImplementedError


def insert_notification(client, username, title, message, is_read=False):
    db = client.app.state.TestingSessionLocal()
    try:
        user = db.query(models.User).filter(
            models.User.username == username
        ).first()
        assert user is not None

        notification = models.Notification(
            user_id=user.id,
            title=title,
            message=message,
            type="TEST",
            is_read=is_read,
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification.id
    finally:
        db.close()


def create_coupon(client, admin_headers, code="SAVE10",
                  discount_type="PERCENTAGE", discount_value=10,
                  usage_limit=5):
    response = client.post(
        "/coupons/",
        headers=admin_headers,
        json={
            "coupon_code": code,
            "discount_type": discount_type,
            "discount_value": discount_value,
            "minimum_booking_amount": 100,
            "expiry_date": (
                datetime.now() + timedelta(days=30)
            ).isoformat(),
            "usage_limit": usage_limit,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


# =========================================================
# TICKET TESTS
# =========================================================

def test_user_can_get_own_tickets(client):
    organizer_headers = register_user(
        client, "ticketorganizer", "ORGANIZER"
    )
    user_headers = register_user(client, "ticketowner")

    event_id = create_active_event(client, organizer_headers)
    booking_id = create_booking(client, user_headers, event_id)

    response = client.get(
        "/tickets/my-tickets",
        headers=user_headers,
    )

    assert response.status_code == 200, response.text
    tickets = response.json()

    assert len(tickets) == 1
    assert tickets[0]["booking_id"] == booking_id
    assert tickets[0]["ticket_code"]
    assert "qr_code_url" in tickets[0]


def test_user_cannot_see_another_users_tickets(client):
    organizer_headers = register_user(
        client, "ticketprivacyorganizer", "ORGANIZER"
    )
    first_user_headers = register_user(client, "firstticketuser")
    second_user_headers = register_user(client, "secondticketuser")

    event_id = create_active_event(client, organizer_headers)
    create_booking(client, first_user_headers, event_id)

    response = client.get(
        "/tickets/my-tickets",
        headers=second_user_headers,
    )

    assert response.status_code == 200
    assert response.json() == []


def test_ticket_endpoint_requires_authentication(client):
    response = client.get("/tickets/my-tickets")
    assert response.status_code in (401, 403)


# =========================================================
# NOTIFICATION TESTS
# =========================================================

def test_user_can_list_own_notifications(client):
    headers = register_user(client, "notificationowner")

    insert_notification(
        client,
        "notificationowner",
        "First notification",
        "First test message",
    )
    insert_notification(
        client,
        "notificationowner",
        "Second notification",
        "Second test message",
    )

    response = client.get(
        "/notifications/",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert len(response.json()) == 2
    assert {item["title"] for item in response.json()} == {
        "First notification",
        "Second notification",
    }


def test_user_cannot_see_another_users_notifications(client):
    first_headers = register_user(client, "firstnotifyuser")
    second_headers = register_user(client, "secondnotifyuser")

    insert_notification(
        client,
        "firstnotifyuser",
        "Private notification",
        "This belongs to the first user",
    )

    response = client.get(
        "/notifications/",
        headers=second_headers,
    )

    assert response.status_code == 200
    assert response.json() == []


def test_unread_notification_count(client):
    headers = register_user(client, "unreadnotifyuser")

    insert_notification(
        client,
        "unreadnotifyuser",
        "Unread one",
        "Message one",
        is_read=False,
    )
    insert_notification(
        client,
        "unreadnotifyuser",
        "Unread two",
        "Message two",
        is_read=False,
    )
    insert_notification(
        client,
        "unreadnotifyuser",
        "Already read",
        "Message three",
        is_read=True,
    )

    response = client.get(
        "/notifications/unread-count",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["unread_count"] == 2


def test_user_can_mark_own_notification_as_read(client):
    headers = register_user(client, "markreaduser")

    notification_id = insert_notification(
        client,
        "markreaduser",
        "Please read",
        "Test notification",
        is_read=False,
    )

    response = client.put(
        f"/notifications/{notification_id}/read",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["is_read"] is True

    db = client.app.state.TestingSessionLocal()
    try:
        notification = db.query(models.Notification).filter(
            models.Notification.id == notification_id
        ).first()
        assert notification.is_read is True
    finally:
        db.close()


def test_user_cannot_mark_another_users_notification_as_read(client):
    register_user(client, "notificationprivacyowner")
    other_headers = register_user(client, "notificationprivacyother")

    notification_id = insert_notification(
        client,
        "notificationprivacyowner",
        "Private",
        "Another user's notification",
        is_read=False,
    )

    response = client.put(
        f"/notifications/{notification_id}/read",
        headers=other_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Notification not found"


# =========================================================
# COUPON TESTS
# =========================================================

def test_non_admin_cannot_create_coupon(client):
    user_headers = register_user(client, "couponordinaryuser")

    response = client.post(
        "/coupons/",
        headers=user_headers,
        json={
            "coupon_code": "SAVE10",
            "discount_type": "PERCENTAGE",
            "discount_value": 10,
            "minimum_booking_amount": 0,
            "expiry_date": (
                datetime.now() + timedelta(days=30)
            ).isoformat(),
            "usage_limit": 5,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Only administrators can manage coupons"
    )


def test_admin_can_create_coupon(client):
    admin_headers = register_user(client, "couponadmin", "ADMIN")

    coupon = create_coupon(
        client,
        admin_headers,
        code="  save20  ",
        discount_type="PERCENTAGE",
        discount_value=20,
    )

    assert coupon["coupon_code"] == "SAVE20"
    assert coupon["discount_type"] == "PERCENTAGE"
    assert coupon["discount_value"] == 20
    assert coupon["used_count"] == 0
    assert coupon["is_active"] is True


def test_user_can_validate_percentage_coupon(client):
    admin_headers = register_user(
        client, "percentagecouponadmin", "ADMIN"
    )
    user_headers = register_user(client, "percentagecouponuser")

    create_coupon(
        client,
        admin_headers,
        code="PERCENT20",
        discount_type="PERCENTAGE",
        discount_value=20,
    )

    response = client.post(
        "/coupons/validate",
        headers=user_headers,
        json={
            "coupon_code": " percent20 ",
            "booking_amount": 500,
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()

    assert result["coupon_code"] == "PERCENT20"
    assert result["booking_amount"] == 500
    assert result["discount_amount"] == 100
    assert result["final_amount"] == 400


def test_fixed_coupon_discount_cannot_exceed_booking_amount(client):
    admin_headers = register_user(
        client, "fixedcouponadmin", "ADMIN"
    )
    user_headers = register_user(client, "fixedcouponuser")

    create_coupon(
        client,
        admin_headers,
        code="FIXED1000",
        discount_type="FIXED",
        discount_value=1000,
    )

    response = client.post(
        "/coupons/validate",
        headers=user_headers,
        json={
            "coupon_code": "FIXED1000",
            "booking_amount": 250,
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()

    assert result["discount_amount"] == 250
    assert result["final_amount"] == 0


def test_unknown_coupon_returns_404(client):
    user_headers = register_user(client, "unknowncouponuser")

    response = client.post(
        "/coupons/validate",
        headers=user_headers,
        json={
            "coupon_code": "DOESNOTEXIST",
            "booking_amount": 500,
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Coupon code not found"


def test_coupon_rejects_booking_below_minimum_amount(client):
    admin_headers = register_user(
        client, "minimumcouponadmin", "ADMIN"
    )
    user_headers = register_user(client, "minimumcouponuser")

    create_coupon(
        client,
        admin_headers,
        code="MINIMUM500",
        discount_type="FIXED",
        discount_value=50,
    )

    response = client.post(
        "/coupons/validate",
        headers=user_headers,
        json={
            "coupon_code": "MINIMUM500",
            "booking_amount": 50,
        },
    )

    assert response.status_code == 400
    assert "at least" in response.json()["detail"]


def test_coupon_rejects_usage_limit_reached(client):
    admin_headers = register_user(
        client, "limitcouponadmin", "ADMIN"
    )
    user_headers = register_user(client, "limitcouponuser")

    create_coupon(
        client,
        admin_headers,
        code="ONETIME",
        discount_type="FIXED",
        discount_value=25,
        usage_limit=1,
    )

    db = client.app.state.TestingSessionLocal()
    try:
        coupon = db.query(models.Coupon).filter(
            models.Coupon.coupon_code == "ONETIME"
        ).first()
        coupon.used_count = 1
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/coupons/validate",
        headers=user_headers,
        json={
            "coupon_code": "ONETIME",
            "booking_amount": 500,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "This coupon has reached its usage limit"
    )
