"""Tests for /api/register and /api/login authentication endpoints."""


def test_register_success(client):
    response = client.post(
        "/api/register",
        json={"username": "alice", "password": "secret123"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["username"] == "alice"
    assert isinstance(data["token"], str)
    assert data["token"]


def test_register_duplicate_username(client):
    payload = {"username": "bob", "password": "secret123"}
    first = client.post("/api/register", json=payload)
    assert first.status_code == 200

    second = client.post("/api/register", json=payload)

    assert second.status_code == 409
    assert second.get_json()["error"] == "Username already taken, choose another"


def test_register_missing_fields(client):
    response = client.post("/api/register", json={"username": "carol"})

    assert response.status_code == 400
    assert response.get_json()["error"] == "Username and password are required"


def test_register_empty_username(client):
    response = client.post(
        "/api/register",
        json={"username": "   ", "password": "secret123"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Username and password are required"


def test_login_success(client):
    client.post(
        "/api/register",
        json={"username": "dave", "password": "mypassword"},
    )

    response = client.post(
        "/api/login",
        json={"username": "dave", "password": "mypassword"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["username"] == "dave"
    assert isinstance(data["token"], str)
    assert data["token"]


def test_login_wrong_password(client):
    client.post(
        "/api/register",
        json={"username": "eve", "password": "correct"},
    )

    response = client.post(
        "/api/login",
        json={"username": "eve", "password": "wrong"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "Invalid username or password"


def test_login_nonexistent_user(client):
    response = client.post(
        "/api/login",
        json={"username": "nobody", "password": "secret123"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "Invalid username or password"


def test_login_missing_fields(client):
    response = client.post("/api/login", json={"username": "frank"})

    assert response.status_code == 400
    assert response.get_json()["error"] == "Username and password are required"
