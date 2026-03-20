"""Tests for skills/refinet-knowledge-curator/scripts/knowledge_health.py"""

import importlib
import json
import os
import sqlite3
import sys
from unittest.mock import patch

import pytest

SCRIPT_DIR = os.path.join(os.path.dirname(__file__), "..", "refinet-knowledge-curator", "scripts")
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import knowledge_health  # noqa: E402


# ── Import Tests ─────────────────────────────────────────────────────────

class TestKnowledgeImports:
    def test_module_functions_exist(self):
        assert callable(knowledge_health.get_db)
        assert callable(knowledge_health.get_stats)
        assert callable(knowledge_health.find_orphans)
        assert callable(knowledge_health.find_stale_chunks)
        assert callable(knowledge_health.prune_stale)
        assert callable(knowledge_health.find_unsynced_cag)
        assert callable(knowledge_health.format_report)
        assert callable(knowledge_health.send_email)
        assert callable(knowledge_health.main)


# ── get_stats Tests ──────────────────────────────────────────────────────

class TestGetStats:
    def test_stats_with_data(self, knowledge_db, monkeypatch):
        db_path, conn = knowledge_db
        monkeypatch.setattr(knowledge_health, "DB_PATH", db_path)

        stats = knowledge_health.get_stats(conn)
        assert stats["total_documents"] == 3
        assert stats["total_chunks"] == 9
        # 8 chunks have embeddings (last chunk of last doc has None)
        assert stats["total_embeddings"] == 8
        assert stats["embeddings_complete"] is False

    def test_stats_empty_db(self, tmp_db, monkeypatch):
        db_path, conn = tmp_db
        monkeypatch.setattr(knowledge_health, "DB_PATH", db_path)

        stats = knowledge_health.get_stats(conn)
        assert stats["total_documents"] == 0
        assert stats["total_chunks"] == 0
        assert stats["total_embeddings"] == 0
        assert stats["embeddings_complete"] is True  # 0 == 0

    def test_stats_cag_tables_present(self, knowledge_db, monkeypatch):
        db_path, conn = knowledge_db
        monkeypatch.setattr(knowledge_health, "DB_PATH", db_path)

        # Insert a contract_definition
        conn.execute(
            "INSERT INTO contract_definitions (id, name, chain, description, abi_json) "
            "VALUES ('cd-1', 'Test', 'ethereum', 'desc', '[{}]')"
        )
        conn.commit()

        stats = knowledge_health.get_stats(conn)
        assert stats["cag_contracts"] == 1
        assert stats["cag_functions"] == 1  # has abi_json


# ── find_orphans Tests ───────────────────────────────────────────────────

class TestFindOrphans:
    def test_finds_doc_with_no_chunks(self, knowledge_db):
        _, conn = knowledge_db
        # Add a doc with no chunks
        conn.execute(
            "INSERT INTO knowledge_documents (id, title, category, content_hash, content, uploaded_by, doc_type) "
            "VALUES ('orphan-doc', 'Orphan', 'docs', 'hash-orphan', 'text', 'admin', 'txt')"
        )
        conn.commit()

        orphans = knowledge_health.find_orphans(conn)
        orphan_ids = [o["document_id"] for o in orphans]
        assert "orphan-doc" in orphan_ids
        orphan = next(o for o in orphans if o["document_id"] == "orphan-doc")
        assert orphan["status"] == "no_chunks"

    def test_finds_doc_with_partial_embeddings(self, knowledge_db):
        _, conn = knowledge_db
        # doc-2 has 3 chunks but only 2 embeddings (chunk-2-2 has None)
        orphans = knowledge_health.find_orphans(conn)
        orphan_ids = [o["document_id"] for o in orphans]
        assert "doc-2" in orphan_ids
        orphan = next(o for o in orphans if o["document_id"] == "doc-2")
        assert orphan["status"] == "partial_embeddings"
        assert orphan["missing"] == 1

    def test_no_orphans_when_complete(self, tmp_db):
        _, conn = tmp_db
        # Doc with all chunks having embeddings
        conn.execute(
            "INSERT INTO knowledge_documents (id, title, category, content_hash, content, uploaded_by) "
            "VALUES ('complete-doc', 'Complete', 'docs', 'hash-c', 'text', 'admin')"
        )
        for i in range(2):
            conn.execute(
                "INSERT INTO knowledge_chunks (id, document_id, chunk_index, content, embedding) "
                "VALUES (?, 'complete-doc', ?, 'text', '[0.1]')",
                (f"c-{i}", i)
            )
        conn.commit()

        orphans = knowledge_health.find_orphans(conn)
        assert len(orphans) == 0


# ── find_stale_chunks Tests ──────────────────────────────────────────────

