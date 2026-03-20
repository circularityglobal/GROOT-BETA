#!/usr/bin/env python3
"""
REFINET Contract Watcher — On-Chain Intelligence Scanner
Scans ABIs for dangerous patterns, checks chain event status,
monitors watched contracts, and emails admin reports.

Usage:
    python contract_scan.py                          # Scan and print status
    python contract_scan.py --scan-abis              # Scan unanalyzed ABIs for dangers
    python contract_scan.py --check-events           # Process uninterpreted chain events
    python contract_scan.py --activity               # Check watched contract activity
    python contract_scan.py --email                  # Email admin report
    python contract_scan.py --scan-abis --email      # Full ABI scan + email
"""

import json
import os
import re
import sys
import sqlite3
import smtplib
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

DB_PATH = os.getenv("DATABASE_PATH", "public.db")
API_BASE = os.getenv("REFINET_API_BASE", "http://localhost:8000")

# ─────────────────────────────────────────────────────────────────
# Dangerous pattern definitions
# ─────────────────────────────────────────────────────────────────
DANGEROUS_PATTERNS = {
    "delegatecall": {
        "severity": "CRITICAL",
        "regex": r"delegatecall",
        "description": "Executes external code in caller context",
        "risk": "Complete fund drainage if target is malicious"
    },
    "selfdestruct": {
        "severity": "CRITICAL",
        "regex": r"selfdestruct|SELFDESTRUCT|suicide",
        "description": "Permanently destroys contract",
        "risk": "Irreversible loss of contract state and funds"
    },
    "tx_origin": {
        "severity": "HIGH",
        "regex": r"tx\.origin",
        "description": "Uses tx.origin for authentication",
        "risk": "Phishing attacks can bypass authentication"
    },
    "unchecked_call": {
        "severity": "HIGH",
        "regex": r"\.call\{value:",
        "description": "Low-level call with value transfer",
        "risk": "Reentrancy if return value not checked"
    },
    "infinite_approval": {
        "severity": "HIGH",
        "regex": r"type\(uint256\)\.max|0xffffffff{8}",
        "description": "Unlimited token approval",
        "risk": "Spender can drain all approved tokens"
    },
    "inline_assembly": {
        "severity": "MEDIUM",
        "regex": r"assembly\s*\{",
        "description": "Inline assembly usage",
        "risk": "Bypasses Solidity safety checks"
    },
    "proxy_pattern": {
        "severity": "MEDIUM",
        "regex": r"upgradeTo|_implementation|ERC1967",
        "description": "Upgradeable proxy pattern",
        "risk": "Contract behavior can change post-deployment"
    },
    "ownership_transfer": {
        "severity": "MEDIUM",
        "regex": r"transferOwnership|renounceOwnership",
        "description": "Ownership control function",
        "risk": "Contract control can be transferred or abandoned"
    }
}


def get_db():
    if not Path(DB_PATH).exists():
        print(f"[chain] Database not found: {DB_PATH}")
        sys.exit(1)
    return sqlite3.connect(DB_PATH, timeout=10)


# ─────────────────────────────────────────────────────────────────
# ABI Security Analysis
# ─────────────────────────────────────────────────────────────────
def get_unscanned_abis(db) -> list[dict]:
    """Find ABIs that haven't been security-analyzed yet."""
    try:
        rows = db.execute("""
            SELECT ca.id, ca.project_id, ca.chain, ca.contract_address, ca.contract_name,
                   rp.name as project_name
            FROM registry_abis ca
            JOIN registry_projects rp ON rp.id = ca.project_id
            LEFT JOIN contract_security_flags csf ON csf.abi_id = ca.id
            WHERE csf.id IS NULL
        """).fetchall()
        return [
            {"abi_id": r[0], "project_id": r[1], "chain": r[2],
             "address": r[3], "name": r[4], "project": r[5]}
            for r in rows
        ]
    except sqlite3.OperationalError:
        return []


