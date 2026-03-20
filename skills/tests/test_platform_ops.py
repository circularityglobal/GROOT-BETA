"""Tests for skills/refinet-platform-ops/scripts/health_check.py"""

import asyncio
import importlib
import json
import os
import sqlite3
import sys
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the script to the path so we can import it
SCRIPT_DIR = os.path.join(os.path.dirname(__file__), "..", "refinet-platform-ops", "scripts")
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)


@pytest.fixture(autouse=True)
def _patch_httpx_import():
    """Ensure httpx is available (skip auto-install logic)."""
    pass


import health_check  # noqa: E402


# ── Import / Structure Tests ─────────────────────────────────────────────

class TestHealthCheckImports:
    def test_module_functions_exist(self):
        assert callable(health_check.check_subsystem)
        assert callable(health_check.run_all_checks)
        assert callable(health_check.format_report)
        assert callable(health_check.send_email)
        assert callable(health_check.main)

    def test_constants_have_defaults(self):
        assert health_check.API_BASE.startswith("http")
        assert health_check.BITNET_HOST.startswith("http")


# ── check_subsystem Tests ────────────────────────────────────────────────

class TestCheckSubsystem:
    def test_successful_get(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.elapsed = timedelta(milliseconds=42)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        name, result = asyncio.run(
            health_check.check_subsystem(mock_client, "api", "GET", "http://test/health")
        )
        assert name == "api"
        assert result["ok"] is True
        assert result["status_code"] == 200
        assert "latency_ms" in result

    def test_failed_check_500(self):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.elapsed = timedelta(milliseconds=100)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        name, result = asyncio.run(
            health_check.check_subsystem(mock_client, "api", "GET", "http://test/health")
        )
        assert result["ok"] is False

    def test_connection_error(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=ConnectionError("refused"))

        name, result = asyncio.run(
            health_check.check_subsystem(mock_client, "api", "GET", "http://test/health")
        )
        assert result["ok"] is False
        assert "error" in result

    def test_post_method(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.elapsed = timedelta(milliseconds=10)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        name, result = asyncio.run(
            health_check.check_subsystem(mock_client, "bitnet", "POST", "http://test/v1/chat", json={})
        )
        assert result["ok"] is True


# ── Database Check ───────────────────────────────────────────────────────

class TestDatabaseCheck:
    def test_db_exists_and_queryable(self, tmp_db, monkeypatch):
        db_path, conn = tmp_db
        conn.close()
        monkeypatch.setenv("DATABASE_PATH", db_path)

        # Reload to pick up new env
        importlib.reload(health_check)

        # Run only the DB portion of run_all_checks by calling it
        # and checking the database result
        with patch("health_check.httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_resp = MagicMock(status_code=200, elapsed=timedelta(milliseconds=1))
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_httpx.AsyncClient.return_value = mock_client

            results = asyncio.run(health_check.run_all_checks())
        assert results["database"]["ok"] is True

    def test_db_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "nonexistent.db"))
        importlib.reload(health_check)

        with patch("health_check.httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_resp = MagicMock(status_code=200, elapsed=timedelta(milliseconds=1))
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_httpx.AsyncClient.return_value = mock_client

            results = asyncio.run(health_check.run_all_checks())
        assert results["database"]["ok"] is False


# ── format_report Tests ──────────────────────────────────────────────────

class TestFormatReport:
    def test_all_ok_report(self):
        results = {
            "api": {"ok": True, "latency_ms": 5},
            "database": {"ok": True},
            "disk": {"ok": True, "used_pct": 40},
        }
        text, all_ok = health_check.format_report(results)
        assert all_ok is True
        assert "ALL SYSTEMS OPERATIONAL" in text

    def test_issues_report(self):
        results = {
            "api": {"ok": False, "error": "connection refused"},
            "database": {"ok": True},
        }
        text, all_ok = health_check.format_report(results)
        assert all_ok is False
        assert "ISSUES DETECTED" in text

    def test_report_includes_all_subsystems(self):
        results = {
            "api": {"ok": True},
            "bitnet": {"ok": True},
            "database": {"ok": True},
            "smtp": {"ok": True},
            "disk": {"ok": True, "used_pct": 30},
            "memory": {"ok": True, "note": "skipped"},
        }
        text, _ = health_check.format_report(results)
        for name in results:
            assert name in text


# ── send_email Tests ─────────────────────────────────────────────────────

class TestSendEmail:
    def test_skips_when_no_admin_email(self, monkeypatch):
        monkeypatch.delenv("ADMIN_EMAIL", raising=False)
        # Should not raise
        health_check.send_email("Test", "<p>html</p>", "text")

    def test_sends_email_with_admin_set(self, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAIL", "admin@test.com")
        monkeypatch.setenv("SMTP_HOST", "127.0.0.1")
        monkeypatch.setenv("SMTP_PORT", "8025")

        sent_messages = []

        class MockSMTP:
            def __init__(self, host, port, **kwargs):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def send_message(self, msg):
                sent_messages.append(msg)

        with patch("health_check.smtplib.SMTP", MockSMTP):
            health_check.send_email("Subject", "<p>body</p>", "body text")

        assert len(sent_messages) == 1
        assert sent_messages[0]["Subject"] == "Subject"
        assert sent_messages[0]["To"] == "admin@test.com"
