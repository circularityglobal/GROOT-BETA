#!/usr/bin/env python3
"""
REFINET SDK Gateway — Sync Worker
Scans for stale/missing/corrupt SDKs and auto-regenerates them.
Reads usage analytics from sdk_queries.jsonl for hot-contract reporting.

Usage:
    python3 sdk_sync_worker.py                    # Dry-run scan
    python3 sdk_sync_worker.py --repair           # Auto-regenerate stale SDKs
    python3 sdk_sync_worker.py --repair --email   # Full cycle with email report
"""

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Allow running from repo root or skills/ directory
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

SCRIPT_META = {
    "name": "sdk_sync_worker",
    "description": "Scan for stale/missing SDKs and auto-regenerate",
    "category": "maintenance",
    "requires_admin": False,
}

LOG_PATH = REPO_ROOT / "memory" / "working" / "sdk_queries.jsonl"


def _sha256(data: str) -> str:
    """SHA-256 hex digest of a string."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def scan_sdks(db, repair: bool = False):
    """
    Scan all public contracts for SDK issues.
    Returns a report dict with counts and details.
    """
    from api.models.brain import ContractRepo, SDKDefinition

    report = {
        "total_public_contracts": 0,
        "total_sdks": 0,
        "stale": [],
        "missing": [],
        "corrupt": [],
        "repaired": [],
        "errors": [],
    }

    # All public, active contracts
    contracts = db.query(ContractRepo).filter(
        ContractRepo.is_public == True,  # noqa: E712
        ContractRepo.is_active == True,  # noqa: E712
        ContractRepo.status.in_(["parsed", "published"]),
    ).all()

    report["total_public_contracts"] = len(contracts)

    for contract in contracts:
        sdk = db.query(SDKDefinition).filter(
            SDKDefinition.contract_id == contract.id,
        ).first()

        if not sdk:
            report["missing"].append({
                "name": contract.name,
                "slug": contract.slug,
                "chain": contract.chain,
                "reason": "No SDK row exists",
            })
            if repair:
                try:
                    _regenerate_sdk(db, contract)
                    report["repaired"].append(contract.slug)
                except Exception as e:
                    report["errors"].append(f"{contract.slug}: {e}")
            continue

        report["total_sdks"] += 1

        # Check integrity: sdk_hash vs actual hash
        actual_hash = _sha256(sdk.sdk_json) if sdk.sdk_json else None
        if sdk.sdk_hash and actual_hash and sdk.sdk_hash != actual_hash:
            report["corrupt"].append({
                "name": contract.name,
                "slug": contract.slug,
                "reason": "sdk_hash mismatch (data corruption)",
            })
            if repair:
                try:
                    _regenerate_sdk(db, contract)
                    report["repaired"].append(contract.slug)
                except Exception as e:
                    report["errors"].append(f"{contract.slug}: {e}")
            continue

        # Check staleness: ABI hash at generation vs current ABI
        if contract.abi_json:
            current_abi_hash = _sha256(contract.abi_json)
            # The SDK was generated from the ABI — if ABI changed, SDK is stale
            if contract.abi_hash and contract.abi_hash != current_abi_hash:
                report["stale"].append({
                    "name": contract.name,
                    "slug": contract.slug,
                    "chain": contract.chain,
                    "reason": "ABI updated since SDK generation",
                })
                if repair:
                    try:
                        _regenerate_sdk(db, contract)
                        report["repaired"].append(contract.slug)
                    except Exception as e:
                        report["errors"].append(f"{contract.slug}: {e}")

    return report


def _regenerate_sdk(db, contract):
    """Regenerate SDK for a contract from its current ABI."""
    from api.services.abi_parser import parse_abi
    from api.services.sdk_generator import generate_sdk

    if not contract.abi_json:
        raise ValueError("No ABI available")

    abi_data = json.loads(contract.abi_json)
    parsed = parse_abi(abi_data)

    # Update parsed functions in DB
    from api.models.brain import ContractFunction
    db.query(ContractFunction).filter(
        ContractFunction.contract_id == contract.id,
    ).delete()

    for fn in parsed.get("functions", []):
        db.add(ContractFunction(
            contract_id=contract.id,
            function_name=fn["name"],
            function_type=fn.get("type", "function"),
            selector=fn.get("selector"),
            signature=fn.get("signature"),
            visibility=fn.get("visibility", "public"),
            state_mutability=fn.get("state_mutability", "nonpayable"),
            access_level=fn.get("access_level", "public"),
            access_modifier=fn.get("access_modifier"),
            access_roles=json.dumps(fn.get("access_roles", [])),
            inputs=json.dumps(fn.get("inputs", [])),
            outputs=json.dumps(fn.get("outputs", [])),
            is_sdk_enabled=True,
            is_dangerous=fn.get("is_dangerous", False),
            danger_reason=fn.get("danger_reason"),
            natspec_notice=fn.get("natspec_notice"),
        ))

    # Generate SDK
    sdk_result = generate_sdk(contract, parsed)
    sdk_json = json.dumps(sdk_result)
    sdk_hash = _sha256(sdk_json)

    # Upsert SDK definition
    from api.models.brain import SDKDefinition
    existing = db.query(SDKDefinition).filter(
        SDKDefinition.contract_id == contract.id,
    ).first()

    if existing:
        existing.sdk_json = sdk_json
        existing.sdk_hash = sdk_hash
        existing.is_public = contract.is_public
        existing.generated_at = datetime.now(timezone.utc)
    else:
        db.add(SDKDefinition(
            contract_id=contract.id,
            user_id=contract.user_id,
            sdk_json=sdk_json,
            sdk_hash=sdk_hash,
            is_public=contract.is_public,
            chain=contract.chain,
            contract_address=contract.address,
            generated_at=datetime.now(timezone.utc),
        ))

    db.flush()

    # Bridge to knowledge base
    try:
        from api.services.contract_brain import ingest_sdk_to_knowledge
        sdk = db.query(SDKDefinition).filter(
            SDKDefinition.contract_id == contract.id,
        ).first()
        if sdk:
            ingest_sdk_to_knowledge(db, contract, sdk)
    except Exception:
        pass  # Knowledge bridge is best-effort


def get_usage_analytics():
    """Read sdk_queries.jsonl and return usage stats."""
    if not LOG_PATH.exists():
        return {"total_queries": 0, "top_contracts": [], "queries_last_24h": 0}

    counter = Counter()
    total = 0
    recent = 0
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    try:
        with open(LOG_PATH, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    total += 1
                    counter[entry.get("cid", "unknown")] += 1
                    ts = datetime.fromisoformat(entry["ts"])
                    if ts > cutoff:
                        recent += 1
                except (json.JSONDecodeError, KeyError):
                    continue
    except Exception:
        return {"total_queries": 0, "top_contracts": [], "queries_last_24h": 0}

    return {
        "total_queries": total,
        "queries_last_24h": recent,
        "top_contracts": counter.most_common(10),
    }


def prune_old_logs(max_age_days: int = 30):
    """Remove log entries older than max_age_days."""
    if not LOG_PATH.exists():
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    kept = []
    pruned = 0

    with open(LOG_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                ts = datetime.fromisoformat(entry["ts"])
                if ts > cutoff:
                    kept.append(line)
                else:
                    pruned += 1
            except (json.JSONDecodeError, KeyError):
                kept.append(line)  # Keep unparseable entries

    with open(LOG_PATH, "w") as f:
        f.write("\n".join(kept) + "\n" if kept else "")

    return pruned


def format_report(report: dict, analytics: dict) -> str:
    """Format scan results as a human-readable report."""
    lines = [
        "=" * 60,
        "REFINET SDK Gateway — Sync Worker Report",
        f"Timestamp: {datetime.now(timezone.utc).isoformat()}",
        "=" * 60,
        "",
        f"Public contracts:  {report['total_public_contracts']}",
        f"SDKs present:      {report['total_sdks']}",
        f"Stale SDKs:        {len(report['stale'])}",
        f"Missing SDKs:      {len(report['missing'])}",
        f"Corrupt SDKs:      {len(report['corrupt'])}",
        f"Repaired:          {len(report['repaired'])}",
        f"Errors:            {len(report['errors'])}",
        "",
    ]

    if report["stale"]:
        lines.append("--- Stale SDKs ---")
        for s in report["stale"]:
            lines.append(f"  {s['slug']} ({s['chain']}): {s['reason']}")
        lines.append("")

    if report["missing"]:
        lines.append("--- Missing SDKs ---")
        for m in report["missing"]:
            lines.append(f"  {m['slug']} ({m['chain']}): {m['reason']}")
        lines.append("")

    if report["corrupt"]:
        lines.append("--- Corrupt SDKs ---")
        for c in report["corrupt"]:
            lines.append(f"  {c['slug']}: {c['reason']}")
        lines.append("")

    if report["repaired"]:
        lines.append("--- Repaired ---")
        for r in report["repaired"]:
            lines.append(f"  {r}")
        lines.append("")

    if report["errors"]:
        lines.append("--- Errors ---")
        for e in report["errors"]:
            lines.append(f"  {e}")
        lines.append("")

    lines.append(f"Total SDK queries (all time): {analytics['total_queries']}")
    lines.append(f"Queries last 24h:             {analytics['queries_last_24h']}")
    if analytics["top_contracts"]:
        lines.append("Top queried contracts:")
        for cid, count in analytics["top_contracts"]:
            lines.append(f"  {cid}: {count} queries")

    return "\n".join(lines)


def send_report_email(report_text: str):
    """Send report via admin email alert."""
    try:
        import smtplib
        from email.mime.text import MIMEText

        admin_email = os.environ.get("ADMIN_EMAIL")
        smtp_host = os.environ.get("SMTP_HOST", "localhost")
        smtp_port = int(os.environ.get("SMTP_PORT", "8025"))
        mail_from = os.environ.get("MAIL_FROM", "groot@refinet.cloud")

        if not admin_email:
            print("ADMIN_EMAIL not set — skipping email")
            return

        msg = MIMEText(report_text, "plain")
        msg["Subject"] = "[SDK-GATEWAY] Sync Worker Report"
        msg["From"] = mail_from
        msg["To"] = admin_email

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.send_message(msg)
        print(f"Report emailed to {admin_email}")
    except Exception as e:
        print(f"Email failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="SDK Gateway Sync Worker")
    parser.add_argument("--repair", action="store_true", help="Auto-regenerate stale/missing SDKs")
    parser.add_argument("--email", action="store_true", help="Send report via email")
    parser.add_argument("--prune-days", type=int, default=30, help="Prune log entries older than N days")
    args = parser.parse_args()

    # Set up database path
    db_path = os.environ.get("DATABASE_PATH", str(REPO_ROOT / "data" / "public.db"))
    os.environ.setdefault("DATABASE_PATH", db_path)

    from api.database import get_public_db

    with get_public_db() as db:
        report = scan_sdks(db, repair=args.repair)
        if args.repair:
            db.commit()

    analytics = get_usage_analytics()
    pruned = prune_old_logs(args.prune_days)
    if pruned:
        print(f"Pruned {pruned} old log entries")

    report_text = format_report(report, analytics)
    print(report_text)

    if args.email:
        send_report_email(report_text)

    # Exit with error code if issues found
    issues = len(report["stale"]) + len(report["missing"]) + len(report["corrupt"])
    if issues > 0 and not args.repair:
        sys.exit(1)


if __name__ == "__main__":
    main()
