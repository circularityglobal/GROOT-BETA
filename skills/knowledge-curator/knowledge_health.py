#!/usr/bin/env python3
"""
REFINET Knowledge Base Health Check
Runs all knowledge integrity checks, detects orphans, prunes stale chunks,
benchmarks search quality, and emails admin report.

Usage:
    python knowledge_health.py                       # Check and print
    python knowledge_health.py --repair              # Check + fix orphans + prune stale
    python knowledge_health.py --benchmark           # Run embedding quality benchmark
    python knowledge_health.py --email               # Email admin report
    python knowledge_health.py --repair --email      # Full run: check, fix, email
"""

import json
import os
import sys
import sqlite3
import smtplib
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

DB_PATH = os.getenv("DATABASE_PATH", "public.db")
API_BASE = os.getenv("REFINET_API_BASE", "http://localhost:8000")


def get_db():
    if not Path(DB_PATH).exists():
        print(f"[knowledge] Database not found: {DB_PATH}")
        sys.exit(1)
    return sqlite3.connect(DB_PATH, timeout=10)


def get_stats(db) -> dict:
    """Get overall knowledge base statistics."""
    stats = {}

    stats["total_documents"] = db.execute(
        "SELECT COUNT(*) FROM documents"
    ).fetchone()[0]

    stats["total_chunks"] = db.execute(
        "SELECT COUNT(*) FROM document_chunks"
    ).fetchone()[0]

    stats["total_embeddings"] = db.execute(
        "SELECT COUNT(*) FROM chunk_embeddings"
    ).fetchone()[0]

    stats["embeddings_complete"] = stats["total_embeddings"] == stats["total_chunks"]

    # Documents added in last 24h
    yesterday = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    stats["new_documents_24h"] = db.execute(
        "SELECT COUNT(*) FROM documents WHERE created_at > ?", (yesterday,)
    ).fetchone()[0]

    stats["new_chunks_24h"] = db.execute(
        "SELECT COUNT(*) FROM document_chunks WHERE created_at > ?", (yesterday,)
    ).fetchone()[0]

    # DB file size
    stats["db_size_mb"] = round(Path(DB_PATH).stat().st_size / (1024 * 1024), 1)

    # CAG stats
    try:
        stats["cag_contracts"] = db.execute(
            "SELECT COUNT(DISTINCT abi_id) FROM cag_index"
        ).fetchone()[0]
        stats["cag_functions"] = db.execute(
            "SELECT COUNT(*) FROM cag_index"
        ).fetchone()[0]
    except sqlite3.OperationalError:
        stats["cag_contracts"] = 0
        stats["cag_functions"] = 0

    return stats


def find_orphans(db) -> list[dict]:
    """Find documents with missing or incomplete embeddings."""
    try:
        rows = db.execute("""
            SELECT d.id, d.title, d.format,
                   COUNT(dc.id) as chunk_count,
                   COUNT(ce.id) as embedding_count
            FROM documents d
            LEFT JOIN document_chunks dc ON dc.document_id = d.id
            LEFT JOIN chunk_embeddings ce ON ce.chunk_id = dc.id
            GROUP BY d.id
            HAVING chunk_count = 0 OR embedding_count < chunk_count
        """).fetchall()
    except sqlite3.OperationalError:
        return []

    return [
        {
            "document_id": r[0],
            "title": r[1],
            "format": r[2],
            "chunks": r[3],
            "embeddings": r[4],
            "missing": r[3] - r[4],
            "status": "no_chunks" if r[3] == 0 else "partial_embeddings"
        }
        for r in rows
    ]


def find_stale_chunks(db) -> list[dict]:
    """Find chunks whose parent document no longer exists."""
    try:
        rows = db.execute("""
            SELECT dc.id, dc.document_id, dc.chunk_index
            FROM document_chunks dc
            LEFT JOIN documents d ON d.id = dc.document_id
            WHERE d.id IS NULL
        """).fetchall()
    except sqlite3.OperationalError:
        return []

    return [{"chunk_id": r[0], "doc_id": r[1], "index": r[2]} for r in rows]


def prune_stale(db, stale_chunks: list[dict]) -> int:
    """Remove stale chunks and their embeddings."""
    if not stale_chunks:
        return 0
    chunk_ids = [s["chunk_id"] for s in stale_chunks]
    ph = ",".join("?" * len(chunk_ids))
    db.execute(f"DELETE FROM chunk_embeddings WHERE chunk_id IN ({ph})", chunk_ids)
    db.execute(f"DELETE FROM document_chunks WHERE id IN ({ph})", chunk_ids)
    db.commit()
    return len(chunk_ids)


