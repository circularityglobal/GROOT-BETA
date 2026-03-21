#!/usr/bin/env python3
"""
REFINET SDK Gateway — SDK Indexer
Builds a searchable catalog of all public SDKs organized by chain.
Writes to memory/working/sdk_catalog.json for offline analysis.

Usage:
    python3 sdk_indexer.py                  # Build index, print summary
    python3 sdk_indexer.py --output json    # Full catalog to stdout
    python3 sdk_indexer.py --email          # Email summary to admin
"""

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# Allow running from repo root or skills/ directory
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

SCRIPT_META = {
    "name": "sdk_indexer",
    "description": "Build searchable catalog of all public SDKs per chain",
    "category": "maintenance",
    "requires_admin": False,
}

CATALOG_PATH = REPO_ROOT / "memory" / "working" / "sdk_catalog.json"
LOG_PATH = REPO_ROOT / "memory" / "working" / "sdk_queries.jsonl"


def build_catalog(db) -> dict:
    """
    Build a complete catalog of all public SDKs organized by chain.
    Returns a dict suitable for JSON serialization.
    """
    from api.models.brain import ContractRepo, SDKDefinition
    from api.models.chain import ContractDeployment, SupportedChain

    # Get all public contracts with their SDKs
    rows = (
        db.query(ContractRepo, SDKDefinition)
        .outerjoin(SDKDefinition, SDKDefinition.contract_id == ContractRepo.id)
        .filter(
            ContractRepo.is_public == True,  # noqa: E712
            ContractRepo.is_active == True,  # noqa: E712
        )
        .order_by(ContractRepo.chain, ContractRepo.name)
        .all()
    )

    chains = {}
    total_contracts = 0
    total_sdks = 0
    stale_count = 0

    for contract, sdk in rows:
        total_contracts += 1
        chain_key = contract.chain or "unknown"

        if chain_key not in chains:
            # Look up chain metadata
            chain_meta = db.query(SupportedChain).filter(
                SupportedChain.short_name == chain_key,
            ).first()
            chains[chain_key] = {
                "chain_id": chain_meta.chain_id if chain_meta else None,
                "chain_name": chain_meta.name if chain_meta else chain_key,
                "contract_count": 0,
                "contracts": [],
            }

        chain_entry = chains[chain_key]
        chain_entry["contract_count"] += 1

        entry = {
            "name": contract.name,
            "slug": contract.slug,
            "address": contract.address,
            "description": contract.description,
            "has_sdk": False,
            "function_count": 0,
            "sdk_hash": None,
        }

        if sdk and sdk.is_public and sdk.sdk_json:
            total_sdks += 1
            entry["has_sdk"] = True
            entry["sdk_hash"] = sdk.sdk_hash

            try:
                sdk_data = json.loads(sdk.sdk_json)
                pub_fns = sdk_data.get("functions", {}).get("public", [])
                admin_fns = sdk_data.get("functions", {}).get("owner_admin", [])
                entry["function_count"] = len(pub_fns) + len(admin_fns)
                entry["public_function_count"] = len(pub_fns)
                entry["admin_function_count"] = len(admin_fns)
            except (json.JSONDecodeError, TypeError):
                pass

            # Check staleness
            if contract.abi_json and contract.abi_hash:
                import hashlib
                current_hash = hashlib.sha256(contract.abi_json.encode()).hexdigest()
                if current_hash != contract.abi_hash:
                    stale_count += 1
                    entry["is_stale"] = True

        # Get multi-chain deployments
        deployments = db.query(ContractDeployment, SupportedChain).join(
            SupportedChain, SupportedChain.chain_id == ContractDeployment.chain_id,
        ).filter(
            ContractDeployment.contract_id == contract.id,
        ).all()

        if deployments:
            entry["deployments"] = [
                {"chain": sc.short_name, "chain_id": sc.chain_id, "address": dep.address}
                for dep, sc in deployments
            ]

        chain_entry["contracts"].append(entry)

    # Get top queried contracts
    top_queried = _get_top_queried()

    catalog = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_contracts": total_contracts,
        "total_sdks": total_sdks,
        "stale_count": stale_count,
        "chains": chains,
        "top_queried": top_queried,
    }

    return catalog


def _get_top_queried(limit: int = 10) -> list[str]:
    """Get top queried contract IDs from usage log."""
    if not LOG_PATH.exists():
        return []

    counter = Counter()
    try:
        with open(LOG_PATH, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    counter[entry.get("cid", "unknown")] += 1
                except (json.JSONDecodeError, KeyError):
                    continue
    except Exception:
        return []

    return [cid for cid, _ in counter.most_common(limit)]


def format_summary(catalog: dict) -> str:
    """Format catalog as a human-readable summary."""
    lines = [
        "=" * 60,
        "REFINET SDK Gateway — Catalog Index",
        f"Generated: {catalog['generated_at']}",
        "=" * 60,
        "",
        f"Total public contracts: {catalog['total_contracts']}",
        f"SDKs available:        {catalog['total_sdks']}",
        f"Stale SDKs:            {catalog['stale_count']}",
        "",
        "--- By Chain ---",
    ]

    for chain_key, chain_data in sorted(catalog["chains"].items()):
        chain_id = chain_data.get("chain_id", "?")
        count = chain_data["contract_count"]
        sdk_count = sum(1 for c in chain_data["contracts"] if c.get("has_sdk"))
        lines.append(f"  {chain_key} (ID: {chain_id}): {count} contracts, {sdk_count} SDKs")

        for c in chain_data["contracts"][:5]:  # Show first 5 per chain
            status = "SDK" if c.get("has_sdk") else "no SDK"
            stale = " [STALE]" if c.get("is_stale") else ""
            fns = c.get("function_count", 0)
            lines.append(f"    - {c['name']} ({c.get('slug', '?')}): {status}, {fns} functions{stale}")

        remaining = count - min(count, 5)
        if remaining > 0:
            lines.append(f"    ... and {remaining} more")

    if catalog.get("top_queried"):
        lines.append("")
        lines.append("--- Top Queried ---")
        for cid in catalog["top_queried"]:
            lines.append(f"  {cid}")

    return "\n".join(lines)


def send_summary_email(summary: str):
    """Send summary via admin email alert."""
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

        msg = MIMEText(summary, "plain")
        msg["Subject"] = "[SDK-GATEWAY] Catalog Index Report"
        msg["From"] = mail_from
        msg["To"] = admin_email

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.send_message(msg)
        print(f"Summary emailed to {admin_email}")
    except Exception as e:
        print(f"Email failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="SDK Gateway Indexer")
    parser.add_argument("--output", choices=["json", "summary"], default="summary",
                        help="Output format (default: summary)")
    parser.add_argument("--email", action="store_true", help="Send summary via email")
    args = parser.parse_args()

    # Set up database path
    db_path = os.environ.get("DATABASE_PATH", str(REPO_ROOT / "data" / "public.db"))
    os.environ.setdefault("DATABASE_PATH", db_path)

    from api.database import get_public_db

    with get_public_db() as db:
        catalog = build_catalog(db)

    # Write catalog to file
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CATALOG_PATH, "w") as f:
        json.dump(catalog, f, indent=2)
    print(f"Catalog written to {CATALOG_PATH}")

    if args.output == "json":
        print(json.dumps(catalog, indent=2))
    else:
        summary = format_summary(catalog)
        print(summary)

        if args.email:
            send_summary_email(summary)


if __name__ == "__main__":
    main()
