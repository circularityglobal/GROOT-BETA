"""Integration tests: platform-ops → knowledge-curator → contract-watcher pipeline."""

import asyncio
import importlib
import json
import os
import sys
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add script dirs
for subdir in ["refinet-platform-ops", "refinet-knowledge-curator", "refinet-contract-watcher"]:
    d = os.path.join(os.path.dirname(__file__), "..", subdir, "scripts")
    if d not in sys.path:
        sys.path.insert(0, d)

import health_check  # noqa: E402
import knowledge_health  # noqa: E402
import contract_scan  # noqa: E402


class TestPipelineImports:
    """All three modules can be imported without error."""

    def test_all_importable(self):
        assert hasattr(health_check, "main")
        assert hasattr(knowledge_health, "main")
        assert hasattr(contract_scan, "main")


class TestPipelineReportFormats:
    """Each skill produces the expected report format."""

    def test_platform_ops_report_format(self):
        results = {
            "api": {"ok": True, "latency_ms": 5},
            "database": {"ok": True},
            "disk": {"ok": True, "used_pct": 30},
        }
        text, all_ok = health_check.format_report(results)
        assert isinstance(text, str)
        assert isinstance(all_ok, bool)

    def test_knowledge_curator_report_format(self):
        stats = {
            "total_documents": 5, "total_chunks": 20, "total_embeddings": 20,
            "embeddings_complete": True, "new_documents_24h": 0, "new_chunks_24h": 0,
            "cag_contracts": 0, "cag_functions": 0, "db_size_mb": 0.5,
        }
        text, html = knowledge_health.format_report(stats, [], [], 0, 0)
        assert isinstance(text, str)
        assert isinstance(html, str)
        assert "<div" in html

    def test_contract_watcher_report_format(self):
        event_stats = {"total_listeners": 0, "total_events": 0, "events_this_week": 0, "unprocessed_events": 0}
        registry_stats = {"total_projects": 0, "total_abis": 0, "flagged_abis": 0, "starred_projects": 0}
        scan_results = {"scanned": 0, "critical_total": 0, "high_total": 0}
        text, html = contract_scan.format_report(event_stats, registry_stats, scan_results)
        assert isinstance(text, str)
        assert isinstance(html, str)
        assert "<div" in html


class TestSequentialPipeline:
    """Run all three skills in sequence against a shared test DB."""

    def test_full_pipeline_runs_without_error(self, knowledge_db, contract_db, monkeypatch):
        """Simulates: platform-ops → knowledge-curator → contract-watcher."""
        k_path, k_conn = knowledge_db
        c_path, c_conn = contract_db

        # ── Step 1: Platform Ops ──────────────────────────────────
        results = {
            "api": {"ok": True, "latency_ms": 10},
            "bitnet": {"ok": True, "latency_ms": 50},
            "database": {"ok": True},
            "smtp": {"ok": False, "error": "Connection refused"},
            "disk": {"ok": True, "used_pct": 45, "total_gb": 200, "free_gb": 110},
            "memory": {"ok": True, "note": "Non-Linux — skipped"},
        }
        ops_text, ops_ok = health_check.format_report(results)
        assert isinstance(ops_text, str)
        assert ops_ok is False  # smtp failed

        # ── Step 2: Knowledge Curator ─────────────────────────────
        monkeypatch.setattr(knowledge_health, "DB_PATH", k_path)
        stats = knowledge_health.get_stats(k_conn)
        orphans = knowledge_health.find_orphans(k_conn)
        stale = knowledge_health.find_stale_chunks(k_conn)
        unsynced = knowledge_health.find_unsynced_cag(k_conn)
        k_text, k_html = knowledge_health.format_report(stats, orphans, stale, unsynced, 0)
        assert isinstance(k_text, str)
        assert stats["total_documents"] == 3

        # ── Step 3: Contract Watcher ──────────────────────────────
        monkeypatch.setattr(contract_scan, "DB_PATH", c_path)
        event_stats = contract_scan.get_event_stats(c_conn)
        registry_stats = contract_scan.get_registry_stats(c_conn)

        # Scan ABIs
        unscanned = contract_scan.get_unscanned_abis(c_conn)
        scan_results = {"scanned": 0, "critical_total": 0, "high_total": 0, "flagged_abis": []}
        for abi_info in unscanned:
            analysis = contract_scan.analyze_abi_from_db(c_conn, abi_info["abi_id"])
            contract_scan.store_flags(c_conn, abi_info["abi_id"], analysis)
            scan_results["scanned"] += 1
            scan_results["critical_total"] += analysis.get("critical_count", 0)
            scan_results["high_total"] += analysis.get("high_count", 0)

        c_text, c_html = contract_scan.format_report(event_stats, registry_stats, scan_results)
        assert isinstance(c_text, str)
        assert scan_results["scanned"] == 2  # clean + dangerous ABIs

        # Verify dangerous ABI was flagged
        assert scan_results["critical_total"] > 0

    def test_pipeline_exit_codes(self, knowledge_db, contract_db, monkeypatch):
        """Verify exit codes: 0=healthy, 1=issues."""
        k_path, k_conn = knowledge_db

        # Knowledge curator should exit 1 (has orphans due to partial embeddings)
        monkeypatch.setattr(knowledge_health, "DB_PATH", k_path)
        stats = knowledge_health.get_stats(k_conn)
        orphans = knowledge_health.find_orphans(k_conn)
        stale = knowledge_health.find_stale_chunks(k_conn)
        all_ok = len(orphans) == 0 and len(stale) == 0 and stats.get("embeddings_complete", False)
        assert all_ok is False  # doc-2 has partial embeddings → exit code 1

        # Contract watcher with critical flags → exit code 1
        c_path, c_conn = contract_db
        monkeypatch.setattr(contract_scan, "DB_PATH", c_path)
        analysis = contract_scan.analyze_abi_from_db(c_conn, "abi-danger")
        assert analysis["critical_count"] > 0  # would trigger exit code 1
