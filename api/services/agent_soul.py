"""
REFINET Cloud — Agent Soul Service
Parses SOUL.md format into structured identity data.
Builds agent system prompts using the 7-layer context injection stack:
  Layer 0: Root SOUL.md (always loaded)
  Layer 1: Per-agent SOUL (from DB)
  Layer 2: MEMORY.md + current memory state
  Layer 3: RAG context (knowledge base + contracts)
  Layer 4: Skills metadata (from skills/ directory)
  Layer 5: SAFETY.md (always loaded — hard constraints)
  Layer 6: Runtime context (datetime, model, tokens, tools)
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


# ── System Prompt Builder — 7-Layer Context Injection Stack ─────

def build_agent_system_prompt(
    db: Session,
    agent_id: Optional[str],
    user_query: str,
    user_id: Optional[str] = None,
    model: str = "bitnet-b1.58-2b",
    memory_context: Optional[str] = None,
) -> tuple[str, list[dict], dict]:
    """
    Build a full system prompt using the 7-layer context injection stack.

    When agent_id is None, builds the default GROOT chat prompt (root SOUL only).
    When agent_id is provided, includes the per-agent SOUL from DB.

    Returns (system_prompt, sources_list, token_report).
    """
    from api.services.context_loader import load_control_document, load_skills_metadata
    from api.services.token_budget import create_budget

    budget = create_budget(model)
    parts = []
    sources = []

    # ── Layer 0: Root SOUL.md (always loaded) ────────────────────
    root_soul = load_control_document("SOUL.md")
    if root_soul:
        root_soul = budget.allocate("soul", root_soul)
        parts.append(root_soul)

    # ── Layer 1: Per-Agent SOUL (from DB) ────────────────────────
    if agent_id:
        soul = get_soul(db, agent_id)
        agent_soul_parts = []
        if soul:
            if soul["persona"]:
                agent_soul_parts.append(f"## Your Identity\n{soul['persona']}")
            if soul["goals"]:
                goals_str = "\n".join(f"- {g}" for g in soul["goals"])
                agent_soul_parts.append(f"## Your Goals\n{goals_str}")
            if soul["constraints"]:
                constraints_str = "\n".join(f"- {c}" for c in soul["constraints"])
                agent_soul_parts.append(f"## Your Constraints\n{constraints_str}")
            if soul["tools_allowed"]:
                tools_str = ", ".join(soul["tools_allowed"])
                agent_soul_parts.append(f"## Available Tools\n{tools_str}")

        agent_soul_text = "\n\n".join(agent_soul_parts) if agent_soul_parts else ""
        if agent_soul_text:
            agent_soul_text = budget.allocate("agent_soul", agent_soul_text)
            parts.append(agent_soul_text)

        # Add operating protocol for agent mode
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
    else:
        budget.allocate("agent_soul", "")

    # ── Layer 2: Memory State ────────────────────────────────────
    if memory_context:
        memory_text = budget.allocate("memory", f"## Your Memories\n{memory_context}")
        if memory_text:
            parts.append(memory_text)
    else:
        budget.allocate("memory", "")

    # ── Layer 3: RAG Context ─────────────────────────────────────
    from api.services.rag import build_rag_context
    rag_context, rag_sources = build_rag_context(db, user_query, user_id=user_id)
    sources = list(rag_sources) if rag_sources else []

    if rag_context:
        rag_header = "Use the following reference information to inform your response. Cite it naturally — don't say \"according to the knowledge base.\""
        rag_full = f"## Reference Information\n{rag_header}\n\n{rag_context}"
        rag_text = budget.allocate("rag", rag_full)
        if rag_text:
            parts.append(rag_text)
    else:
        budget.allocate("rag", "")

    # ── Layer 3.5: CAG Context (Contract-Augmented Generation) ──
    # GROOT is the Wizard — it uses the contract registry as its logic repository.
    # Public SDK definitions are injected here so GROOT can reason about contracts.
    try:
        from api.services.contract_brain import get_sdk_context_for_groot
        cag_context = get_sdk_context_for_groot(db, user_query, max_results=3)
        if cag_context:
            cag_header = (
                "## Contract Knowledge (CAG)\n"
                "You are GROOT, the sole Wizard of REFINET Cloud. You have access to the contract registry below.\n"
                "Use this knowledge to answer questions about contracts, help users deploy, and suggest interactions.\n"
                "You can: query contracts (cag_query), read on-chain state (cag_execute), "
                "or request state-changing actions (cag_act — requires master_admin approval).\n\n"
            )
            cag_full = cag_header + cag_context
            cag_text = budget.allocate("cag", cag_full)
            if cag_text:
                parts.append(cag_text)
                sources.append({"type": "cag", "description": "Contract registry SDK definitions"})
        else:
            budget.allocate("cag", "")
    except Exception as e:
        budget.allocate("cag", "")
        logger.debug(f"CAG context skipped: {e}")

    # ── Layer 4: Skills Metadata ─────────────────────────────────
    skills_meta = load_skills_metadata()
    if skills_meta:
        skills_text = budget.allocate("skills", f"## {skills_meta}")
        if skills_text:
            parts.append(skills_text)
    else:
        budget.allocate("skills", "")

    # ── Layer 5: SAFETY.md (always loaded) ───────────────────────
    safety = load_control_document("SAFETY.md")
    if safety:
        safety_text = budget.allocate("safety", safety)
        if safety_text:
            parts.append(safety_text)

    # ── Layer 6: Runtime Context ─────────────────────────────────
    now = datetime.now(timezone.utc)
    runtime = (
        f"## Runtime\n"
        f"- Date: {now.strftime('%Y-%m-%d %H:%M UTC')}\n"
        f"- Model: {model}\n"
        f"- Context window: {budget.context_window} tokens\n"
        f"- Tokens remaining for response: {budget.remaining} tokens"
    )
    runtime_text = budget.allocate("runtime", runtime)
    if runtime_text:
        parts.append(runtime_text)

    # ── Assemble ─────────────────────────────────────────────────
    system_prompt = "\n\n".join(parts)
    token_report = budget.report()

    logger.debug(
        f"Context assembled: {token_report['allocated']}/{token_report['total_usable']} tokens "
        f"({len(parts)} layers)"
    )

    return system_prompt, sources, token_report


def get_allowed_tools(db: Session, agent_id: str) -> list[str]:
    """Get the list of tools this agent is allowed to use."""
    soul = db.query(AgentSoul).filter(AgentSoul.agent_id == agent_id).first()
    if not soul or not soul.tools_allowed:
        return []
    try:
        return json.loads(soul.tools_allowed)
    except (json.JSONDecodeError, TypeError):
        return []
