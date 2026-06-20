"""Tests for GET /api/stats/<short_code> analytics endpoint."""

from datetime import datetime


def test_stats_returns_correct_data(client, auth_headers, mongo_db):
    headers = auth_headers(username="stats_user")
    create = client.post(
        "/api/shorten",
        json={"url": "https://stats.example.com", "custom_alias": "stat-code"},
        headers=headers,
    )
    assert create.status_code == 200

    mongo_db["urls"].update_one(
        {"short_code": "stat-code"},
        {"$set": {"clicks": 7}},
    )

    response = client.get("/api/stats/stat-code")

    assert response.status_code == 200
    data = response.get_json()
    assert data["short_code"] == "stat-code"
    assert data["original_url"] == "https://stats.example.com"
    assert data["clicks"] == 7
    assert data["expiry"] is None


def test_stats_not_found(client):
    response = client.get("/api/stats/missing-code")

    assert response.status_code == 404
    assert response.get_json()["error"] == "URL not found"


def test_stats_includes_expiry(client, auth_headers):
    headers = auth_headers(username="expiry_stats_user")
    expiry = "2026-12-31T23:59:00"
    client.post(
        "/api/shorten",
        json={
            "url": "https://expiring.example.com",
            "custom_alias": "exp-code",
            "expiry": expiry,
        },
        headers=headers,
    )

    response = client.get("/api/stats/exp-code")

    assert response.status_code == 200
    parsed = datetime.fromisoformat(response.get_json()["expiry"])
    assert parsed.year == 2026
    assert parsed.month == 12
    assert parsed.day == 31