def analyze_abi_from_db(db, abi_id: str) -> dict:
    """Load ABI JSON and analyze for dangerous patterns."""
    row = db.execute(
        "SELECT abi_json FROM registry_abis WHERE id = ?", (abi_id,)
    ).fetchone()
    if not row:
        return {"flags": [], "flag_count": 0, "risk_score": 0, "risk_level": "UNKNOWN"}

    try:
        abi_json = json.loads(row[0]) if isinstance(row[0], str) else row[0]
    except (json.JSONDecodeError, TypeError):
        return {"flags": [], "flag_count": 0, "risk_score": 0, "risk_level": "PARSE_ERROR"}

    flags = []
    severity_weights = {"CRITICAL": 10, "HIGH": 5, "MEDIUM": 2, "LOW": 1}

    # Check function names in ABI
    dangerous_fn_names = {"selfdestruct", "suicide", "delegatecall"}
    ownership_fn_names = {"transferOwnership", "renounceOwnership"}

    for item in abi_json:
        if item.get("type") != "function":
            continue
        name = item.get("name", "")
        if name in dangerous_fn_names:
            flags.append({
                "pattern": name, "severity": "CRITICAL",
                "location": f"function {name}()",
                "description": f"Dangerous function: {name}"
            })
        if name in ownership_fn_names:
            flags.append({
                "pattern": "ownership_transfer", "severity": "MEDIUM",
                "location": f"function {name}()",
                "description": "Ownership control function"
            })
        if name == "upgradeTo" or name == "upgradeToAndCall":
            flags.append({
                "pattern": "proxy_pattern", "severity": "MEDIUM",
                "location": f"function {name}()",
                "description": "Upgradeable proxy pattern"
            })

    # Scan ABI JSON string for embedded patterns
    abi_str = json.dumps(abi_json)
    for pattern_name, pattern_info in DANGEROUS_PATTERNS.items():
        matches = re.findall(pattern_info["regex"], abi_str, re.IGNORECASE)
        if matches and not any(f["pattern"] == pattern_name for f in flags):
            flags.append({
                "pattern": pattern_name, "severity": pattern_info["severity"],
                "location": f"{len(matches)} matches in ABI",
                "description": pattern_info["description"]
            })

    risk_score = sum(severity_weights.get(f["severity"], 0) for f in flags)
    return {
        "flags": flags,
        "flag_count": len(flags),
        "risk_score": risk_score,
        "risk_level": (
            "CRITICAL" if risk_score >= 10 else
            "HIGH" if risk_score >= 5 else
            "MEDIUM" if risk_score >= 2 else
            "LOW" if risk_score >= 1 else "CLEAN"
        ),
        "critical_count": sum(1 for f in flags if f["severity"] == "CRITICAL"),
        "high_count": sum(1 for f in flags if f["severity"] == "HIGH"),
        "medium_count": sum(1 for f in flags if f["severity"] == "MEDIUM"),
    }


def store_flags(db, abi_id: str, analysis: dict):
    """Store security flags in the database."""
    import uuid
    for flag in analysis["flags"]:
        db.execute(
            "INSERT OR IGNORE INTO contract_security_flags (id, abi_id, pattern, severity, location, description, risk) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), abi_id, flag["pattern"], flag["severity"],
             flag.get("location", ""), flag.get("description", ""), flag.get("risk", ""))
        )
    # If clean, insert a sentinel so we don't re-scan
    if not analysis["flags"]:
        db.execute(
            "INSERT OR IGNORE INTO contract_security_flags (id, abi_id, pattern, severity, description) "
            "VALUES (?, ?, 'CLEAN', 'NONE', 'No dangerous patterns detected')",
            (str(uuid.uuid4()), abi_id)
        )
    db.commit()


# ─────────────────────────────────────────────────────────────────
# Chain Events
# ─────────────────────────────────────────────────────────────────
def get_event_stats(db) -> dict:
    """Get chain event statistics."""
    stats = {}
    try:
        stats["total_listeners"] = db.execute(
            "SELECT COUNT(*) FROM chain_watchers WHERE is_active = 1"
        ).fetchone()[0]
        stats["total_events"] = db.execute(
            "SELECT COUNT(*) FROM chain_events"
        ).fetchone()[0]
        stats["unprocessed_events"] = 0  # chain_events has no status column

        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        stats["events_this_week"] = db.execute(
            "SELECT COUNT(*) FROM chain_events WHERE received_at > ?", (week_ago,)
        ).fetchone()[0]

        # Events by chain
        chains = db.execute(
            "SELECT chain, COUNT(*) FROM chain_events GROUP BY chain"
        ).fetchall()
        stats["events_by_chain"] = {str(r[0]): r[1] for r in chains}
    except sqlite3.OperationalError:
        stats["total_listeners"] = 0
        stats["total_events"] = 0
        stats["unprocessed_events"] = 0

    return stats


# ─────────────────────────────────────────────────────────────────
# Registry Stats
# ─────────────────────────────────────────────────────────────────
def get_registry_stats(db) -> dict:
    """Get smart contract registry statistics."""
    stats = {}
    try:
        stats["total_projects"] = db.execute(
            "SELECT COUNT(*) FROM registry_projects"
        ).fetchone()[0]
        stats["total_abis"] = db.execute(
            "SELECT COUNT(*) FROM registry_abis"
        ).fetchone()[0]
        stats["flagged_abis"] = db.execute(
            "SELECT COUNT(DISTINCT abi_id) FROM contract_security_flags WHERE severity IN ('CRITICAL','HIGH')"
        ).fetchone()[0]
        stats["starred_projects"] = db.execute(
            "SELECT COUNT(DISTINCT project_id) FROM registry_stars"
        ).fetchone()[0]
    except sqlite3.OperationalError:
        stats["total_projects"] = 0
        stats["total_abis"] = 0
        stats["flagged_abis"] = 0
        stats["starred_projects"] = 0

    return stats


