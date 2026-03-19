"""
REFINET Cloud — Deterministic I/O Workers
Five scheduled workers that wire GROOT's three brains together.
All workers are pure input→transform→output pipelines — zero LLM dependency.

Workers:
1. knowledge_sync   — Reconcile SDK changes to knowledge base
2. knowledge_gc     — Clean orphaned knowledge chunks/documents
3. chain_event_indexer — Convert chain events to searchable knowledge
4. data_ttl         — Enforce four-tier data retention policies
5. capability_index — Build deterministic contract capability map
"""

import hashlib
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger("refinet.workers")


# ── Data Tier Classification ───────────────────────────────────────
# Reference map: every table classified into one of four access tiers.
# Workers enforce TTL for short-term and long-term tiers.

DATA_TIERS = {
    "private": {
        "description": "Never exposed via public API — indefinite retention, admin-managed",
        "tables": [
            "server_secrets", "custodial_wallets", "wallet_shares",
            "admin_audit_log", "role_assignments", "system_config",
            "mcp_server_registry", "product_registry",
        ],
    },
    "short_term": {
        "description": "Auto-expires — high write volume, TTL-based pruning",
        "tables": {
            "siwe_nonces": "10 minutes (existing handler)",
            "refresh_tokens": "30 days (existing handler)",
            "agent_memory_working": "1 hour (existing handler)",
            "iot_telemetry": "30 days (existing handler)",
            "health_check_logs": "30 days",
            "wallet_sessions": "30 days (inactive only)",
        },
    },
    "long_term": {
        "description": "Persistent but prunable — configurable retention windows",
        "tables": {
            "chain_events": "90 days",
            "usage_records": "180 days",
            "agent_memory_episodic": "30 days",
            "script_executions": "90 days",
        },
    },
    "public": {
        "description": "Discoverable by GROOT/MCP — owner-controlled lifetime",
        "tables": [
            "contract_repos (is_public=True)",
            "sdk_definitions (is_public=True)",
            "knowledge_documents (visibility=public)",
            "app_listings (is_published=True)",
            "registry_projects (visibility=public)",
        ],
    },
}


# ══════════════════════════════════════════════════════════════════
# Worker 1: Knowledge Sync — SDK ↔ Knowledge Reconciliation
# ══════════════════════════════════════════════════════════════════

def knowledge_sync_worker():
    """
    Reconcile SDK definitions with the knowledge base.
    When a user toggles is_sdk_enabled on a function, the SDK regenerates
    but knowledge doesn't update. This worker catches all drift.

    I/O Pipeline:
      INPUT:  All public SDKDefinitions joined with ContractRepo
      TRANSFORM: Compare sdk_hash vs knowledge content_hash
      OUTPUT: Upsert/delete KnowledgeDocuments to match current SDK state
    """
    from api.database import get_public_db
    from api.models.brain import ContractRepo, SDKDefinition
    from api.models.knowledge import KnowledgeDocument, KnowledgeChunk
    from api.services.contract_brain import ingest_sdk_to_knowledge

    synced = 0
    removed = 0

    with get_public_db() as db:
        # 1. Find all public SDKs and their corresponding knowledge docs
        sdks = db.query(SDKDefinition, ContractRepo).join(
            ContractRepo, SDKDefinition.contract_id == ContractRepo.id,
        ).filter(
            ContractRepo.is_active == True,  # noqa: E712
        ).all()

        for sdk, contract in sdks:
            source_filename = f"{contract.slug}.sdk.json"
            existing_doc = db.query(KnowledgeDocument).filter(
                KnowledgeDocument.source_filename == source_filename,
            ).first()

            if contract.is_public and sdk.is_public:
                # Contract is public — ensure knowledge is current
                sdk_content_hash = hashlib.sha256(sdk.sdk_json.encode()).hexdigest()

                if existing_doc:
                    if existing_doc.content_hash == sdk_content_hash:
                        continue  # Already in sync
                    # Hash changed — delete old doc (cascades to chunks), re-ingest
                    db.query(KnowledgeChunk).filter(
                        KnowledgeChunk.document_id == existing_doc.id,
                    ).delete()
                    db.delete(existing_doc)
                    db.flush()

                # Ingest fresh SDK into knowledge
                ingest_sdk_to_knowledge(db, contract, sdk)
                synced += 1

            else:
                # Contract is private — remove knowledge doc if it exists
                if existing_doc:
                    db.query(KnowledgeChunk).filter(
                        KnowledgeChunk.document_id == existing_doc.id,
                    ).delete()
                    db.delete(existing_doc)
                    removed += 1

        db.flush()

    if synced or removed:
        logger.info(f"knowledge_sync: synced={synced}, removed={removed}")


