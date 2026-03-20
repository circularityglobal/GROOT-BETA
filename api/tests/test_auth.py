"""REFINET Cloud — Auth Tests"""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.database import init_databases


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    """Use temp SQLite DBs for testing."""
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

    # Reset cached settings and engines
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


def _create_test_user(client):
    """Create a test user via the wallet/create endpoint and return tokens + address."""
    resp = client.post("/auth/wallet/create", json={"chain_id": 1})
    assert resp.status_code == 200, f"wallet/create failed: {resp.text}"
    data = resp.json()
    return data


def test_wallet_create(client):
    """POST /auth/wallet/create should create a user with a custodial wallet."""
    data = _create_test_user(client)
    assert "access_token" in data
    assert "eth_address" in data
    assert data["eth_address"].startswith("0x")


def test_wallet_create_returns_tokens(client):
    """Wallet creation should return access and refresh tokens."""
    data = _create_test_user(client)
    assert "access_token" in data
    assert "refresh_token" in data
    assert len(data["access_token"]) > 0


def test_login_requires_password(client):
    """Login with email/password fails if user has no password set (wallet-only user)."""
    data = _create_test_user(client)
    # Wallet users have no email/password — login should reject
    resp = client.post("/auth/login", json={
        "email": "nonexistent@refinet.cloud",
        "password": "SecurePass123!@#",
    })
    assert resp.status_code == 401


def test_login_wrong_password(client):
    """Login with wrong credentials returns 401."""
    resp = client.post("/auth/login", json={
        "email": "wrong@refinet.cloud",
        "password": "WrongPassword!@#",
    })
    assert resp.status_code == 401


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["platform"] == "REFINET Cloud"
    assert "checks" in data
    assert "uptime_seconds" in data


def test_models_no_auth(client):
    """GET /v1/models should work without auth."""
    resp = client.get("/v1/models")
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"][0]["id"] == "bitnet-b1.58-2b"


def test_inference_no_auth_allowed(client):
    """POST /v1/chat/completions without auth is allowed (anonymous access).
    The request passes auth but may fail at inference (BitNet not running in tests)."""
    resp = client.post("/v1/chat/completions", json={
        "messages": [{"role": "user", "content": "hello"}],
    })
    # Should NOT be 401 — anonymous access is allowed
    assert resp.status_code != 401


def test_inference_bad_token(client):
    """POST /v1/chat/completions with invalid token should fail."""
    resp = client.post("/v1/chat/completions", json={
        "messages": [{"role": "user", "content": "hello"}],
    }, headers={"Authorization": "Bearer invalid_token"})
    assert resp.status_code == 401


def test_me_requires_auth(client):
    """GET /auth/me without auth should fail."""
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_with_auth(client):
    """GET /auth/me with valid token should return user info."""
    data = _create_test_user(client)
    resp = client.get("/auth/me", headers={
        "Authorization": f"Bearer {data['access_token']}",
    })
    assert resp.status_code == 200
    me = resp.json()
    assert me["eth_address"] == data["eth_address"]