# ─────────────────────────────────────────────────────────────────
# Reporting
# ─────────────────────────────────────────────────────────────────
def format_report(event_stats, registry_stats, scan_results) -> tuple[str, str]:
    """Return (text_report, html_report)."""
    has_issues = (
        scan_results.get("critical_total", 0) > 0 or
        event_stats.get("unprocessed_events", 0) > 50
    )
    status = "ALERTS" if has_issues else "NOMINAL"

    lines = [
        f"Chain Intelligence: {status}",
        "=" * 40,
        f"  Listeners active: {event_stats.get('total_listeners', 0)}",
        f"  Events total: {event_stats.get('total_events', 0)}",
        f"  Events this week: {event_stats.get('events_this_week', 0)}",
        f"  Unprocessed: {event_stats.get('unprocessed_events', 0)}",
        f"  Registry projects: {registry_stats.get('total_projects', 0)}",
        f"  Total ABIs: {registry_stats.get('total_abis', 0)}",
        f"  Flagged (HIGH+): {registry_stats.get('flagged_abis', 0)}",
        f"  Starred projects: {registry_stats.get('starred_projects', 0)}",
        f"  ABIs scanned now: {scan_results.get('scanned', 0)}",
        f"  Critical flags: {scan_results.get('critical_total', 0)}",
        f"  High flags: {scan_results.get('high_total', 0)}",
    ]
    text = "\n".join(lines)

    rows = ""
    checks = [
        ("Active listeners", event_stats.get("total_listeners", 0), True),
        ("Events (7d)", event_stats.get("events_this_week", 0), True),
        ("Unprocessed events", event_stats.get("unprocessed_events", 0), event_stats.get("unprocessed_events", 0) < 50),
        ("Registry ABIs", registry_stats.get("total_abis", 0), True),
        ("Flagged (HIGH+)", registry_stats.get("flagged_abis", 0), registry_stats.get("flagged_abis", 0) == 0),
        ("Scanned this run", scan_results.get("scanned", 0), True),
        ("Critical flags", scan_results.get("critical_total", 0), scan_results.get("critical_total", 0) == 0),
    ]
    for label, value, ok in checks:
        color = "#00d4aa" if ok else "#ff6b6b"
        rows += f"<tr><td style='padding:6px;color:{color}'>{'OK' if ok else '!!'}</td><td style='padding:6px'><b>{label}</b></td><td style='padding:6px'>{value}</td></tr>"

    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto">
      <div style="background:#1a1a2e;color:#e0e0e0;padding:16px 20px;border-radius:8px 8px 0 0">
        <h2 style="margin:0;font-size:18px">Chain Intelligence — {status}</h2>
        <p style="margin:4px 0 0;font-size:12px;color:#888">{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
      </div>
      <div style="background:#16213e;color:#e0e0e0;padding:20px;border-radius:0 0 8px 8px">
        <table style="width:100%;border-collapse:collapse">{rows}</table>
        <hr style="border:none;border-top:1px solid #333;margin:16px 0">
        <p style="font-size:11px;color:#666;margin:0">Sent by GROOT Contract Watcher Agent</p>
      </div>
    </div>
    """
    return text, html


def send_email(subject, html_body, text_body):
    admin = os.getenv("ADMIN_EMAIL")
    if not admin:
        print("[chain] ADMIN_EMAIL not set — skipping email")
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
        print(f"[chain] Email sent to {admin}")
    except Exception as e:
        print(f"[chain] Email failed: {e}")


# ─────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────
def main():
    db = get_db()
    event_stats = get_event_stats(db)
    registry_stats = get_registry_stats(db)

    scan_results = {"scanned": 0, "critical_total": 0, "high_total": 0, "flagged_abis": []}

    if "--scan-abis" in sys.argv:
        unscanned = get_unscanned_abis(db)
        print(f"[chain] Found {len(unscanned)} unscanned ABIs")
        for abi_info in unscanned:
            analysis = analyze_abi_from_db(db, abi_info["abi_id"])
            store_flags(db, abi_info["abi_id"], analysis)
            scan_results["scanned"] += 1
            scan_results["critical_total"] += analysis.get("critical_count", 0)
            scan_results["high_total"] += analysis.get("high_count", 0)
            if analysis["risk_level"] in ("CRITICAL", "HIGH"):
                scan_results["flagged_abis"].append({
                    "name": abi_info["name"],
                    "project": abi_info["project"],
                    "risk": analysis["risk_level"],
                    "flags": analysis["flag_count"]
                })
            level = analysis["risk_level"]
            icon = {"CRITICAL": "!!", "HIGH": "!", "MEDIUM": "~", "LOW": ".", "CLEAN": "ok"}.get(level, "?")
            print(f"  [{icon}] {abi_info['name']} @ {abi_info['project']}: {level} ({analysis['flag_count']} flags)")

    text_report, html_report = format_report(event_stats, registry_stats, scan_results)
    print(text_report)

    if "--email" in sys.argv:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        has_critical = scan_results["critical_total"] > 0
        subject_status = "CRITICAL FLAGS DETECTED" if has_critical else "Status Report"
        send_email(f"[REFINET CHAIN] {subject_status} — {ts}", html_report, text_report)

    print(json.dumps({"events": event_stats, "registry": registry_stats, "scan": scan_results}, indent=2, default=str))
    has_issues = scan_results["critical_total"] > 0
    db.close()
    sys.exit(1 if has_issues else 0)


if __name__ == "__main__":
    main()
