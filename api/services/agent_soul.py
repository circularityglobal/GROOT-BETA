"""
REFINET Cloud — Agent Soul Service
Parses SOUL.md format into structured identity data.
Builds agent system prompts by combining SOUL with RAG context.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from api.models.agent_engine import AgentSoul

logger = logging.getLogger("refinet.agent.soul")


# ── SOUL.md Parser ────────────────────────────────────────────────

def parse_soul_md(soul_md: str) -> dict:
    """
    Parse a SOUL.md markdown document into structured fields.

    Expected format:
        # Identity
        <persona description>

        # Goals
        - goal 1
        - goal 2

        # Constraints
        - constraint 1
        - constraint 2

        # Tools
        - tool_name_1
        - tool_name_2

        # Delegation
        auto | approve | none
    """
    result = {
        "persona": None,
        "goals": [],
        "constraints": [],
        "tools_allowed": [],
        "delegation_policy": "none",
    }

    # Split into sections by heading
    sections = re.split(r'^#\s+', soul_md, flags=re.MULTILINE)

    for section in sections:
        if not section.strip():
            continue

        lines = section.strip().split('\n')
        heading = lines[0].strip().lower()
        body = '\n'.join(lines[1:]).strip()

        if heading in ('identity', 'persona', 'who'):
            result["persona"] = body

        elif heading in ('goals', 'objectives', 'mission'):
            result["goals"] = _extract_list_items(body)

        elif heading in ('constraints', 'rules', 'boundaries', 'safety'):
            result["constraints"] = _extract_list_items(body)

        elif heading in ('tools', 'capabilities', 'allowed tools'):
            result["tools_allowed"] = _extract_list_items(body)

        elif heading in ('delegation', 'delegation policy'):
            policy = body.strip().lower()
            if policy in ('auto', 'approve', 'none'):
                result["delegation_policy"] = policy

    return result


def _extract_list_items(text: str) -> list[str]:
    """Extract bullet points or numbered list items from text."""
    items = []
    for line in text.split('\n'):
        line = line.strip()
        # Match: - item, * item, 1. item, 1) item
        match = re.match(r'^[-*•]\s+(.+)$|^\d+[.)]\s+(.+)$', line)
        if match:
            item = match.group(1) or match.group(2)
            items.append(item.strip())
        elif line and not items:
            # First line might be a single-line value
            items.append(line)
    return items


# ── CRUD ──────────────────────────────────────────────────────────

def create_soul(db: Session, agent_id: str, soul_md: str) -> AgentSoul:
    """Create or update an agent's SOUL from markdown."""
    parsed = parse_soul_md(soul_md)

    existing = db.query(AgentSoul).filter(AgentSoul.agent_id == agent_id).first()

    if existing:
        existing.soul_md = soul_md
        existing.persona = parsed["persona"]
        existing.goals = json.dumps(parsed["goals"])
        existing.constraints = json.dumps(parsed["constraints"])
        existing.tools_allowed = json.dumps(parsed["tools_allowed"])
        existing.delegation_policy = parsed["delegation_policy"]
        existing.updated_at = datetime.now(timezone.utc)
        db.flush()
        return existing

    soul = AgentSoul(
        agent_id=agent_id,
        soul_md=soul_md,
        persona=parsed["persona"],
        goals=json.dumps(parsed["goals"]),
        constraints=json.dumps(parsed["constraints"]),
        tools_allowed=json.dumps(parsed["tools_allowed"]),
        delegation_policy=parsed["delegation_policy"],
    )
    db.add(soul)
    db.flush()
    return soul


def get_soul(db: Session, agent_id: str) -> Optional[dict]:
    """Get an agent's soul as a structured dict."""
    soul = db.query(AgentSoul).filter(AgentSoul.agent_id == agent_id).first()
    if not soul:
        return None

    return {
        "id": soul.id,
        "agent_id": soul.agent_id,
        "soul_md": soul.soul_md,
        "persona": soul.persona,
        "goals": json.loads(soul.goals) if soul.goals else [],
        "constraints": json.loads(soul.constraints) if soul.constraints else [],
        "tools_allowed": json.loads(soul.tools_allowed) if soul.tools_allowed else [],
        "delegation_policy": soul.delegation_policy,
        "created_at": soul.created_at.isoformat() if soul.created_at else None,
        "updated_at": soul.updated_at.isoformat() if soul.updated_at else None,
    }


def delete_soul(db: Session, agent_id: str) -> bool:
    """Delete an agent's soul."""
    soul = db.query(AgentSoul).filter(AgentSoul.agent_id == agent_id).first()
    if not soul:
        return False
    db.delete(soul)
    db.flush()
    return True


# ── System Prompt Builder ────────────────────────────────────────

def build_agent_system_prompt(
    db: Session,
    agent_id: str,
    user_query: str,
    user_id: Optional[str] = None,
) -> tuple[str, list[dict]]:
    """
    Build a full system prompt for an agent by combining:
    1. SOUL identity (persona, goals, constraints)
    2. RAG context from knowledge base (scoped to user's visible docs)

    Returns (system_prompt, sources_list).
    """
    soul = get_soul(db, agent_id)

    # Build SOUL section
    soul_parts = []
    if soul:
        if soul["persona"]:
            soul_parts.append(f"## Your Identity\n{soul['persona']}")
        if soul["goals"]:
            goals_str = "\n".join(f"- {g}" for g in soul["goals"])
            soul_parts.append(f"## Your Goals\n{goals_str}")
        if soul["constraints"]:
            constraints_str = "\n".join(f"- {c}" for c in soul["constraints"])
            soul_parts.append(f"## Your Constraints\n{constraints_str}")
        if soul["tools_allowed"]:
            tools_str = ", ".join(soul["tools_allowed"])
            soul_parts.append(f"## Available Tools\n{tools_str}")

    soul_section = "\n\n".join(soul_parts) if soul_parts else ""

    # Get RAG context
    from api.services.rag import build_rag_context
    rag_context, sources = build_rag_context(db, user_query, user_id=user_id)

    # Assemble
    parts = ["You are an autonomous AI agent running on REFINET Cloud."]
    if soul_section:
        parts.append(soul_section)

    parts.append("""## Operating Protocol
You execute tasks through a structured cognitive loop:
1. PERCEIVE — Understand the task and recall relevant memories
2. PLAN — Create a structured step-by-step plan
3. ACT — Execute each step using available tools
4. OBSERVE — Check results against expectations
5. REFLECT — Evaluate what worked and what didn't
6. STORE — Save lessons learned to memory

When creating a plan, output valid JSON with this structure:
{"steps": [{"action": "tool_name or reason", "args": {}, "expected": "description"}]}

When reflecting, be honest about outcomes: "success", "partial", or "failure".""")

    if rag_context:
        parts.append(f"\n## Reference Information\n{rag_context}")

    return "\n\n".join(parts), sources


def get_allowed_tools(db: Session, agent_id: str) -> list[str]:
    """Get the list of tools this agent is allowed to use."""
    soul = db.query(AgentSoul).filter(AgentSoul.agent_id == agent_id).first()
    if not soul or not soul.tools_allowed:
        return []
    try:
        return json.loads(soul.tools_allowed)
    except (json.JSONDecodeError, TypeError):
        return []
