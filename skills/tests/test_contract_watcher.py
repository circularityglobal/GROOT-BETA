"""Tests for skills/refinet-contract-watcher/scripts/contract_scan.py"""

import json
import os
import sqlite3
import sys
from unittest.mock import patch

import pytest

SCRIPT_DIR = os.path.join(os.path.dirname(__file__), "..", "refinet-contract-watcher", "scripts")
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import contract_scan  # noqa: E402


# ── Import Tests ─────────────────────────────────────────────────────────

class TestContractWatcherImports:
    def test_module_functions_exist(self):
        assert callable(contract_scan.get_db)
        assert callable(contract_scan.get_unscanned_abis)
        assert callable(contract_scan.analyze_abi_from_db)
        assert callable(contract_scan.store_flags)
        assert callable(contract_scan.get_event_stats)
        assert callable(contract_scan.get_registry_stats)
        assert callable(contract_scan.format_report)
        assert callable(contract_scan.send_email)
        assert callable(contract_scan.main)

    def test_dangerous_patterns_defined(self):
        assert len(contract_scan.DANGEROUS_PATTERNS) == 8
        expected = {"delegatecall", "selfdestruct", "tx_origin", "unchecked_call",
                    "infinite_approval", "inline_assembly", "proxy_pattern", "ownership_transfer"}
        assert set(contract_scan.DANGEROUS_PATTERNS.keys()) == expected

    def test_each_pattern_has_fields(self):
        for name, p in contract_scan.DANGEROUS_PATTERNS.items():
            assert "severity" in p, f"{name} missing severity"
            assert "regex" in p, f"{name} missing regex"
            assert "description" in p, f"{name} missing description"
            assert "risk" in p, f"{name} missing risk"


# ── analyze_abi_from_db Tests (pattern detection) ────────────────────────

class TestAnalyzeABI:
    """Test each dangerous pattern is detected."""

    def _insert_abi(self, conn, abi_id, abi_json):
        conn.execute("INSERT INTO users (id) VALUES ('u1') ON CONFLICT DO NOTHING")
        conn.execute(
            "INSERT INTO registry_projects (id, owner_id, slug, name) VALUES ('p1', 'u1', 'u1/t', 'T') ON CONFLICT DO NOTHING"
        )
        conn.execute(
            "INSERT INTO registry_abis (id, project_id, contract_name, chain, abi_json) VALUES (?, 'p1', 'Test', 'ethereum', ?)",
            (abi_id, json.dumps(abi_json))
        )
        conn.commit()

    def test_detects_selfdestruct(self, tmp_db):
        _, conn = tmp_db
        abi = [{"type": "function", "name": "selfdestruct", "inputs": [], "outputs": []}]
        self._insert_abi(conn, "abi-sd", abi)
        result = contract_scan.analyze_abi_from_db(conn, "abi-sd")
        patterns = [f["pattern"] for f in result["flags"]]
        assert "selfdestruct" in patterns
        assert result["risk_level"] == "CRITICAL"

    def test_detects_delegatecall(self, tmp_db):
        _, conn = tmp_db
        abi = [{"type": "function", "name": "delegatecall", "inputs": [], "outputs": []}]
        self._insert_abi(conn, "abi-dc", abi)
        result = contract_scan.analyze_abi_from_db(conn, "abi-dc")
        patterns = [f["pattern"] for f in result["flags"]]
        assert "delegatecall" in patterns

    def test_detects_ownership_transfer(self, tmp_db):
        _, conn = tmp_db
        abi = [{"type": "function", "name": "transferOwnership", "inputs": [{"name": "newOwner", "type": "address"}], "outputs": []}]
        self._insert_abi(conn, "abi-ot", abi)
        result = contract_scan.analyze_abi_from_db(conn, "abi-ot")
        patterns = [f["pattern"] for f in result["flags"]]
        assert "ownership_transfer" in patterns

    def test_detects_proxy_pattern(self, tmp_db):
        _, conn = tmp_db
        abi = [{"type": "function", "name": "upgradeTo", "inputs": [{"name": "impl", "type": "address"}], "outputs": []}]
        self._insert_abi(conn, "abi-px", abi)
        result = contract_scan.analyze_abi_from_db(conn, "abi-px")
        patterns = [f["pattern"] for f in result["flags"]]
        assert "proxy_pattern" in patterns

    def test_detects_tx_origin_in_abi_string(self, tmp_db):
        _, conn = tmp_db
        # tx.origin appears in a string within the ABI
        abi = [{"type": "function", "name": "check", "inputs": [], "outputs": [], "devdoc": "uses tx.origin auth"}]
        self._insert_abi(conn, "abi-tx", abi)
        result = contract_scan.analyze_abi_from_db(conn, "abi-tx")
        patterns = [f["pattern"] for f in result["flags"]]
        assert "tx_origin" in patterns

    def test_detects_inline_assembly_in_abi_string(self, tmp_db):
        _, conn = tmp_db
        abi = [{"type": "function", "name": "foo", "inputs": [], "outputs": [], "notice": "uses assembly { mstore }"}]
        self._insert_abi(conn, "abi-asm", abi)
        result = contract_scan.analyze_abi_from_db(conn, "abi-asm")
        patterns = [f["pattern"] for f in result["flags"]]
        assert "inline_assembly" in patterns

    def test_detects_unchecked_call(self, tmp_db):
        _, conn = tmp_db
        abi = [{"type": "function", "name": "pay", "inputs": [], "outputs": [], "notice": "addr.call{value: amount}"}]
        self._insert_abi(conn, "abi-uc", abi)
        result = contract_scan.analyze_abi_from_db(conn, "abi-uc")
        patterns = [f["pattern"] for f in result["flags"]]
        assert "unchecked_call" in patterns

    def test_detects_infinite_approval(self, tmp_db):
        _, conn = tmp_db
        abi = [{"type": "function", "name": "approve", "inputs": [], "outputs": [], "notice": "type(uint256).max"}]
        self._insert_abi(conn, "abi-ia", abi)
        result = contract_scan.analyze_abi_from_db(conn, "abi-ia")
        patterns = [f["pattern"] for f in result["flags"]]
        assert "infinite_approval" in patterns