# ══════════════════════════════════════════════════════════════════
# Worker 2: Knowledge GC — Orphan Cleanup
# ══════════════════════════════════════════════════════════════════

def knowledge_gc_worker():
    """
    Clean orphaned knowledge chunks and inactive documents.
    Prevents stale data from polluting GROOT's search results.

    I/O Pipeline:
      INPUT:  Chunks with missing/inactive parent documents
      TRANSFORM: Collect orphan IDs
      OUTPUT: DELETE orphaned chunks + inactive documents
    """
    from api.database import get_public_db
    from api.models.knowledge import KnowledgeDocument, KnowledgeChunk

    orphan_chunks = 0
    inactive_docs = 0

    with get_public_db() as db:
        # 1. Delete chunks whose parent document no longer exists
        all_chunk_doc_ids = db.query(KnowledgeChunk.document_id).distinct().all()
        for (doc_id,) in all_chunk_doc_ids:
            exists = db.query(KnowledgeDocument.id).filter(
                KnowledgeDocument.id == doc_id,
            ).first()
            if not exists:
                count = db.query(KnowledgeChunk).filter(
                    KnowledgeChunk.document_id == doc_id,
                ).delete()
                orphan_chunks += count

        # 2. Delete chunks of inactive documents
        inactive = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.is_active == False,  # noqa: E712
        ).all()
        for doc in inactive:
            count = db.query(KnowledgeChunk).filter(
                KnowledgeChunk.document_id == doc.id,
            ).delete()
            orphan_chunks += count
            db.delete(doc)
            inactive_docs += 1

        db.flush()

    if orphan_chunks or inactive_docs:
        logger.info(
            f"knowledge_gc: orphan_chunks={orphan_chunks}, inactive_docs={inactive_docs}"
        )


# ══════════════════════════════════════════════════════════════════
# Worker 3: Chain Event Indexer — On-Chain Events → Knowledge
# ══════════════════════════════════════════════════════════════════

