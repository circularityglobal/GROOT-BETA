"""
REFINET Cloud — Pipeline & Deployment Models
DAG orchestration for wizard workers, pending admin actions, and deployment tracking.
All tables in public.db (user-facing data).
"""

from sqlalchemy import (
    Column, String, Boolean, Integer, Float, DateTime, Text, ForeignKey
)
from sqlalchemy.sql import func
from api.database import PublicBase
import uuid


def new_uuid() -> str:
    return str(uuid.uuid4())


# ── Pipeline Execution ────────────────────────────────────────────

class PipelineRun(PublicBase):
    """Tracks a multi-step DAG execution (compile → test → deploy → transfer)."""
    __tablename__ = "pipeline_runs"

    id = Column(String, primary_key=True, default=new_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    agent_task_id = Column(String, ForeignKey("agent_tasks.id"), nullable=True)
    pipeline_type = Column(String, nullable=False)           # compile_test | deploy | full
    status = Column(String, default="pending", index=True)   # pending | running | paused | completed | failed | cancelled
    dag_json = Column(Text, nullable=True)                   # JSON adjacency list of steps
    current_step = Column(String, nullable=True)             # Name of currently executing step
    config_json = Column(Text, nullable=True)                # JSON: pipeline configuration (source, chain, etc.)
    result_json = Column(Text, nullable=True)                # JSON: final pipeline output
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


class PipelineStep(PublicBase):
    """Individual step within a pipeline run."""
    __tablename__ = "pipeline_steps"

    id = Column(String, primary_key=True, default=new_uuid)
    pipeline_id = Column(String, ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    step_name = Column(String, nullable=False)               # compile | test | rbac_check | deploy | verify | transfer_ownership
    step_index = Column(Integer, nullable=False)
    status = Column(String, default="pending")               # pending | running | completed | failed | skipped
    worker_type = Column(String, nullable=False)             # maps to wizard_workers function name
    input_json = Column(Text, nullable=True)                 # JSON: input data for worker
    output_json = Column(Text, nullable=True)                # JSON: worker result
    error_message = Column(Text, nullable=True)
    depends_on = Column(Text, nullable=True)                 # JSON array of step IDs this step waits for
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


# ── Pending Admin Actions ─────────────────────────────────────────

class PendingAction(PublicBase):
    """Admin approval gate for Tier 2 actions (deploy, transfer, withdrawal)."""
    __tablename__ = "pending_actions"

    id = Column(String, primary_key=True, default=new_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    action_type = Column(String, nullable=False)             # deploy | transfer_ownership | withdrawal
    target_chain = Column(String, nullable=True)             # ethereum | base | polygon | sepolia ...
    target_address = Column(String, nullable=True)           # contract or recipient address
    payload_json = Column(Text, nullable=True)               # JSON: action-specific data
    status = Column(String, default="pending", index=True)   # pending | approved | rejected | expired
    reviewer_id = Column(String, ForeignKey("users.id"), nullable=True)
    review_note = Column(Text, nullable=True)
    pipeline_step_id = Column(String, ForeignKey("pipeline_steps.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    reviewed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)


# ── Deployment Records ────────────────────────────────────────────

class DeploymentRecord(PublicBase):
    """Tracks every contract GROOT has deployed on-chain."""
    __tablename__ = "deployment_records"

    id = Column(String, primary_key=True, default=new_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    pipeline_run_id = Column(String, ForeignKey("pipeline_runs.id"), nullable=True)
    contract_address = Column(String, nullable=False, index=True)
    chain = Column(String, nullable=False)                   # ethereum | base | polygon | sepolia ...
    chain_id = Column(Integer, nullable=True)
    deployer_address = Column(String, nullable=True)         # GROOT's custodial wallet address
    owner_address = Column(String, nullable=True)            # Current owner (starts as deployer)
    tx_hash = Column(String, nullable=True)
    block_number = Column(Integer, nullable=True)
    constructor_args_json = Column(Text, nullable=True)      # JSON: constructor parameters
    abi_hash = Column(String, nullable=True)                 # Hash of deployed ABI for reference
    ownership_status = Column(String, default="groot_owned") # groot_owned | transferring | user_owned | unknown
    transfer_tx_hash = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    transferred_at = Column(DateTime, nullable=True)
