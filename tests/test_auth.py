
def test_register_user(client):
    response = client.post(
        "/auth/register",
        json={
            "username": "testuser01",
            "email": "testuser01@example.com",
            "password": "TestPass123!",
        },
    )

    assert response.status_code == 201

    data = response.json()
    assert data["username"] == "testuser01"
    assert data["email"] == "testuser01@example.com"
    assert data["role"] == "USER"
    assert "hashed_password" not in data


def test_register_duplicate_username(client):
    payload = {
        "username": "duplicateuser",
        "email": "first@example.com",
        "password": "TestPass123!",
    }

    first_response = client.post("/auth/register", json=payload)
    assert first_response.status_code == 201

    duplicate_response = client.post(
        "/auth/register",
        json={
            "username": "duplicateuser",
            "email": "second@example.com",
            "password": "TestPass456!",
        },
    )

    assert duplicate_response.status_code == 400
    assert duplicate_response.json()["detail"] == "Username already exists"


def test_register_duplicate_email(client):
    first_response = client.post(
        "/auth/register",
        json={
            "username": "firstuser",
            "email": "shared@example.com",
            "password": "TestPass123!",
        },
    )
    assert first_response.status_code == 201

    duplicate_response = client.post(
        "/auth/register",
        json={
            "username": "seconduser",
            "email": "shared@example.com",
            "password": "TestPass456!",
        },
    )

    assert duplicate_response.status_code == 400
    assert duplicate_response.json()["detail"] == "Email already exists"


def test_login_success(client):
    client.post(
        "/auth/register",
        json={
            "username": "loginuser",
            "email": "loginuser@example.com",
            "password": "TestPass123!",
        },
    )

    response = client.post(
        "/auth/login",
        json={
            "username": "loginuser",
            "password": "TestPass123!",
        },
    )

    assert response.status_code == 200

    data = response.json()
    assert data["token_type"] == "bearer"
    assert isinstance(data["access_token"], str)
    assert len(data["access_token"]) > 0


def test_login_wrong_password(client):
    client.post(
        "/auth/register",
        json={
            "username": "wrongpassuser",
            "email": "wrongpass@example.com",
            "password": "TestPass123!",
        },
    )

    response = client.post(
        "/auth/login",
        json={
            "username": "wrongpassuser",
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"
