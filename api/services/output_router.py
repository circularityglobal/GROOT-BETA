"""
REFINET Cloud — Output Router
Routes completed task results to configured output targets.

Output targets:
  - json_store: Persist to task result (default, always done)
  - response:   Return to API caller (default, always done)
  - memory:     Write to episodic/semantic memory (default via STORE phase)
  - agent:      Chain result as new task to another agent
  - webhook:    Publish to EventBus for webhook delivery
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger("refinet.output_router")


class OutputTarget(str, Enum):
    """Where to route completed task results."""
    JSON_STORE = "json_store"   # Already done: task.result_json
    RESPONSE = "response"       # Already done: HTTP response
    MEMORY = "memory"           # Already done: STORE phase
    AGENT = "agent"             # Chain to another agent
    WEBHOOK = "webhook"         # Publish to EventBus → webhook delivery


# Default targets that are always active (handled by existing code)
DEFAULT_TARGETS = {OutputTarget.JSON_STORE, OutputTarget.RESPONSE, OutputTarget.MEMORY}


async def route_output(
    db: Session,
    task_id: str,
    agent_id: str,
    user_id: str,
    result: dict,
    targets: Optional[list[dict]] = None,
) -> dict:
    """
    Route completed task results to configured output targets.

    Args:
        db: Database session
        task_id: Completed task ID
        agent_id: Source agent ID
        user_id: Task owner
        result: Task result dict with 'output' and 'success' keys
        targets: List of output target configs, e.g.:
            [{"type": "agent", "target_agent_id": "agent_xyz", "description": "..."}]
            [{"type": "webhook", "event": "custom.event.name"}]

    Returns:
        Summary dict of routing results.
    """
    if not targets:
        return {"routed": [], "skipped": "no additional targets configured"}

    routing_results = []

    for target_config in targets:
        target_type = target_config.get("type", "")

        try:
            if target_type == OutputTarget.AGENT:
                # Chain to another agent
                chain_result = await _route_to_agent(
                    db=db,
                    source_agent_id=agent_id,
                    source_task_id=task_id,
                    user_id=user_id,
                    result=result,
                    config=target_config,
                )
                routing_results.append({
                    "target": "agent",
                    "success": chain_result is not None,
                    "task_id": chain_result,
                })

            elif target_type == OutputTarget.WEBHOOK:
                # Publish custom event to EventBus
                await _route_to_webhook(
                    agent_id=agent_id,
                    task_id=task_id,
                    result=result,
                    config=target_config,
                )
                routing_results.append({
                    "target": "webhook",
                    "success": True,
                    "event": target_config.get("event", "agent.output.routed"),
                })

            elif target_type in (OutputTarget.JSON_STORE, OutputTarget.RESPONSE, OutputTarget.MEMORY):
                # These are handled by existing code — skip silently
                routing_results.append({
                    "target": target_type,
                    "success": True,
                    "note": "handled by default pipeline",
                })

            else:
                logger.warning(f"Unknown output target type: {target_type}")
                routing_results.append({
                    "target": target_type,
                    "success": False,
                    "error": f"Unknown target type: {target_type}",
                })

        except Exception as e:
            logger.error(f"Output routing error for target {target_type}: {e}")
            routing_results.append({
                "target": target_type,
                "success": False,
                "error": str(e),
            })

    return {"routed": routing_results}


async def _route_to_agent(
    db: Session,
    source_agent_id: str,
    source_task_id: str,
    user_id: str,
    result: dict,
    config: dict,
) -> Optional[str]:
    """
    Chain task result to another agent by creating a delegation.
    Returns the delegated task ID, or None on failure.
    """
    from api.services.agent_engine import delegate_task

    target_agent_id = config.get("target_agent_id")
    if not target_agent_id:
        logger.error("Agent output target missing 'target_agent_id'")
        return None

    description = config.get("description", "")
    if not description:
        # Auto-generate description from result
        output = result.get("output", "")
        description = f"Process output from task {source_task_id}: {output[:200]}"

    delegation = await delegate_task(
        db=db,
        source_agent_id=source_agent_id,
        target_agent_id=target_agent_id,
        source_task_id=source_task_id,
        subtask_description=description,
        user_id=user_id,
    )

    if delegation:
        logger.info(
            f"Output chained: {source_agent_id} → {target_agent_id} "
            f"(delegation={delegation.id})"
        )
        return delegation.delegated_task_id

    return None


async def _route_to_webhook(
    agent_id: str,
    task_id: str,
    result: dict,
    config: dict,
) -> None:
    """Publish task result as a custom event to EventBus."""
    from api.services.event_bus import EventBus

    event_name = config.get("event", "agent.output.routed")
    payload = {
        "agent_id": agent_id,
        "task_id": task_id,
        "success": result.get("success", False),
        "output": result.get("output", ""),
    }

    await EventBus.get().publish(event_name, payload)
    logger.debug(f"Output published to EventBus: {event_name}")


def get_output_targets(db: Session, agent_id: str) -> list[dict]:
    """
    Get configured output targets for an agent.
    Reads from the agent registration's config JSON.
    """
    from api.models.public import AgentRegistration

    agent = db.query(AgentRegistration).filter(
        AgentRegistration.id == agent_id,
    ).first()

    if not agent or not agent.config:
        return []

    try:
        config = json.loads(agent.config) if isinstance(agent.config, str) else agent.config
        return config.get("output_targets", [])
    except (json.JSONDecodeError, TypeError, AttributeError):
        return []
