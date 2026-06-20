"""Shared pytest fixtures for the Flask URL shortener backend."""

import os
import sys
from unittest.mock import patch

import fakeredis
import mongomock
import pytest

# Ensure the backend package root is importable as ``app``.
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

# Patch external services before the application module is first imported.
_redis_patch = patch("redis.Redis", fakeredis.FakeRedis)
_mongo_patch = patch("pymongo.MongoClient", mongomock.MongoClient)
_redis_patch.start()
_mongo_patch.start()

import app as app_module  # noqa: E402
from app import app as flask_app  # noqa: E402


@pytest.fixture
def fake_redis():
    """Fresh in-memory Redis instance for each test."""
    client = fakeredis.FakeRedis()
    yield client
    client.flushall()


@pytest.fixture
def mongo_db():
    """Fresh in-memory MongoDB database for each test."""
    client = mongomock.MongoClient()
    db = client["url_shortener_test"]
    db["urls"].delete_many({})
    db["users"].delete_many({})
    yield db
    client.close()


@pytest.fixture
def app(mongo_db, fake_redis, monkeypatch):
    """Flask app wired to in-memory MongoDB and Redis; state reset per test."""
    monkeypatch.setattr(app_module, "redis_client", fake_redis)
    monkeypatch.setattr(app_module, "client", mongo_db.client)
    monkeypatch.setattr(app_module, "db", mongo_db)
    monkeypatch.setattr(app_module, "collection", mongo_db["urls"])
    monkeypatch.setattr(app_module, "users", mongo_db["users"])

    mongo_db["urls"].delete_many({})
    mongo_db["users"].delete_many({})
    fake_redis.flushall()

    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    """Flask test client bound to the per-test app fixture."""
    return app.test_client()


@pytest.fixture
def auth_token(client):
    """Register a user and return a Bearer token string."""

    def _register(username="testuser", password="password123"):
        response = client.post(
            "/api/register",
            json={"username": username, "password": password},
        )
        assert response.status_code == 200
        return response.get_json()["token"]

    return _register


@pytest.fixture
def auth_headers(auth_token):
    """Register a user and return Authorization headers for protected routes."""

    def _headers(username="testuser", password="password123"):
        token = auth_token(username=username, password=password)
        return {"Authorization": f"Bearer {token}"}

    return _headers
