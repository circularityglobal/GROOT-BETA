#!/usr/bin/env python3
"""
Backfill SDK Knowledge — Bridge existing public SDKs into knowledge chunks.
Run once after deploying the SDK→Knowledge bridge to populate RAG with
existing contract SDKs that were published before the bridge was added.

Usage:
    python scripts/backfill_sdk_knowledge.py
"""

SCRIPT_META = {
    "name": "backfill_sdk_knowledge",
    "description": "Ingest existing public SDK definitions into RAG knowledge base",
    "category": "maintenance",
    "requires_admin": True,
}

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.database import init_databases, create_public_session
from api.models.brain import ContractRepo, SDKDefinition
from api.services.contract_brain import ingest_sdk_to_knowledge


def main():
    init_databases()
    db = create_public_session()

    try:
        # Find all public SDKs
        sdks = db.query(SDKDefinition).filter(
            SDKDefinition.is_public == True,  # noqa: E712
        ).all()

        print(f"Found {len(sdks)} public SDK definitions to backfill")

        ingested = 0
        skipped = 0
        for sdk in sdks:
            contract = db.query(ContractRepo).filter(
                ContractRepo.id == sdk.contract_id,
                ContractRepo.is_active == True,  # noqa: E712
            ).first()

            if not contract:
                skipped += 1
                continue

            doc_id = ingest_sdk_to_knowledge(db, contract, sdk)
            if doc_id:
                ingested += 1
                print(f"  Ingested: {contract.name} ({contract.chain}) → {doc_id}")
            else:
                skipped += 1
                print(f"  Skipped (already exists): {contract.name}")

        db.commit()
        print(f"\nDone: {ingested} ingested, {skipped} skipped")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
