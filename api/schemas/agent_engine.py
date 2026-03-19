"""
REFINET Cloud — Agent Engine Schemas
Pydantic request/response models for agent SOUL, tasks, and memory.
"""

from pydantic import BaseModel, Field
from typing import Optional


class SoulCreateRequest(BaseModel):
    soul_md: str = Field(..., description="SOUL.md markdown content defining agent identity")


class SoulResponse(BaseModel):
    id: str
    agent_id: str
    persona: Optional[str] = None
    goals: list[str] = []
    constraints: list[str] = []
    tools_allowed: list[str] = []
    delegation_policy: str = "none"
    soul_md: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class TaskSubmitRequest(BaseModel):
    description: str = Field(..., description="What the agent should do")


class TaskResponse(BaseModel):
    id: str
    agent_id: str
    description: str
    status: str
    current_phase: Optional[str] = None
    tokens_used: int = 0
    inference_calls: int = 0
    tool_calls: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: Optional[str] = None


class TaskDetailResponse(BaseModel):
    id: str
    agent_id: str
    description: str
    status: str
    current_phase: Optional[str] = None
    plan: Optional[dict] = None
    steps: Optional[list[dict]] = None
    result: Optional[dict] = None
    error_message: Optional[str] = None
    tokens_used: int = 0
    inference_calls: int = 0
    tool_calls: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: Optional[str] = None


class DelegationRequest(BaseModel):
    target_agent_id: str = Field(..., description="Agent to delegate to")
    subtask_description: str = Field(..., description="What the target agent should do")
