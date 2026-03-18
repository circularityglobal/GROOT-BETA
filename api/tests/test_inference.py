"""REFINET Cloud — Inference Tests
Tests for anonymous access, auth enforcement, and rate limiting.
BitNet sidecar is not running during tests, so inference calls will fail at the
HTTP call to BitNet — but we can verify auth behavior up to that point.
"""

import pytest
from unittest.mock import patch, AsyncMock
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

    # Reset anonymous rate limit counters between tests
    from api.routes.inference import _anon_counters, _anon_lock
    with _anon_lock:
        _anon_counters.clear()

    yield


@pytest.fixture
def client():
    return TestClient(app)


def test_anonymous_access_allowed(client):
    """POST /v1/chat/completions without auth should NOT return 401."""
    with patch("api.routes.inference.call_bitnet", new_callable=AsyncMock) as mock_bitnet:
        mock_bitnet.return_value = {
            "content": "Hello! I am Groot.",
            "prompt_tokens": 10,
            "completion_tokens": 5,
        }
        resp = client.post("/v1/chat/completions", json={
            "messages": [{"role": "user", "content": "hello"}],
        })
        assert resp.status_code != 401
        # Should succeed (200) since BitNet is mocked
        assert resp.status_code == 200
        data = resp.json()
        assert data["choices"][0]["message"]["content"] == "Hello! I am Groot."


def test_anonymous_max_tokens_capped(client):
    """Anonymous requests should have max_tokens capped to 256."""
    with patch("api.routes.inference.call_bitnet", new_callable=AsyncMock) as mock_bitnet:
        mock_bitnet.return_value = {
            "content": "Response",
            "prompt_tokens": 10,
            "completion_tokens": 5,
        }
        resp = client.post("/v1/chat/completions", json={
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 4096,  # requesting more than anonymous limit
        })
        assert resp.status_code == 200
        # Verify BitNet was called with capped tokens
        assert mock_bitnet.called
        call_kwargs = mock_bitnet.call_args
        assert call_kwargs[1]["max_tokens"] <= 256


def test_invalid_bearer_token_rejected(client):
    """Invalid Bearer token should return 401."""
    resp = client.post("/v1/chat/completions", json={
        "messages": [{"role": "user", "content": "hello"}],
    }, headers={"Authorization": "Bearer invalid_token_here"})
    assert resp.status_code == 401


def test_invalid_api_key_rejected(client):
    """Invalid API key should return 401."""
    resp = client.post("/v1/chat/completions", json={
        "messages": [{"role": "user", "content": "hello"}],
    }, headers={"Authorization": "Bearer rf_fake_key_that_does_not_exist"})
    assert resp.status_code == 401


def test_models_endpoint_no_auth(client):
    """GET /v1/models works without auth."""
    resp = client.get("/v1/models")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["data"]) > 0
    assert data["data"][0]["id"] == "bitnet-b1.58-2b"
