"""
REFINET Cloud — Agent Engine Models
Cognitive architecture: SOUL identity, 4-tier memory, task tracking, delegation.
All tables in public.db (user-facing, per-agent data).
"""

from sqlalchemy import (
    Column, String, Boolean, Integer, Float, DateTime, Text, ForeignKey
)
from sqlalchemy.sql import func
from api.database import PublicBase
import uuid


def new_uuid() -> str:
    return str(uuid.uuid4())


# ── SOUL: Agent Identity ──────────────────────────────────────────

class AgentSoul(PublicBase):
    """Persistent agent identity — personality, goals, constraints, tool permissions."""
    __tablename__ = "agent_souls"

    id = Column(String, primary_key=True, default=new_uuid)
    agent_id = Column(String, ForeignKey("agent_registrations.id", ondelete="CASCADE"),
                      unique=True, nullable=False, index=True)
    # SOUL.md content (raw markdown)
    soul_md = Column(Text, nullable=False)
    # Parsed fields for fast access
    persona = Column(String, nullable=True)              # personality archetype
    goals = Column(Text, nullable=True)                  # JSON array of goal strings
    constraints = Column(Text, nullable=True)            # JSON array of constraint strings
    tools_allowed = Column(Text, nullable=True)          # JSON array of tool names/patterns
    delegation_policy = Column(String, default="none")   # none | approve | auto
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())


# ── Memory Tier 1: Working Memory (short-lived, per-task) ────────

class AgentMemoryWorking(PublicBase):
    """Short-lived per-task context with TTL. Auto-cleaned after task completion."""
    __tablename__ = "agent_memory_working"

    id = Column(String, primary_key=True, default=new_uuid)
    agent_id = Column(String, ForeignKey("agent_registrations.id", ondelete="CASCADE"),
                      nullable=False, index=True)
    task_id = Column(String, nullable=False, index=True)
    key = Column(String, nullable=False)
    value = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)


# ── Memory Tier 2: Episodic Memory (timestamped events) ──────────

class AgentMemoryEpisodic(PublicBase):
    """Timestamped event records with outcomes — used for learning from past actions."""
    __tablename__ = "agent_memory_episodic"

    id = Column(String, primary_key=True, default=new_uuid)
    agent_id = Column(String, ForeignKey("agent_registrations.id", ondelete="CASCADE"),
                      nullable=False, index=True)
    event_type = Column(String, nullable=False)          # task_completed | tool_called | error | reflection
    summary = Column(Text, nullable=False)               # Human-readable description
    context_json = Column(Text, nullable=True)           # JSON: task details, input, etc.
    outcome = Column(String, nullable=False)             # success | failure | partial
    tokens_used = Column(Integer, default=0)
    timestamp = Column(DateTime, server_default=func.now())


# ── Memory Tier 3: Semantic Memory (learned facts) ────────────────

class AgentMemorySemantic(PublicBase):
    """Learned facts with confidence scores and embeddings for similarity search."""
    __tablename__ = "agent_memory_semantic"

    id = Column(String, primary_key=True, default=new_uuid)
    agent_id = Column(String, ForeignKey("agent_registrations.id", ondelete="CASCADE"),
                      nullable=False, index=True)
    fact = Column(Text, nullable=False)                  # The learned fact
    confidence = Column(Float, default=0.5)              # 0.0–1.0 confidence score
    source = Column(String, nullable=True)               # Where this was learned
    embedding = Column(Text, nullable=True)              # JSON-serialized 384-dim float array
    usage_count = Column(Integer, default=0)             # How many times this fact was recalled
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())


# ── Memory Tier 4: Procedural Memory (strategy patterns) ────────

class AgentMemoryProcedural(PublicBase):
    """Learned strategy patterns with success rates."""
    __tablename__ = "agent_memory_procedural"

    id = Column(String, primary_key=True, default=new_uuid)
    agent_id = Column(String, ForeignKey("agent_registrations.id", ondelete="CASCADE"),
                      nullable=False, index=True)
    pattern_name = Column(String, nullable=False)
    trigger_condition = Column(Text, nullable=False)     # When to apply this pattern
    action_sequence = Column(Text, nullable=False)       # JSON array of action steps
    success_rate = Column(Float, default=0.0)            # 0.0–1.0
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


# ── Task Tracking ────────────────────────────────────────────────

class AgentTask(PublicBase):
    """Tracks agent task execution through the cognitive loop."""
    __tablename__ = "agent_tasks"

    id = Column(String, primary_key=True, default=new_uuid)
    agent_id = Column(String, ForeignKey("agent_registrations.id", ondelete="CASCADE"),
                      nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    description = Column(Text, nullable=False)           # What the agent was asked to do
    status = Column(String, default="pending", index=True)  # pending | running | completed | failed | cancelled
    # Cognitive loop state
    current_phase = Column(String, nullable=True)        # perceive | plan | act | observe | reflect | store
    plan_json = Column(Text, nullable=True)              # JSON: structured plan from PLAN phase
    steps_json = Column(Text, nullable=True)             # JSON array: execution trace
    result_json = Column(Text, nullable=True)            # JSON: final output
    error_message = Column(Text, nullable=True)
    # Token accounting
    tokens_used = Column(Integer, default=0)
    inference_calls = Column(Integer, default=0)
    tool_calls = Column(Integer, default=0)
    # Timing
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


# ── Agent-to-Agent Delegation ────────────────────────────────────

class AgentDelegation(PublicBase):
    """Tracks delegation chains between agents."""
    __tablename__ = "agent_delegations"

    id = Column(String, primary_key=True, default=new_uuid)
    source_agent_id = Column(String, ForeignKey("agent_registrations.id"), nullable=False, index=True)
    target_agent_id = Column(String, ForeignKey("agent_registrations.id"), nullable=False, index=True)
    source_task_id = Column(String, ForeignKey("agent_tasks.id"), nullable=False)
    delegated_task_id = Column(String, ForeignKey("agent_tasks.id"), nullable=True)  # Set when target creates its task
    subtask_description = Column(Text, nullable=False)
    status = Column(String, default="requested")         # requested | accepted | completed | rejected | failed
    result_json = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    resolved_at = Column(DateTime, nullable=True)