# ── Clean ABI Tests ──────────────────────────────────────────────────────

class TestAnalyzeCleanABI:
    def test_clean_abi_returns_no_flags(self, tmp_db):
        _, conn = tmp_db
        conn.execute("INSERT INTO users (id) VALUES ('u1')")
        conn.execute("INSERT INTO registry_projects (id, owner_id, slug, name) VALUES ('p1', 'u1', 'u1/t', 'T')")
        clean = [
            {"type": "function", "name": "transfer", "inputs": [{"name": "to", "type": "address"}], "outputs": [{"name": "", "type": "bool"}]},
            {"type": "event", "name": "Transfer", "inputs": []},
        ]
        conn.execute(
            "INSERT INTO registry_abis (id, project_id, contract_name, chain, abi_json) VALUES ('abi-clean', 'p1', 'ERC20', 'ethereum', ?)",
            (json.dumps(clean),)
        )
        conn.commit()

        result = contract_scan.analyze_abi_from_db(conn, "abi-clean")
        assert result["flag_count"] == 0
        assert result["risk_level"] == "CLEAN"
        assert result["risk_score"] == 0

    def test_missing_abi_returns_unknown(self, tmp_db):
        _, conn = tmp_db
        result = contract_scan.analyze_abi_from_db(conn, "nonexistent")
        assert result["risk_level"] == "UNKNOWN"


# ── Risk Scoring Tests ───────────────────────────────────────────────────

