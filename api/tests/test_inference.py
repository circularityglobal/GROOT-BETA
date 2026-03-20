"""REFINET Cloud — Inference Tests
Tests for anonymous access, auth enforcement, and rate limiting.
BitNet sidecar is not running during tests, so we mock the ModelGateway.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
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


def _mock_inference_result(**overrides):
    """Build a mock InferenceResult matching the gateway's return type."""
    from api.services.providers.base import InferenceResult
    defaults = {
        "content": "Hello! I am Groot.",
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "model": "bitnet-b1.58-2b",
        "provider": "bitnet",
        "finish_reason": "stop",
    }
    defaults.update(overrides)
    return InferenceResult(**defaults)


def test_anonymous_access_allowed(client):
    """POST /v1/chat/completions without auth should NOT return 401."""
    mock_gateway = MagicMock()
    mock_gateway.complete = AsyncMock(return_value=_mock_inference_result())

    with patch("api.routes.inference.ModelGateway.get", return_value=mock_gateway):
        resp = client.post("/v1/chat/completions", json={
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
        })
        assert resp.status_code != 401
        assert resp.status_code == 200
        data = resp.json()
        assert data["choices"][0]["message"]["content"] == "Hello! I am Groot."


def test_anonymous_max_tokens_capped(client):
    """Anonymous requests should have max_tokens capped."""
    mock_gateway = MagicMock()
    mock_gateway.complete = AsyncMock(return_value=_mock_inference_result(content="Response"))

    with patch("api.routes.inference.ModelGateway.get", return_value=mock_gateway):
        resp = client.post("/v1/chat/completions", json={
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 4096,  # requesting more than anonymous limit
            "stream": False,
        })
        assert resp.status_code == 200
        # Verify gateway was called with capped tokens
        assert mock_gateway.complete.called
        call_kwargs = mock_gateway.complete.call_args
        assert call_kwargs.kwargs["max_tokens"] <= 256


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
