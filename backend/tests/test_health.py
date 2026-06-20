"""Tests for GET /health and GET /metrics endpoints."""


def test_health_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["mongodb"] == "up"
    assert data["redis"] == "up"
    assert isinstance(data["uptime_seconds"], int)
    assert data["uptime_seconds"] >= 0


def test_health_degraded_when_mongodb_unavailable(client, monkeypatch):
    import app as app_module

    monkeypatch.setattr(app_module, "client", None)

    response = client.get("/health")

    assert response.status_code == 503
    data = response.get_json()
    assert data["status"] == "degraded"
    assert data["mongodb"] == "down"
    assert data["redis"] == "up"


def test_health_degraded_when_redis_unavailable(client, monkeypatch):
    import app as app_module

    monkeypatch.setattr(app_module, "redis_client", None)

    response = client.get("/health")

    assert response.status_code == 503
    data = response.get_json()
    assert data["status"] == "degraded"
    assert data["mongodb"] == "up"
    assert data["redis"] == "down"


def test_health_public_no_auth(client):
    response = client.get("/health")

    assert response.status_code == 200


def test_metrics_returns_counters(client, auth_headers):
    headers = auth_headers(username="metrics_user")

    client.post(
        "/api/shorten",
        json={"url": "https://metrics.example.com", "custom_alias": "m1"},
        headers=headers,
    )
    client.get("/m1")

    response = client.get("/metrics")

    assert response.status_code == 200
    data = response.get_json()
    assert data["total_requests"] >= 3
    assert data["total_shortens"] >= 1
    assert data["total_redirects"] >= 1
    assert isinstance(data["uptime_seconds"], int)
