"""Tests for POST /api/shorten URL creation endpoint."""


def test_shorten_success_authenticated(client, auth_headers):
    headers = auth_headers(username="shorten_user")

    response = client.post(
        "/api/shorten",
        json={"url": "https://example.com/page"},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.get_json()
    assert "short_url" in data
    short_code = data["short_url"].rstrip("/").split("/")[-1]
    assert len(short_code) == 6


def test_shorten_without_auth_token(client):
    response = client.post(
        "/api/shorten",
        json={"url": "https://example.com/noauth"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "Unauthorized"


def test_shorten_missing_url(client, auth_headers):
    headers = auth_headers(username="missing_url_user")

    response = client.post("/api/shorten", json={}, headers=headers)

    assert response.status_code == 400
    assert response.get_json()["error"] == "URL is required"


def test_shorten_empty_url(client, auth_headers):
    headers = auth_headers(username="empty_url_user")

    response = client.post(
        "/api/shorten",
        json={"url": ""},
        headers=headers,
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "URL is required"


def test_shorten_custom_alias(client, auth_headers):
    headers = auth_headers(username="alias_user")

    response = client.post(
        "/api/shorten",
        json={"url": "https://example.com/custom", "custom_alias": "my-link"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.get_json()["short_url"].endswith("/my-link")


def test_shorten_custom_alias_already_taken(client, auth_headers):
    headers = auth_headers(username="alias_owner")

    first = client.post(
        "/api/shorten",
        json={"url": "https://example.com/first", "custom_alias": "taken"},
        headers=headers,
    )
    assert first.status_code == 200

    second = client.post(
        "/api/shorten",
        json={"url": "https://example.com/second", "custom_alias": "taken"},
        headers=headers,
    )

    assert second.status_code == 400
    assert second.get_json()["error"] == "Custom alias already taken"