def find_unsynced_cag(db) -> int:
    """Count ABIs not yet in CAG index."""
    try:
        return db.execute("""
            SELECT COUNT(*)
            FROM contract_abis ca
            LEFT JOIN cag_index ci ON ci.abi_id = ca.id
            WHERE ci.id IS NULL
        """).fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def format_report(stats, orphans, stale, unsynced_cag, pruned=0) -> tuple[str, str]:
    """Return (text_report, html_report)."""
    all_ok = (
        len(orphans) == 0 and
        len(stale) == 0 and
        stats.get("embeddings_complete", False) and
        unsynced_cag == 0
    )

    status = "HEALTHY" if all_ok else "ISSUES DETECTED"

    lines = [
        f"Knowledge Base: {status}",
        "=" * 40,
        f"  Documents: {stats['total_documents']}",
        f"  Chunks: {stats['total_chunks']}",
        f"  Embeddings: {stats['total_embeddings']}",
        f"  Complete: {'YES' if stats['embeddings_complete'] else 'NO'}",
        f"  New docs (24h): {stats.get('new_documents_24h', 0)}",
        f"  New chunks (24h): {stats.get('new_chunks_24h', 0)}",
        f"  CAG contracts: {stats.get('cag_contracts', 0)}",
        f"  Unsynced ABIs: {unsynced_cag}",
        f"  Orphaned docs: {len(orphans)}",
        f"  Stale chunks: {len(stale)}",
        f"  Pruned: {pruned}",
        f"  DB size: {stats.get('db_size_mb', '?')} MB",
    ]
    text = "\n".join(lines)

    # HTML for email
    rows = ""
    checks = [
        ("Documents", stats["total_documents"], True),
        ("Chunks", stats["total_chunks"], stats["total_chunks"] > 0),
        ("Embeddings complete", "Yes" if stats["embeddings_complete"] else "No", stats["embeddings_complete"]),
        ("Orphaned documents", len(orphans), len(orphans) == 0),
        ("Stale chunks", len(stale), len(stale) == 0),
        ("Unsynced CAG ABIs", unsynced_cag, unsynced_cag == 0),
        ("DB size", f"{stats.get('db_size_mb', '?')} MB", True),
    ]
    for label, value, ok in checks:
        icon = "OK" if ok else "ISSUE"
        color = "#00d4aa" if ok else "#ff6b6b"
        rows += f"<tr><td style='padding:6px;color:{color}'>{icon}</td><td style='padding:6px'><b>{label}</b></td><td style='padding:6px'>{value}</td></tr>"

    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto">
      <div style="background:#1a1a2e;color:#e0e0e0;padding:16px 20px;border-radius:8px 8px 0 0">
        <h2 style="margin:0;font-size:18px">Knowledge Base — {status}</h2>
        <p style="margin:4px 0 0;font-size:12px;color:#888">{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
      </div>
      <div style="background:#16213e;color:#e0e0e0;padding:20px;border-radius:0 0 8px 8px">
        <table style="width:100%;border-collapse:collapse">{rows}</table>
        <hr style="border:none;border-top:1px solid #333;margin:16px 0">
        <p style="font-size:11px;color:#666;margin:0">
          Sent by GROOT Knowledge Curator Agent
        </p>
      </div>
    </div>
    """
    return text, html


def send_email(subject, html_body, text_body):
    admin = os.getenv("ADMIN_EMAIL")
    if not admin:
        print("[knowledge] ADMIN_EMAIL not set — skipping email")
        return
    msg = MIMEMultipart("alternative")
    msg["From"] = os.getenv("MAIL_FROM", "groot@refinet.io")
    msg["To"] = admin
    msg["Subject"] = subject
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    try:
        with smtplib.SMTP(
            os.getenv("SMTP_HOST", "127.0.0.1"),
            int(os.getenv("SMTP_PORT", "8025"))
        ) as server:
            server.send_message(msg)
        print(f"[knowledge] Email sent to {admin}")
    except Exception as e:
        print(f"[knowledge] Email failed: {e}")


def main():
    db = get_db()
    stats = get_stats(db)
    orphans = find_orphans(db)
    stale = find_stale_chunks(db)
    unsynced = find_unsynced_cag(db)
    pruned = 0

    if "--repair" in sys.argv:
        if stale:
            pruned = prune_stale(db, stale)
            print(f"[knowledge] Pruned {pruned} stale chunks")
        if orphans:
            print(f"[knowledge] Found {len(orphans)} orphans — re-embedding requires API call")
            for o in orphans:
                print(f"  - {o['title']} ({o['status']}, missing {o['missing']} embeddings)")
            # Re-embedding via API: POST /knowledge/documents/{id}/reindex
            try:
                import httpx
                for o in orphans:
                    r = httpx.post(f"{API_BASE}/knowledge/documents/{o['document_id']}/reindex")
                    if r.status_code == 200:
                        print(f"  [OK] Re-indexed: {o['title']}")
                    else:
                        print(f"  [FAIL] {o['title']}: {r.status_code}")
            except Exception as e:
                print(f"  [SKIP] API re-index unavailable: {e}")

    text_report, html_report = format_report(stats, orphans, stale, unsynced, pruned)
    print(text_report)

    if "--email" in sys.argv:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        status_str = "Healthy" if len(orphans) == 0 and len(stale) == 0 else "Issues Detected"
        send_email(
            f"[REFINET KNOWLEDGE] {status_str} — {ts}",
            html_report,
            text_report
        )

    print(json.dumps(stats, indent=2))
    all_ok = len(orphans) == 0 and len(stale) == 0 and stats.get("embeddings_complete", False)
    db.close()
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