class TestRiskScoring:
    def _insert_abi(self, conn, abi_id, abi_json):
        conn.execute("INSERT INTO users (id) VALUES ('u1') ON CONFLICT DO NOTHING")
        conn.execute(
            "INSERT INTO registry_projects (id, owner_id, slug, name) VALUES ('p1', 'u1', 'u1/t', 'T') ON CONFLICT DO NOTHING"
        )
        conn.execute(
            "INSERT INTO registry_abis (id, project_id, contract_name, chain, abi_json) VALUES (?, 'p1', 'Test', 'ethereum', ?)",
            (abi_id, json.dumps(abi_json))
        )
        conn.commit()

    def test_critical_score(self, tmp_db):
        _, conn = tmp_db
        abi = [
            {"type": "function", "name": "selfdestruct", "inputs": [], "outputs": []},
            {"type": "function", "name": "delegatecall", "inputs": [], "outputs": []},
        ]
        self._insert_abi(conn, "abi-crit", abi)
        result = contract_scan.analyze_abi_from_db(conn, "abi-crit")
        assert result["risk_level"] == "CRITICAL"
        assert result["risk_score"] >= 10

    def test_medium_score(self, tmp_db):
        _, conn = tmp_db
        abi = [{"type": "function", "name": "transferOwnership", "inputs": [{"name": "n", "type": "address"}], "outputs": []}]
        self._insert_abi(conn, "abi-med", abi)
        result = contract_scan.analyze_abi_from_db(conn, "abi-med")
        assert result["risk_level"] == "MEDIUM"
        assert result["risk_score"] >= 2


# ── store_flags Tests ────────────────────────────────────────────────────

class TestStoreFlags:
    def test_stores_flags_in_db(self, contract_db):
        _, conn = contract_db
        analysis = contract_scan.analyze_abi_from_db(conn, "abi-danger")
        contract_scan.store_flags(conn, "abi-danger", analysis)

        count = conn.execute("SELECT COUNT(*) FROM contract_security_flags WHERE abi_id = 'abi-danger'").fetchone()[0]
        assert count > 0

    def test_stores_clean_sentinel(self, contract_db):
        _, conn = contract_db
        analysis = contract_scan.analyze_abi_from_db(conn, "abi-clean")
        contract_scan.store_flags(conn, "abi-clean", analysis)

        row = conn.execute(
            "SELECT pattern, severity FROM contract_security_flags WHERE abi_id = 'abi-clean'"
        ).fetchone()
        assert row[0] == "CLEAN"
        assert row[1] == "NONE"


# ── get_event_stats Tests ────────────────────────────────────────────────

class TestGetEventStats:
    def test_event_stats_with_data(self, contract_db):
        _, conn = contract_db
        stats = contract_scan.get_event_stats(conn)
        assert stats["total_listeners"] == 1
        assert stats["total_events"] == 5
        assert stats["unprocessed_events"] == 0  # no status column


# ── get_registry_stats Tests ─────────────────────────────────────────────

class TestGetRegistryStats:
    def test_registry_stats_with_data(self, contract_db):
        _, conn = contract_db
        stats = contract_scan.get_registry_stats(conn)
        assert stats["total_projects"] == 1
        assert stats["total_abis"] == 2
        assert stats["starred_projects"] == 1


# ── format_report Tests ──────────────────────────────────────────────────

class TestContractFormatReport:
    def test_nominal_report(self):
        event_stats = {"total_listeners": 1, "total_events": 10, "events_this_week": 5, "unprocessed_events": 0}
        registry_stats = {"total_projects": 2, "total_abis": 5, "flagged_abis": 0, "starred_projects": 1}
        scan_results = {"scanned": 3, "critical_total": 0, "high_total": 0}
        text, html = contract_scan.format_report(event_stats, registry_stats, scan_results)
        assert "NOMINAL" in text
        assert "#00d4aa" in html

    def test_alerts_report(self):
        event_stats = {"total_listeners": 1, "total_events": 10, "events_this_week": 5, "unprocessed_events": 0}
        registry_stats = {"total_projects": 2, "total_abis": 5, "flagged_abis": 2, "starred_projects": 1}
        scan_results = {"scanned": 3, "critical_total": 2, "high_total": 1}
        text, html = contract_scan.format_report(event_stats, registry_stats, scan_results)
        assert "ALERTS" in text
        assert "#ff6b6b" in html