def chain_event_indexer():
    """
    Convert chain events into searchable knowledge documents.
    Chain listener stores ChainEvent rows but GROOT can't search them.
    This worker builds deterministic markdown summaries — no LLM needed.

    I/O Pipeline:
      INPUT:  ChainEvent rows since last indexed timestamp
      TRANSFORM: Group by (chain, contract_address), build markdown summary
      OUTPUT: Upsert KnowledgeDocuments with category 'chain-activity'
    """
    from api.database import get_public_db, get_internal_db
    from api.models.public import ChainEvent, ChainWatcher
    from api.models.internal import SystemConfig
    from api.models.knowledge import KnowledgeDocument, KnowledgeChunk

    # Read last indexed timestamp from SystemConfig
    last_run_iso: Optional[str] = None
    with get_internal_db() as int_db:
        marker = int_db.query(SystemConfig).filter(
            SystemConfig.key == "chain_indexer.last_run",
        ).first()
        if marker:
            last_run_iso = marker.value

    cutoff = datetime.min.replace(tzinfo=timezone.utc)
    if last_run_iso:
        try:
            cutoff = datetime.fromisoformat(last_run_iso)
        except (ValueError, TypeError):
            pass

    indexed_count = 0

    with get_public_db() as db:
        # Query new events since last run
        query = db.query(ChainEvent).filter(
            ChainEvent.received_at > cutoff,
        ).order_by(ChainEvent.received_at.asc())

        events = query.limit(5000).all()
        if not events:
            return

        # Group by (chain, contract_address)
        groups: dict[tuple[str, str], list] = defaultdict(list)
        for ev in events:
            groups[(ev.chain, ev.contract_address)].append(ev)

        for (chain, address), group_events in groups.items():
            # Build deterministic markdown summary
            event_counts: dict[str, int] = defaultdict(int)
            latest_block = 0
            recent_txs: list[str] = []

            for ev in group_events:
                event_name = ev.event_name or "Unknown"
                event_counts[event_name] += 1
                if ev.block_number > latest_block:
                    latest_block = ev.block_number
                if ev.tx_hash and ev.tx_hash not in recent_txs:
                    recent_txs.append(ev.tx_hash)

            # Build markdown content
            parts = [
                f"# On-Chain Activity: {address[:10]}...{address[-6:]} ({chain})",
                f"\nChain: {chain}",
                f"Contract: {address}",
                f"Latest block: {latest_block}",
                f"Events indexed: {sum(event_counts.values())}",
                "\n## Event Summary",
            ]
            for name, count in sorted(event_counts.items(), key=lambda x: -x[1]):
                parts.append(f"- {name}: {count} occurrences")

            if recent_txs:
                parts.append("\n## Recent Transactions")
                for tx in recent_txs[-5:]:
                    parts.append(f"- `{tx}`")

            content = "\n".join(parts)
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            source_filename = f"chain:{chain}:{address}"

            # Upsert: delete old doc if exists, then create new
            existing = db.query(KnowledgeDocument).filter(
                KnowledgeDocument.source_filename == source_filename,
            ).first()
            if existing:
                db.query(KnowledgeChunk).filter(
                    KnowledgeChunk.document_id == existing.id,
                ).delete()
                db.delete(existing)
                db.flush()

            from api.services.rag import ingest_document
            ingest_document(
                db=db,
                title=f"On-chain: {address[:10]}...{address[-6:]} ({chain})",
                content=content,
                category="chain-activity",
                uploaded_by="system:chain_indexer",
                source_filename=source_filename,
                tags=["chain-activity", chain, address[:10]],
            )
            indexed_count += 1

        # Track the latest event timestamp for next run
        latest_ts = max(ev.received_at for ev in events if ev.received_at)

    # Update marker in internal DB
    if indexed_count > 0:
        with get_internal_db() as int_db:
            marker = int_db.query(SystemConfig).filter(
                SystemConfig.key == "chain_indexer.last_run",
            ).first()
            ts_value = latest_ts.isoformat() if latest_ts else datetime.now(timezone.utc).isoformat()
            if marker:
                marker.value = ts_value
                marker.updated_at = datetime.now(timezone.utc)
            else:
                int_db.add(SystemConfig(
                    key="chain_indexer.last_run",
                    value=ts_value,
                    data_type="string",
                    description="Last chain event indexed timestamp",
                    updated_by="system:chain_indexer",
                ))
            int_db.flush()

        logger.info(f"chain_event_indexer: indexed {indexed_count} contract groups")


# ══════════════════════════════════════════════════════════════════
# Worker 4: Data TTL — Tiered Retention Enforcement
# ══════════════════════════════════════════════════════════════════

def data_ttl_worker():
    """
    Enforce four-tier data retention policies.
    Deletes expired rows from short-term and long-term tables.
    Does NOT touch private tier (admin-managed) or public tier (owner-controlled).

    I/O Pipeline:
      INPUT:  Rows older than defined TTL per table
      TRANSFORM: Compute cutoff timestamps
      OUTPUT: DELETE expired rows, log counts
    """
    from api.database import get_public_db, get_internal_db
    from api.models.public import ChainEvent, UsageRecord, WalletSession
    from api.models.agent_engine import AgentMemoryEpisodic
    from api.models.internal import HealthCheckLog, ScriptExecution

    now = datetime.now(timezone.utc)
    results: dict[str, int] = {}

    # ── Public DB tables ──
    with get_public_db() as db:
        # Chain events: 90 days
        cutoff_90d = now - timedelta(days=90)
        count = db.query(ChainEvent).filter(
            ChainEvent.received_at < cutoff_90d,
        ).delete()
        if count:
            results["chain_events"] = count

        # Usage records: 180 days
        cutoff_180d = now - timedelta(days=180)
        count = db.query(UsageRecord).filter(
            UsageRecord.created_at < cutoff_180d,
        ).delete()
        if count:
            results["usage_records"] = count

        # Episodic memory: 30 days
        cutoff_30d = now - timedelta(days=30)
        count = db.query(AgentMemoryEpisodic).filter(
            AgentMemoryEpisodic.timestamp < cutoff_30d,
        ).delete()
        if count:
            results["agent_memory_episodic"] = count

        # Inactive wallet sessions: 30 days old + not active
        count = db.query(WalletSession).filter(
            WalletSession.is_active == False,  # noqa: E712
            WalletSession.created_at < cutoff_30d,
        ).delete()
        if count:
            results["wallet_sessions_inactive"] = count

        db.flush()

    # ── Internal DB tables ──
    with get_internal_db() as int_db:
        # Health check logs: 30 days
        count = int_db.query(HealthCheckLog).filter(
            HealthCheckLog.timestamp < cutoff_30d,
        ).delete()
        if count:
            results["health_check_logs"] = count

        # Script executions: 90 days (use completed_at or started_at)
        count = int_db.query(ScriptExecution).filter(
            ScriptExecution.completed_at != None,  # noqa: E711
            ScriptExecution.completed_at < cutoff_90d,
        ).delete()
        if count:
            results["script_executions"] = count

        int_db.flush()

    if results:
        total = sum(results.values())
        detail = ", ".join(f"{k}={v}" for k, v in results.items())
        logger.info(f"data_ttl: pruned {total} rows — {detail}")


