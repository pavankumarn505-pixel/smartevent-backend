from app.models import Wishlist, User


def create_user_and_token(client):
    """Register, promote to ORGANIZER, and log in a test user."""

    response = client.post(
        "/auth/register",
        json={
            "username": "wishlistorganizer",
            "email": "wishlistorganizer@example.com",
            "password": "TestPass123!",
        },
    )

    assert response.status_code == 201, response.text

    # Promote the test account in the isolated test database.
    TestingSessionLocal = client.app.state.TestingSessionLocal

    db = TestingSessionLocal()
    try:
        user = (
            db.query(User)
            .filter(User.username == "wishlistorganizer")
            .first()
        )

        assert user is not None
        user.role = "ORGANIZER"
        db.commit()
    finally:
        db.close()

    # Log in after promotion so the JWT contains the updated role.
    login_response = client.post(
        "/auth/login",
        json={
            "username": "wishlistorganizer",
            "password": "TestPass123!",
        },
    )

    assert login_response.status_code == 200, login_response.text

    token = login_response.json()["access_token"]

    return {"Authorization": f"Bearer {token}"}


def create_event(client, headers):
    """Create an event for Wishlist tests."""

    response = client.post(
        "/events/",
        headers=headers,
        json={
            "title": "Wishlist Test Event",
            "description": "An event for automated testing",
            "category": "Tech",
            "location": "Bengaluru",
            "event_date": "2027-12-15T10:00:00",
            "ticket_price": 500,
            "total_tickets": 100,
        },
    )

    assert response.status_code in (200, 201), response.text
    return response.json()["id"]


def test_wishlist_model_import():
    assert Wishlist.__tablename__ == "wishlists"


def test_wishlist_unique_constraint():
    constraints = [
        constraint.name
        for constraint in Wishlist.__table__.constraints
    ]

    assert "uq_wishlist_user_event" in constraints


def test_add_event_to_wishlist(client):
    headers = create_user_and_token(client)
    event_id = create_event(client, headers)

    response = client.post(
        f"/wishlist/{event_id}",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["message"] == (
        "Event added to wishlist successfully"
    )
    assert response.json()["event_id"] == event_id


def test_list_wishlist(client):
    headers = create_user_and_token(client)
    event_id = create_event(client, headers)

    add_response = client.post(
        f"/wishlist/{event_id}",
        headers=headers,
    )
    assert add_response.status_code == 200, add_response.text

    response = client.get("/wishlist/", headers=headers)

    assert response.status_code == 200, response.text

    items = response.json()
    assert len(items) == 1
    assert items[0]["event_id"] == event_id
    assert items[0]["title"] == "Wishlist Test Event"


def test_remove_event_from_wishlist(client):
    headers = create_user_and_token(client)
    event_id = create_event(client, headers)

    add_response = client.post(
        f"/wishlist/{event_id}",
        headers=headers,
    )
    assert add_response.status_code == 200, add_response.text

    response = client.delete(
        f"/wishlist/{event_id}",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["message"] == (
        "Event removed from wishlist successfully"
    )

    list_response = client.get("/wishlist/", headers=headers)

    assert list_response.status_code == 200
    assert all(
        item["event_id"] != event_id
        for item in list_response.json()
    )


def test_add_duplicate_event_to_wishlist(client):
    headers = create_user_and_token(client)
    event_id = create_event(client, headers)

    first_response = client.post(
        f"/wishlist/{event_id}",
        headers=headers,
    )
    assert first_response.status_code == 200, first_response.text

    second_response = client.post(
        f"/wishlist/{event_id}",
        headers=headers,
    )

    assert second_response.status_code == 409
    assert second_response.json()["detail"] == (
        "Event is already in your wishlist"
    )


def test_add_missing_event_to_wishlist(client):
    headers = create_user_and_token(client)

    response = client.post(
        "/wishlist/999999",
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Event not found"


def test_remove_missing_wishlist_item(client):
    headers = create_user_and_token(client)

    response = client.delete(
        "/wishlist/999999",
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Event not found in your wishlist"
    )


def test_wishlist_requires_authentication(client):
    response = client.get("/wishlist/")

    assert response.status_code == 401

