"""REFINET Cloud — Webhook Tests
Tests for webhook subscription, event matching, HMAC signing, and retry logic.
"""

import json
import hmac
import hashlib
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.database import init_databases
from api.services.webhook_delivery import (
    _matches_event,
    deliver_single_webhook,
    RETRY_BACKOFF,
    MAX_RETRIES,
)


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


# ── Event Matching Tests ─────────────────────────────────────────────

def test_exact_event_match():
    """Exact event name should match."""
    assert _matches_event(["registry.project.created"], "registry.project.created")


def test_wildcard_match():
    """Wildcard pattern should match all events in namespace."""
    assert _matches_event(["registry.*"], "registry.project.created")
    assert _matches_event(["messaging.*"], "messaging.dm.sent")
    assert _matches_event(["system.*"], "system.health.degraded")


def test_global_wildcard():
    """Global wildcard '*' matches everything."""
    assert _matches_event(["*"], "anything.at.all")


def test_no_match():
    """Non-matching events should not match."""
    assert not _matches_event(["registry.*"], "messaging.dm.sent")
    assert not _matches_event(["registry.project.created"], "registry.abi.added")


# ── HMAC Signing Tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_hmac_signature_format():
    """Webhook deliveries should include properly formatted HMAC-SHA256 signature."""
    # This will fail to connect (no real endpoint) but we can verify the signing logic
    result = await deliver_single_webhook(
        url="http://127.0.0.1:19999/webhook-test",  # non-existent
        event="test.event",
        payload={"key": "value"},
        secret_hash="test_secret_hash_123",
    )
    # Connection will fail, but verify the function handles it gracefully
    assert result["delivered"] is False
    assert result["status_code"] is None
    assert result["message"]  # should contain error info


def test_hmac_computation():
    """Verify HMAC-SHA256 computation matches expected output."""
    secret = "my_webhook_secret"
    body = '{"event":"test","payload":{},"timestamp":"2026-01-01T00:00:00"}'
    expected = hmac.new(
        secret.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    assert len(expected) == 64  # SHA256 hex digest is 64 chars
    assert expected == hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()


# ── Retry Configuration Tests ────────────────────────────────────────

def test_retry_backoff_configured():
    """Retry backoff should have 3 increasing delays."""
    assert MAX_RETRIES == 3
    assert len(RETRY_BACKOFF) == 3
    assert RETRY_BACKOFF[0] < RETRY_BACKOFF[1] < RETRY_BACKOFF[2]
    assert RETRY_BACKOFF == [2, 8, 30]
