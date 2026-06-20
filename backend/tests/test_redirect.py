"""Tests for GET /<short_code> redirect endpoint."""


def _create_short_url(client, auth_headers, url, alias=None):
    payload = {"url": url}
    if alias:
        payload["custom_alias"] = alias
    response = client.post("/api/shorten", json=payload, headers=auth_headers())
    assert response.status_code == 200
    short_url = response.get_json()["short_url"]
    return short_url.rstrip("/").split("/")[-1]


def test_redirect_success(client, auth_headers):
    short_code = _create_short_url(
        client,
        auth_headers,
        "https://destination.example.com/path",
        alias="go-here",
    )

    response = client.get(f"/{short_code}")

    assert response.status_code == 302
    assert response.headers["Location"] == "https://destination.example.com/path"


def test_redirect_not_found(client):
    response = client.get("/does-not-exist")

    assert response.status_code == 404
    assert response.get_json()["error"] == "URL not found"


def test_redirect_public_without_auth(client, auth_headers):
    """Redirect must work with no Authorization header."""
    short_code = _create_short_url(
        client,
        auth_headers,
        "https://public.example.com",
        alias="public-link",
    )

    response = client.get(f"/{short_code}")

    assert response.status_code == 302
    assert response.headers["Location"] == "https://public.example.com"
