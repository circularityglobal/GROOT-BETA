"""
REFINET Cloud — Trigger Router
Unified routing from all 5 trigger sources to agent tasks.

Subscribes to EventBus patterns and normalizes incoming events
into AgentTask entries, optionally running the cognitive loop.

Trigger sources: heartbeat, cron, webhook, chain, messenger
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger("refinet.trigger_router")


# ── Trigger Payload ──────────────────────────────────────────────

@dataclass
class TriggerPayload:
    """Normalized trigger event from any source."""
    source: str          # heartbeat | cron | webhook | chain | messenger
    event_type: str      # e.g., "chain.event.transfer", "device.telemetry.received"
    data: dict = field(default_factory=dict)
    target_agent_id: Optional[str] = None  # Override: route to specific agent
    user_id: Optional[str] = None          # Owner context
    priority: int = 5    # 1=highest, 10=lowest


# ── Event → Agent Mapping ────────────────────────────────────────

# Maps event patterns to agent archetype names.
# The trigger router resolves archetype names to actual registered agents.
TRIGGER_MAP: dict[str, str] = {
    "device.telemetry.*": "device-monitor",
    "device.status.*": "device-monitor",
    "chain.event.*": "contract-watcher",
    "chain.watcher.*": "contract-watcher",
    "knowledge.document.*": "knowledge-curator",
    "agent.task.completed": "orchestrator",
    "system.health.*": "maintenance",
    "pipeline.run.completed": "orchestrator",
    "pipeline.run.failed": "orchestrator",
    "pipeline.approval.needed": "orchestrator",
    "broker.session.*": "orchestrator",
}

# Rate limiting: track last trigger time per agent archetype
_last_trigger: dict[str, float] = {}
_MIN_TRIGGER_INTERVAL = 10.0  # seconds between auto-triggered tasks per agent


# ── Router Logic ─────────────────────────────────────────────────

async def route_trigger(payload: TriggerPayload) -> Optional[str]:
    """
    Route a trigger payload to the appropriate agent and create a task.

    Returns the created task ID, or None if no agent matched or rate-limited.
    """
    from api.database import get_db_session
    from api.models.public import AgentRegistration
    from api.services.agent_engine import create_task, AgentCognitiveLoop

    # Determine target agent archetype
    target_archetype = None

    if payload.target_agent_id:
        # Direct targeting — skip mapping
        target_archetype = None  # Will use target_agent_id directly
    else:
        # Match event_type against TRIGGER_MAP patterns
        target_archetype = _match_event_pattern(payload.event_type)

    if not target_archetype and not payload.target_agent_id:
        logger.debug(f"No agent mapping for event: {payload.event_type}")
        return None

    # Rate limiting
    rate_key = payload.target_agent_id or target_archetype
    now = time.monotonic()
    if rate_key in _last_trigger:
        elapsed = now - _last_trigger[rate_key]
        if elapsed < _MIN_TRIGGER_INTERVAL:
            logger.debug(
                f"Rate limited: {rate_key} triggered {elapsed:.1f}s ago "
                f"(min interval: {_MIN_TRIGGER_INTERVAL}s)"
            )
            return None

    _last_trigger[rate_key] = now

    # Find the actual agent registration
    try:
        db = next(get_db_session())
    except Exception as e:
        logger.error(f"Failed to get DB session for trigger routing: {e}")
        return None

    try:
        if payload.target_agent_id:
            agent = db.query(AgentRegistration).filter(
                AgentRegistration.id == payload.target_agent_id,
            ).first()
        else:
            # Find an agent whose name matches the archetype
            agent = db.query(AgentRegistration).filter(
                AgentRegistration.name == target_archetype,
                AgentRegistration.is_active == True,  # noqa: E712
            ).first()

        if not agent:
            logger.debug(f"No registered agent found for archetype: {target_archetype}")
            return None

        # Build task description from trigger data
        description = _build_task_description(payload)

        # Create the task
        task = create_task(
            db=db,
            agent_id=agent.id,
            user_id=payload.user_id or agent.user_id,
            description=description,
        )
        db.commit()

        logger.info(
            f"Trigger routed: {payload.source}/{payload.event_type} → "
            f"agent={agent.name} task={task.id}"
        )

        # Run the cognitive loop in background
        asyncio.create_task(_run_triggered_task(agent.id, agent.user_id, task.id))

        return task.id

    except Exception as e:
        logger.error(f"Trigger routing error: {e}")
        db.rollback()
        return None
    finally:
        db.close()


async def _run_triggered_task(agent_id: str, user_id: str, task_id: str):
    """Run a triggered task's cognitive loop in the background."""
    from api.database import get_db_session
    from api.services.agent_engine import get_task, AgentCognitiveLoop

    try:
        db = next(get_db_session())
        task = get_task(db, task_id, agent_id)
        if task and task.status == "pending":
            loop = AgentCognitiveLoop(db, agent_id, user_id)
            await loop.run(task)
            db.commit()
    except Exception as e:
        logger.error(f"Background task execution error for {task_id}: {e}")
    finally:
        try:
            db.close()
        except Exception:
            pass


def _match_event_pattern(event_type: str) -> Optional[str]:
    """Match an event type against TRIGGER_MAP patterns using fnmatch."""
    import fnmatch
    for pattern, archetype in TRIGGER_MAP.items():
        if fnmatch.fnmatch(event_type, pattern):
            return archetype
    return None


def _build_task_description(payload: TriggerPayload) -> str:
    """Build a human-readable task description from a trigger payload."""
    source = payload.source
    event = payload.event_type

    # Include key data fields in the description
    data_summary = ""
    if payload.data:
        # Take first 3 key-value pairs for summary
        items = list(payload.data.items())[:3]
        data_summary = ", ".join(f"{k}={v}" for k, v in items)
        if len(payload.data) > 3:
            data_summary += f" (+{len(payload.data) - 3} more fields)"

    parts = [f"[{source}] {event}"]
    if data_summary:
        parts.append(f"Data: {data_summary}")

    return " | ".join(parts)


# ── EventBus Registration ────────────────────────────────────────

def register_all_triggers(bus) -> None:
    """
    Subscribe to EventBus patterns that should trigger agent tasks.
    Call this during application startup (lifespan).
    """
    async def _on_trigger_event(event_type: str, data: dict):
        """Generic handler for trigger-mapped events."""
        payload = TriggerPayload(
            source=_infer_source(event_type),
            event_type=event_type,
            data=data,
            user_id=data.get("user_id"),
        )
        await route_trigger(payload)

    # Register for each pattern in TRIGGER_MAP
    registered = set()
    for pattern in TRIGGER_MAP:
        # Convert fnmatch patterns to EventBus patterns
        # EventBus already supports wildcard matching
        if pattern not in registered:
            bus.subscribe(pattern, _on_trigger_event)
            registered.add(pattern)
            logger.info(f"Trigger router subscribed to: {pattern}")


def _infer_source(event_type: str) -> str:
    """Infer the trigger source from the event type."""
    if event_type.startswith("chain."):
        return "chain"
    elif event_type.startswith("device."):
        return "webhook"
    elif event_type.startswith("messaging."):
        return "messenger"
    elif event_type.startswith("knowledge."):
        return "webhook"
    elif event_type.startswith("system."):
        return "heartbeat"
    elif event_type.startswith("agent."):
        return "cron"
    elif event_type.startswith("pipeline."):
        return "webhook"
    elif event_type.startswith("broker."):
        return "webhook"
    return "webhook"