class TestFindStaleChunks:
    def test_finds_chunks_without_parent(self, tmp_db):
        _, conn = tmp_db
        # Chunk pointing to nonexistent doc
        conn.execute(
            "INSERT INTO knowledge_chunks (id, document_id, chunk_index, content) "
            "VALUES ('stale-chunk', 'no-such-doc', 0, 'orphaned text')"
        )
        conn.commit()

        stale = knowledge_health.find_stale_chunks(conn)
        assert len(stale) == 1
        assert stale[0]["chunk_id"] == "stale-chunk"
        assert stale[0]["doc_id"] == "no-such-doc"

    def test_no_stale_when_clean(self, knowledge_db):
        _, conn = knowledge_db
        stale = knowledge_health.find_stale_chunks(conn)
        assert len(stale) == 0


# ── prune_stale Tests ────────────────────────────────────────────────────

class TestPruneStale:
    def test_prune_removes_stale_chunks(self, tmp_db):
        _, conn = tmp_db
        conn.execute(
            "INSERT INTO knowledge_chunks (id, document_id, chunk_index, content) "
            "VALUES ('stale-1', 'gone-doc', 0, 'text')"
        )
        conn.commit()

        stale = [{"chunk_id": "stale-1", "doc_id": "gone-doc", "index": 0}]
        pruned = knowledge_health.prune_stale(conn, stale)
        assert pruned == 1

        remaining = conn.execute("SELECT COUNT(*) FROM knowledge_chunks WHERE id = 'stale-1'").fetchone()[0]
        assert remaining == 0

    def test_prune_noop_when_empty(self, tmp_db):
        _, conn = tmp_db
        pruned = knowledge_health.prune_stale(conn, [])
        assert pruned == 0


# ── find_unsynced_cag Tests ──────────────────────────────────────────────

class TestFindUnsyncedCAG:
    def test_counts_unsynced(self, tmp_db):
        _, conn = tmp_db
        conn.execute("INSERT INTO users (id) VALUES ('u1')")
        conn.execute(
            "INSERT INTO registry_projects (id, owner_id, slug, name) VALUES ('p1', 'u1', 'u1/test', 'Test')"
        )
        # 2 ABIs, neither has a matching contract_definition
        conn.execute(
            "INSERT INTO registry_abis (id, project_id, contract_name, chain, abi_json, contract_address) "
            "VALUES ('a1', 'p1', 'C1', 'ethereum', '[]', '0x111')"
        )
        conn.execute(
            "INSERT INTO registry_abis (id, project_id, contract_name, chain, abi_json, contract_address) "
            "VALUES ('a2', 'p1', 'C2', 'ethereum', '[]', '0x222')"
        )
        # 1 contract_definition matching a1
        conn.execute(
            "INSERT INTO contract_definitions (id, name, chain, address, description) "
            "VALUES ('cd-1', 'C1', 'ethereum', '0x111', 'desc')"
        )
        conn.commit()

        unsynced = knowledge_health.find_unsynced_cag(conn)
        assert unsynced == 1  # a2 not synced

    def test_handles_missing_tables(self, tmp_path):
        # DB with no tables at all
        db_file = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db_file))
        result = knowledge_health.find_unsynced_cag(conn)
        assert result == 0
        conn.close()


# ── format_report Tests ──────────────────────────────────────────────────

class TestKnowledgeFormatReport:
    def test_healthy_report(self):
        stats = {
            "total_documents": 10, "total_chunks": 50, "total_embeddings": 50,
            "embeddings_complete": True, "new_documents_24h": 0, "new_chunks_24h": 0,
            "cag_contracts": 5, "cag_functions": 5, "db_size_mb": 1.2,
        }
        text, html = knowledge_health.format_report(stats, [], [], 0, 0)
        assert "HEALTHY" in text
        assert "#00d4aa" in html  # green

    def test_issues_report(self):
        stats = {
            "total_documents": 10, "total_chunks": 50, "total_embeddings": 40,
            "embeddings_complete": False, "new_documents_24h": 0, "new_chunks_24h": 0,
            "cag_contracts": 0, "cag_functions": 0, "db_size_mb": 1.0,
        }
        orphans = [{"document_id": "d1", "title": "Test", "format": "txt", "chunks": 5, "embeddings": 3, "missing": 2, "status": "partial_embeddings"}]
        text, html = knowledge_health.format_report(stats, orphans, [], 0, 0)
        assert "ISSUES DETECTED" in text
        assert "#ff6b6b" in html  # red

    def test_report_includes_all_metrics(self):
        stats = {
            "total_documents": 1, "total_chunks": 2, "total_embeddings": 2,
            "embeddings_complete": True, "new_documents_24h": 0, "new_chunks_24h": 0,
            "cag_contracts": 0, "cag_functions": 0, "db_size_mb": 0.1,
        }
        text, _ = knowledge_health.format_report(stats, [], [], 0, 0)
        for keyword in ["Documents:", "Chunks:", "Embeddings:", "CAG contracts:", "Orphaned docs:", "Stale chunks:", "DB size:"]:
            assert keyword in text
