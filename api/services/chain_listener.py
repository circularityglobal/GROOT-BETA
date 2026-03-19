"""
REFINET Cloud — On-Chain Event Listener
Polls blockchain RPCs for contract events and emits them to the EventBus.
Zero external dependencies beyond web3 (already in requirements).
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from api.models.public import ChainWatcher, ChainEvent
from api.services.event_bus import EventBus

logger = logging.getLogger("refinet.chain")

# Default RPC endpoints (free public endpoints, rate-limited)
DEFAULT_RPCS = {
    "ethereum": "https://eth.llamarpc.com",
    "base": "https://mainnet.base.org",
    "arbitrum": "https://arb1.arbitrum.io/rpc",
    "polygon": "https://polygon-rpc.com",
    "sepolia": "https://rpc.sepolia.org",
}


# ── CRUD ─────────────────────────────────────────────────────────

def create_watcher(
    db: Session,
    user_id: str,
    chain: str,
    contract_address: str,
    event_names: Optional[list[str]] = None,
    rpc_url: Optional[str] = None,
    from_block: int = 0,
    polling_interval: int = 30,
) -> ChainWatcher:
    """Create a new chain event watcher."""
    watcher = ChainWatcher(
        id=str(uuid.uuid4()),
        user_id=user_id,
        chain=chain,
        contract_address=contract_address.lower(),
        event_names=json.dumps(event_names) if event_names else None,
        rpc_url=rpc_url,
        from_block=from_block,
        last_processed_block=from_block,
        polling_interval_seconds=polling_interval,
    )
    db.add(watcher)
    db.flush()
    return watcher


def list_watchers(db: Session, user_id: str) -> list[dict]:
    """List all watchers for a user."""
    watchers = db.query(ChainWatcher).filter(
        ChainWatcher.user_id == user_id,
    ).all()
    return [
        {
            "id": w.id,
            "chain": w.chain,
            "contract_address": w.contract_address,
            "event_names": json.loads(w.event_names) if w.event_names else None,
            "is_active": w.is_active,
            "last_processed_block": w.last_processed_block,
            "polling_interval_seconds": w.polling_interval_seconds,
            "created_at": w.created_at.isoformat() if w.created_at else None,
        }
        for w in watchers
    ]


def delete_watcher(db: Session, watcher_id: str, user_id: str) -> bool:
    """Delete a watcher."""
    watcher = db.query(ChainWatcher).filter(
        ChainWatcher.id == watcher_id,
        ChainWatcher.user_id == user_id,
    ).first()
    if not watcher:
        return False
    db.delete(watcher)
    db.flush()
    return True


def list_events(
    db: Session,
    watcher_id: str,
    limit: int = 50,
) -> list[dict]:
    """List detected events for a watcher."""
    events = db.query(ChainEvent).filter(
        ChainEvent.watcher_id == watcher_id,
    ).order_by(ChainEvent.block_number.desc()).limit(limit).all()

    return [
        {
            "id": e.id,
            "event_name": e.event_name,
            "block_number": e.block_number,
            "tx_hash": e.tx_hash,
            "decoded_data": json.loads(e.decoded_data) if e.decoded_data else None,
            "received_at": e.received_at.isoformat() if e.received_at else None,
        }
        for e in events
    ]


# ── Polling Engine ───────────────────────────────────────────────

async def poll_watcher(db: Session, watcher: ChainWatcher) -> int:
    """
    Poll a single watcher for new events.
    Uses eth_getLogs to fetch logs from last_processed_block to latest.
    Returns the number of new events detected.
    """
    rpc_url = watcher.rpc_url or DEFAULT_RPCS.get(watcher.chain)
    if not rpc_url:
        logger.warning(f"No RPC URL for chain {watcher.chain}")
        return 0

    try:
        import urllib.request

        # Get latest block number
        latest_block = await _rpc_call(rpc_url, "eth_blockNumber", [])
        if not latest_block:
            return 0
        latest_block = int(latest_block, 16)

        from_block = watcher.last_processed_block + 1
        if from_block > latest_block:
            return 0

        # Cap range to avoid massive responses
        to_block = min(from_block + 1000, latest_block)

        # Build filter params
        filter_params = {
            "fromBlock": hex(from_block),
            "toBlock": hex(to_block),
            "address": watcher.contract_address,
        }

        # Filter by specific event topics if specified
        if watcher.event_names:
            event_list = json.loads(watcher.event_names)
            if event_list:
                from api.services.crypto_utils import keccak256
                topics = [
                    "0x" + keccak256(sig.encode()).hex()
                    for sig in event_list
                ]
                filter_params["topics"] = [topics]

        # Fetch logs
        logs = await _rpc_call(rpc_url, "eth_getLogs", [filter_params])
        if not logs or not isinstance(logs, list):
            watcher.last_processed_block = to_block
            db.flush()
            return 0

        # Store events
        new_events = 0
        for log in logs:
            event = ChainEvent(
                id=str(uuid.uuid4()),
                watcher_id=watcher.id,
                chain=watcher.chain,
                contract_address=watcher.contract_address,
                event_name=_decode_event_name(log),
                block_number=int(log.get("blockNumber", "0x0"), 16),
                tx_hash=log.get("transactionHash", ""),
                log_index=int(log.get("logIndex", "0x0"), 16),
                decoded_data=json.dumps(_decode_log_data(log)),
                raw_data=json.dumps(log),
            )
            db.add(event)
            new_events += 1

            # Emit event to EventBus
            await EventBus.get().publish("chain.event.detected", {
                "watcher_id": watcher.id,
                "chain": watcher.chain,
                "contract_address": watcher.contract_address,
                "event_name": event.event_name,
                "block_number": event.block_number,
                "tx_hash": event.tx_hash,
            })

        watcher.last_processed_block = to_block
        db.flush()

        if new_events:
            logger.info(f"Watcher {watcher.id}: {new_events} events detected (blocks {from_block}–{to_block})")

        return new_events

    except Exception as e:
        logger.error(f"Chain poll error for watcher {watcher.id}: {e}")
        return 0


async def poll_all_watchers():
    """Poll all active watchers. Called by the scheduler."""
    from api.database import get_public_session

    with get_public_session() as db:
        watchers = db.query(ChainWatcher).filter(
            ChainWatcher.is_active == True,  # noqa: E712
        ).all()

        total_events = 0
        for watcher in watchers:
            events = await poll_watcher(db, watcher)
            total_events += events

        db.commit()

        if total_events:
            logger.info(f"Chain poll complete: {total_events} total events across {len(watchers)} watchers")


# ── Helpers ──────────────────────────────────────────────────────

async def _rpc_call(rpc_url: str, method: str, params: list):
    """Make an async JSON-RPC call."""
    import urllib.request
    import asyncio

    def _call():
        payload = json.dumps({
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1,
        }).encode()

        req = urllib.request.Request(
            rpc_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            return result.get("result")

    return await asyncio.get_event_loop().run_in_executor(None, _call)


def _decode_event_name(log: dict) -> Optional[str]:
    """Extract event name from log topics (topic[0] is the event signature hash)."""
    topics = log.get("topics", [])
    if topics:
        return topics[0][:10]  # First 10 chars of topic hash as identifier
    return None


def _decode_log_data(log: dict) -> dict:
    """Basic log data extraction (without full ABI decoding)."""
    return {
        "topics": log.get("topics", []),
        "data": log.get("data", "0x"),
        "block_number": int(log.get("blockNumber", "0x0"), 16),
        "transaction_index": int(log.get("transactionIndex", "0x0"), 16),
    }
