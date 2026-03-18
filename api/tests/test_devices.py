"""REFINET Cloud — Device Tests
Tests for device registration, telemetry, and webhook event firing.
"""

import json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from api.main import app
from api.database import init_databases


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    pub_url = f"sqlite:///{tmp_path}/test_public.db"
    int_url = f"sqlite:///{tmp_path}/test_internal.db"
    monkeypatch.setenv("PUBLIC_DB_URL", pub_url)
    monkeypatch.setenv("INTERNAL_DB_URL", int_url)
    monkeypatch.setenv("SECRET_KEY", "a" * 128)
    monkeypatch.setenv("REFRESH_SECRET", "b" * 128)
    monkeypatch.setenv("SERVER_PEPPER", "c" * 128)
    monkeypatch.setenv("WEBHOOK_SIGNING_KEY", "d" * 64)
    monkeypatch.setenv("INTERNAL_DB_ENCRYPTION_KEY", "e" * 64)
    monkeypatch.setenv("ADMIN_API_SECRET", "f" * 64)

    from api.config import get_settings
    get_settings.cache_clear()

    import api.database as db_mod
    db_mod._public_engine = None
    db_mod._internal_engine = None
    db_mod._PublicSessionLocal = None
    db_mod._InternalSessionLocal = None

    init_databases()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def test_device_register_requires_auth(client):
    """POST /devices/register without auth should return 401."""
    resp = client.post("/devices/register", json={
        "name": "Test Sensor",
        "device_type": "iot",
    })
    assert resp.status_code == 401


def test_device_register_with_jwt(client):
    """Device registration with valid JWT should work."""
    # Create a user via SIWE flow first — since we can't easily do that in tests,
    # we'll create a user directly and generate a token
    from api.database import get_public_session_factory
    from api.models.public import User
    from api.auth.jwt import create_access_token
    import uuid

    db = get_public_session_factory()()
    try:
        user = User(
            id=str(uuid.uuid4()),
            username="device_tester",
            email="device@test.io",
            eth_address="0x742d35Cc6634C0532925a3b844Bc9e7595f2bD38",
        )
        db.add(user)
        db.commit()

        token = create_access_token(user.id, scopes=["devices:write"])

        with patch("api.services.webhook_delivery.deliver_webhook_event"):
            resp = client.post("/devices/register", json={
                "name": "Test Sensor",
                "device_type": "iot",
            }, headers={"Authorization": f"Bearer {token}"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Test Sensor"
        assert data["device_type"] == "iot"
        assert "api_key" in data  # API key returned on registration
        assert data["api_key"].startswith("rf_")
    finally:
        db.close()


def test_device_list_requires_auth(client):
    """GET /devices without auth should return 401."""
    resp = client.get("/devices")
    assert resp.status_code == 401


def test_telemetry_requires_device_key(client):
    """Telemetry push without device API key should fail."""
    resp = client.post("/devices/fake-device-id/telemetry", json={
        "payload": {"temperature": 22.5},
    })
    assert resp.status_code == 401
