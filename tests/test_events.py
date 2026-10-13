from app.main import app
from datetime import datetime, timedelta, timezone

from app.models import User


def register_user(client, username, role="USER"):
    response = client.post(
        "/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "TestPass123!",
        },
    )
    assert response.status_code == 201

    if role != "USER":
        # Use the same database dependency overridden by the test fixture.
        from app.database import get_db

        db_dependency = app.dependency_overrides[get_db]
        db = next(db_dependency())

        try:
            user = db.query(User).filter(
                User.username == username
            ).first()

            assert user is not None, (
                f"Registered user {username} was not found in test database"
            )

            user.role = role
            db.commit()
        finally:
            db.close()

    return response.json()


def login_and_get_token(client, username):
    response = client.post(
        "/auth/login",
        json={
            "username": username,
            "password": "TestPass123!",
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def create_event_payload(title="Test Tech Event"):
    return {
        "title": title,
        "description": "An event created for automated testing.",
        "category": "Tech",
        "location": "Bengaluru",
        "event_date": (
            datetime.now(timezone.utc) + timedelta(days=30)
        ).isoformat(),
        "ticket_price": 499.0,
        "banner_image": None,
        "total_tickets": 100,
    }


def test_get_all_events_empty(client):
    response = client.get("/events/")
    assert response.status_code == 200
    assert response.json() == []


def test_search_events_empty(client):
    response = client.get(
        "/events/search",
        params={"title": "Nonexistent Event"},
    )
    assert response.status_code == 200
    assert response.json() == []


def test_get_events_by_category_empty(client):
    response = client.get("/events/category/Tech")
    assert response.status_code == 200
    assert response.json() == []


def test_get_nonexistent_event(client):
    response = client.get("/events/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Event not found"


def test_regular_user_cannot_create_event(client):
    register_user(client, "regularuser")
    token = login_and_get_token(client, "regularuser")

    response = client.post(
        "/events/",
        json=create_event_payload(),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Organizer access required"


def test_organizer_can_create_event(client):
    register_user(client, "organizeruser", role="ORGANIZER")
    token = login_and_get_token(client, "organizeruser")

    response = client.post(
        "/events/",
        json=create_event_payload(),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Tech Event"
    assert data["category"] == "Tech"
    assert data["total_tickets"] == 100
    assert data["available_tickets"] == 100
    assert data["organizer_id"] is not None
    assert data["event_status"] == "UPCOMING"


def test_organizer_can_get_own_events(client):
    register_user(client, "myorganizer", role="ORGANIZER")
    token = login_and_get_token(client, "myorganizer")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        "/events/",
        json=create_event_payload("Organizer's Event"),
        headers=headers,
    )
    assert create_response.status_code == 201

    response = client.get("/events/my-events", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Organizer's Event"


def test_organizer_cannot_update_another_organizers_event(client):
    register_user(client, "owneruser", role="ORGANIZER")
    owner_token = login_and_get_token(client, "owneruser")

    create_response = client.post(
        "/events/",
        json=create_event_payload("Owner Event"),
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert create_response.status_code == 201
    event_id = create_response.json()["id"]

    register_user(client, "otherorganizer", role="ORGANIZER")
    other_token = login_and_get_token(client, "otherorganizer")

    response = client.put(
        f"/events/{event_id}",
        json={"title": "Unauthorized Change"},
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "You can only update your own events"
    )


def test_organizer_cannot_cancel_another_organizers_event(client):
    register_user(client, "cancelowner", role="ORGANIZER")
    owner_token = login_and_get_token(client, "cancelowner")

    create_response = client.post(
        "/events/",
        json=create_event_payload("Protected Event"),
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert create_response.status_code == 201
    event_id = create_response.json()["id"]

    register_user(client, "cancelother", role="ORGANIZER")
    other_token = login_and_get_token(client, "cancelother")

    response = client.put(
        f"/events/{event_id}/cancel",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "You can only cancel your own events"
    )


def test_event_search_finds_created_event(client):
    register_user(client, "searchorganizer", role="ORGANIZER")
    token = login_and_get_token(client, "searchorganizer")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        "/events/",
        json=create_event_payload("Python Technology Meetup"),
        headers=headers,
    )
    assert create_response.status_code == 201

    response = client.get(
        "/events/search",
        params={"title": "Python Technology"},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Python Technology Meetup"