# ══════════════════════════════════════════════════════════════════
# Worker 5: Capability Index — Deterministic Contract Map
# ══════════════════════════════════════════════════════════════════

def capability_index_worker():
    """
    Build a deterministic JSON map of all public contract functions.
    Gives GROOT a fast, non-embedding lookup for contract capabilities.
    Only writes when the index actually changes (SHA-256 guard).

    I/O Pipeline:
      INPUT:  All public ContractRepo + enabled ContractFunctions
      TRANSFORM: Build JSON capability map, compute SHA-256
      OUTPUT: Store in SystemConfig if hash changed
    """
    from api.database import get_public_db, get_internal_db
    from api.models.brain import ContractRepo, ContractFunction
    from api.models.internal import SystemConfig

    with get_public_db() as db:
        contracts = db.query(ContractRepo).filter(
            ContractRepo.is_public == True,  # noqa: E712
            ContractRepo.is_active == True,  # noqa: E712
        ).order_by(ContractRepo.slug).all()

        capability_map = {"contracts": [], "generated_at": datetime.now(timezone.utc).isoformat()}

        for contract in contracts:
            functions = db.query(ContractFunction).filter(
                ContractFunction.contract_id == contract.id,
                ContractFunction.is_sdk_enabled == True,  # noqa: E712
            ).order_by(ContractFunction.function_name).all()

            fn_list = []
            for fn in functions:
                fn_list.append({
                    "name": fn.function_name,
                    "selector": fn.selector,
                    "signature": fn.signature,
                    "access_level": fn.access_level,
                    "state_mutability": fn.state_mutability,
                })

            if fn_list:
                capability_map["contracts"].append({
                    "slug": contract.slug,
                    "name": contract.name,
                    "chain": contract.chain,
                    "address": contract.address,
                    "description": contract.description or "",
                    "functions": fn_list,
                })

    # Compute hash of the capability map (excluding timestamp for stability)
    hashable = json.dumps(
        [c for c in capability_map["contracts"]],
        sort_keys=True, separators=(",", ":"),
    )
    new_hash = hashlib.sha256(hashable.encode()).hexdigest()

    # Only write if hash changed
    with get_internal_db() as int_db:
        hash_row = int_db.query(SystemConfig).filter(
            SystemConfig.key == "capability_index.hash",
        ).first()

        if hash_row and hash_row.value == new_hash:
            return  # No changes

        # Update or insert the index
        index_row = int_db.query(SystemConfig).filter(
            SystemConfig.key == "capability_index.json",
        ).first()
        index_json = json.dumps(capability_map, separators=(",", ":"))

        if index_row:
            index_row.value = index_json
            index_row.updated_at = datetime.now(timezone.utc)
            index_row.updated_by = "system:capability_index"
        else:
            int_db.add(SystemConfig(
                key="capability_index.json",
                value=index_json,
                data_type="json",
                description="Deterministic map of all public contract functions for GROOT",
                updated_by="system:capability_index",
            ))

        if hash_row:
            hash_row.value = new_hash
            hash_row.updated_at = datetime.now(timezone.utc)
        else:
            int_db.add(SystemConfig(
                key="capability_index.hash",
                value=new_hash,
                data_type="string",
                description="SHA-256 of capability index for change detection",
                updated_by="system:capability_index",
            ))

        int_db.flush()

        contract_count = len(capability_map["contracts"])
        fn_count = sum(len(c["functions"]) for c in capability_map["contracts"])
        logger.info(
            f"capability_index: updated — {contract_count} contracts, {fn_count} functions"
        )
