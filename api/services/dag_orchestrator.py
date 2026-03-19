"""
REFINET Cloud — DAG Pipeline Orchestrator
Coordinates multi-step wizard worker pipelines with dependency tracking
and admin approval gates.

Pipeline Templates:
  compile_test:  [compile] → [test]
  deploy:        [compile] → [test] → [rbac_check] → [deploy] → [verify]
  full:          [compile] → [test] → [rbac_check] → [deploy] → [verify] → [transfer_ownership]
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from api.models.pipeline import PipelineRun, PipelineStep, PendingAction, DeploymentRecord
from api.services.event_bus import EventBus

logger = logging.getLogger("refinet.dag_orchestrator")


# ── Pipeline Step Templates ───────────────────────────────────────

PIPELINE_TEMPLATES = {
    "compile_test": [
        {"step_name": "compile", "worker_type": "compile_worker"},
        {"step_name": "test", "worker_type": "test_worker"},
    ],
    "deploy": [
        {"step_name": "compile", "worker_type": "compile_worker"},
        {"step_name": "test", "worker_type": "test_worker"},
        {"step_name": "rbac_check", "worker_type": "rbac_check_worker"},
        {"step_name": "deploy", "worker_type": "deploy_worker"},
        {"step_name": "verify", "worker_type": "verify_worker"},
    ],
    "full": [
        {"step_name": "compile", "worker_type": "compile_worker"},
        {"step_name": "test", "worker_type": "test_worker"},
        {"step_name": "rbac_check", "worker_type": "rbac_check_worker"},
        {"step_name": "deploy", "worker_type": "deploy_worker"},
        {"step_name": "verify", "worker_type": "verify_worker"},
        {"step_name": "transfer_ownership", "worker_type": "transfer_ownership_worker"},
    ],
}

# Map worker_type names to actual functions
WORKER_DISPATCH = {
    "compile_worker": "api.services.wizard_workers:compile_worker",
    "test_worker": "api.services.wizard_workers:test_worker",
    "rbac_check_worker": "api.services.wizard_workers:rbac_check_worker",
    "deploy_worker": "api.services.wizard_workers:deploy_worker",
    "verify_worker": "api.services.wizard_workers:verify_worker",
    "transfer_ownership_worker": "api.services.wizard_workers:transfer_ownership_worker",
}


def _import_worker(worker_type: str):
    """Dynamically import a worker function from its dotted path."""
    path = WORKER_DISPATCH.get(worker_type)
    if not path:
        raise ValueError(f"Unknown worker_type: {worker_type}")
    module_path, func_name = path.rsplit(":", 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, func_name)


# ── Pipeline Creation ─────────────────────────────────────────────

def create_pipeline(
    db: Session,
    user_id: str,
    pipeline_type: str,
    config: dict,
    agent_task_id: Optional[str] = None,
) -> PipelineRun:
    """
    Create a new pipeline run with steps based on the template.

    Parameters
    ----------
    db : Session
    user_id : str
    pipeline_type : str — one of: compile_test, deploy, full
    config : dict — pipeline configuration (source_code, chain, abi, etc.)
    agent_task_id : str — optional, links pipeline to an agent task

    Returns
    -------
    PipelineRun with steps created
    """
    template = PIPELINE_TEMPLATES.get(pipeline_type)
    if not template:
        raise ValueError(f"Unknown pipeline_type: {pipeline_type}. Valid: {list(PIPELINE_TEMPLATES.keys())}")

    pipeline_id = str(uuid.uuid4())
    pipeline = PipelineRun(
        id=pipeline_id,
        user_id=user_id,
        agent_task_id=agent_task_id,
        pipeline_type=pipeline_type,
        status="pending",
        config_json=json.dumps(config),
    )
    db.add(pipeline)

    # Create steps with linear dependencies (each step depends on the previous)
    step_ids = []
    dag = {}
    for i, step_def in enumerate(template):
        step_id = str(uuid.uuid4())
        depends_on = [step_ids[-1]] if step_ids else []

        step = PipelineStep(
            id=step_id,
            pipeline_id=pipeline_id,
            step_name=step_def["step_name"],
            step_index=i,
            status="pending",
            worker_type=step_def["worker_type"],
            depends_on=json.dumps(depends_on) if depends_on else None,
        )
        db.add(step)
        step_ids.append(step_id)
        dag[step_id] = {"name": step_def["step_name"], "depends_on": depends_on}

    pipeline.dag_json = json.dumps(dag)
    db.flush()

    logger.info("Pipeline created: id=%s type=%s steps=%d user=%s",
                pipeline_id, pipeline_type, len(template), user_id)
    return pipeline


# ── Pipeline Execution ────────────────────────────────────────────

async def run_pipeline(db: Session, pipeline_id: str) -> PipelineRun:
    """
    Execute a pipeline by walking the DAG and dispatching each step.
    Pauses if a step requires admin approval (PendingAction).

    Returns the updated PipelineRun.
    """
    pipeline = db.query(PipelineRun).filter(PipelineRun.id == pipeline_id).first()
    if not pipeline:
        raise ValueError(f"Pipeline not found: {pipeline_id}")

    if pipeline.status not in ("pending", "paused"):
        raise ValueError(f"Pipeline {pipeline_id} is {pipeline.status}, cannot run")

    pipeline.status = "running"
    pipeline.started_at = pipeline.started_at or datetime.now(timezone.utc)
    db.flush()

    config = json.loads(pipeline.config_json or "{}")
    bus = EventBus.get()

    # Get steps ordered by step_index
    steps = (
        db.query(PipelineStep)
        .filter(PipelineStep.pipeline_id == pipeline_id)
        .order_by(PipelineStep.step_index)
        .all()
    )

    accumulated_output = {}  # Carry forward output from previous steps

    for step in steps:
        # Skip already completed steps (for resumed pipelines)
        if step.status == "completed":
            if step.output_json:
                accumulated_output.update(json.loads(step.output_json))
            continue
        if step.status == "skipped":
            continue

        # Check dependencies
        if step.depends_on:
            dep_ids = json.loads(step.depends_on)
            for dep_id in dep_ids:
                dep_step = db.query(PipelineStep).filter(PipelineStep.id == dep_id).first()
                if not dep_step:
                    step.status = "failed"
                    step.error_message = f"Dependency step {dep_id} not found"
                    pipeline.status = "failed"
                    pipeline.error_message = step.error_message
                    db.flush()
                    return pipeline
                if dep_step.status != "completed":
                    step.status = "failed"
                    step.error_message = f"Dependency '{dep_step.step_name}' not completed (status: {dep_step.status})"
                    pipeline.status = "failed"
                    pipeline.error_message = step.error_message
                    db.flush()
                    return pipeline

        # Execute the step
        step.status = "running"
        step.started_at = datetime.now(timezone.utc)
        pipeline.current_step = step.step_name
        db.flush()

        try:
            # Build input for worker
            worker_input = _build_worker_input(step, config, accumulated_output, pipeline)

            # Dispatch to worker
            worker_fn = _import_worker(step.worker_type)

            # rbac_check_worker needs db session
            if step.worker_type == "rbac_check_worker":
                result = worker_fn(worker_input, db=db)
            else:
                result = worker_fn(worker_input)

            step.output_json = json.dumps(result)

            # Check for approval gate (rbac_check returns pending_action_id)
            if result.get("pending_action_id") and not result.get("approved"):
                step.status = "pending"  # Waiting for admin approval
                pipeline.status = "paused"
                pipeline.current_step = step.step_name
                db.flush()

                await bus.publish("pipeline.approval.needed", {
                    "pipeline_id": pipeline_id,
                    "step_id": step.id,
                    "step_name": step.step_name,
                    "pending_action_id": result["pending_action_id"],
                    "user_id": pipeline.user_id,
                    "reason": result.get("reason", "Admin approval required"),
                })
                return pipeline

            # Check for failure — worker returned explicit error
            worker_failed = result.get("success") is False or result.get("approved") is False
            if worker_failed and result.get("error"):
                step.status = "failed"
                step.error_message = result["error"]
                step.completed_at = datetime.now(timezone.utc)
                pipeline.status = "failed"
                pipeline.error_message = f"Step '{step.step_name}' failed: {result['error']}"
                pipeline.completed_at = datetime.now(timezone.utc)
                db.flush()

                await bus.publish("pipeline.run.failed", {
                    "pipeline_id": pipeline_id,
                    "step_name": step.step_name,
                    "error": result["error"],
                    "user_id": pipeline.user_id,
                })
                return pipeline

            # Step completed
            step.status = "completed"
            step.completed_at = datetime.now(timezone.utc)
            accumulated_output.update(result)
            db.flush()

            await bus.publish("pipeline.step.completed", {
                "pipeline_id": pipeline_id,
                "step_id": step.id,
                "step_name": step.step_name,
                "user_id": pipeline.user_id,
            })

            # Record deployment if deploy step succeeded
            if step.step_name == "deploy" and result.get("success") and result.get("contract_address"):
                _record_deployment(db, pipeline, result, config)

            # Update deployment record if transfer completed
            if step.step_name == "transfer_ownership" and result.get("success"):
                _update_deployment_ownership(db, pipeline, result)

        except Exception as e:
            step.status = "failed"
            step.error_message = str(e)
            step.completed_at = datetime.now(timezone.utc)
            pipeline.status = "failed"
            pipeline.error_message = f"Step '{step.step_name}' exception: {e}"
            pipeline.completed_at = datetime.now(timezone.utc)
            db.flush()
            logger.exception("Pipeline step failed: pipeline=%s step=%s", pipeline_id, step.step_name)

            await bus.publish("pipeline.run.failed", {
                "pipeline_id": pipeline_id,
                "step_name": step.step_name,
                "error": str(e),
                "user_id": pipeline.user_id,
            })
            return pipeline

    # All steps completed
    pipeline.status = "completed"
    pipeline.current_step = None
    pipeline.result_json = json.dumps(accumulated_output)
    pipeline.completed_at = datetime.now(timezone.utc)
    db.flush()

    await bus.publish("pipeline.run.completed", {
        "pipeline_id": pipeline_id,
        "pipeline_type": pipeline.pipeline_type,
        "user_id": pipeline.user_id,
        "result": accumulated_output,
    })

    logger.info("Pipeline completed: id=%s type=%s", pipeline_id, pipeline.pipeline_type)
    return pipeline


# ── Pipeline Resume (after admin approval) ────────────────────────

async def resume_pipeline(db: Session, pipeline_id: str) -> PipelineRun:
    """
    Resume a paused pipeline after a PendingAction has been approved.
    Marks the paused rbac_check step as completed and continues.
    """
    pipeline = db.query(PipelineRun).filter(PipelineRun.id == pipeline_id).first()
    if not pipeline:
        raise ValueError(f"Pipeline not found: {pipeline_id}")
    if pipeline.status != "paused":
        raise ValueError(f"Pipeline {pipeline_id} is {pipeline.status}, not paused")

    # Find the pending step and mark it completed
    pending_step = (
        db.query(PipelineStep)
        .filter(
            PipelineStep.pipeline_id == pipeline_id,
            PipelineStep.status == "pending",
        )
        .first()
    )
    if pending_step:
        pending_step.status = "completed"
        pending_step.completed_at = datetime.now(timezone.utc)
        pending_step.output_json = json.dumps({"approved": True, "reason": "Admin approved"})
        db.flush()

    pipeline.status = "paused"  # run_pipeline will set to running
    db.flush()

    return await run_pipeline(db, pipeline_id)


# ── Admin Approval ────────────────────────────────────────────────

async def approve_action(db: Session, action_id: str, reviewer_id: str, note: Optional[str] = None) -> dict:
    """Approve a pending action and resume its pipeline if linked."""
    action = db.query(PendingAction).filter(PendingAction.id == action_id).first()
    if not action:
        return {"error": "Action not found"}
    if action.status != "pending":
        return {"error": f"Action is already {action.status}"}

    action.status = "approved"
    action.reviewer_id = reviewer_id
    action.review_note = note
    action.reviewed_at = datetime.now(timezone.utc)
    db.flush()

    # Resume linked pipeline
    result = {"action_id": action_id, "status": "approved"}
    if action.pipeline_step_id:
        step = db.query(PipelineStep).filter(PipelineStep.id == action.pipeline_step_id).first()
        if step:
            pipeline = db.query(PipelineRun).filter(PipelineRun.id == step.pipeline_id).first()
            if pipeline and pipeline.status == "paused":
                await resume_pipeline(db, pipeline.id)
                result["pipeline_resumed"] = True
                result["pipeline_id"] = pipeline.id

    await EventBus.get().publish("pipeline.action.approved", {
        "action_id": action_id,
        "user_id": action.user_id,
        "reviewer_id": reviewer_id,
    })

    return result


async def reject_action(db: Session, action_id: str, reviewer_id: str, note: Optional[str] = None) -> dict:
    """Reject a pending action and fail its pipeline if linked."""
    action = db.query(PendingAction).filter(PendingAction.id == action_id).first()
    if not action:
        return {"error": "Action not found"}
    if action.status != "pending":
        return {"error": f"Action is already {action.status}"}

    action.status = "rejected"
    action.reviewer_id = reviewer_id
    action.review_note = note
    action.reviewed_at = datetime.now(timezone.utc)
    db.flush()

    # Fail linked pipeline
    if action.pipeline_step_id:
        step = db.query(PipelineStep).filter(PipelineStep.id == action.pipeline_step_id).first()
        if step:
            step.status = "failed"
            step.error_message = f"Rejected by admin: {note or 'No reason given'}"
            step.completed_at = datetime.now(timezone.utc)
            pipeline = db.query(PipelineRun).filter(PipelineRun.id == step.pipeline_id).first()
            if pipeline:
                pipeline.status = "failed"
                pipeline.error_message = f"Action rejected: {note or 'No reason given'}"
                pipeline.completed_at = datetime.now(timezone.utc)
            db.flush()

    await EventBus.get().publish("pipeline.action.rejected", {
        "action_id": action_id,
        "user_id": action.user_id,
        "reviewer_id": reviewer_id,
    })

    return {"action_id": action_id, "status": "rejected"}


# ── Pipeline Queries ──────────────────────────────────────────────

def get_pipeline(db: Session, pipeline_id: str, user_id: Optional[str] = None) -> Optional[dict]:
    """Get pipeline with all steps."""
    query = db.query(PipelineRun).filter(PipelineRun.id == pipeline_id)
    if user_id:
        query = query.filter(PipelineRun.user_id == user_id)
    pipeline = query.first()
    if not pipeline:
        return None

    steps = (
        db.query(PipelineStep)
        .filter(PipelineStep.pipeline_id == pipeline_id)
        .order_by(PipelineStep.step_index)
        .all()
    )

    return {
        "id": pipeline.id,
        "user_id": pipeline.user_id,
        "pipeline_type": pipeline.pipeline_type,
        "status": pipeline.status,
        "current_step": pipeline.current_step,
        "config": json.loads(pipeline.config_json) if pipeline.config_json else {},
        "result": json.loads(pipeline.result_json) if pipeline.result_json else None,
        "error": pipeline.error_message,
        "created_at": pipeline.created_at.isoformat() if pipeline.created_at else None,
        "started_at": pipeline.started_at.isoformat() if pipeline.started_at else None,
        "completed_at": pipeline.completed_at.isoformat() if pipeline.completed_at else None,
        "steps": [
            {
                "id": s.id,
                "step_name": s.step_name,
                "step_index": s.step_index,
                "status": s.status,
                "worker_type": s.worker_type,
                "output": json.loads(s.output_json) if s.output_json else None,
                "error": s.error_message,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            }
            for s in steps
        ],
    }


def list_pipelines(db: Session, user_id: str, limit: int = 20, offset: int = 0) -> list[dict]:
    """List user's pipelines."""
    pipelines = (
        db.query(PipelineRun)
        .filter(PipelineRun.user_id == user_id)
        .order_by(PipelineRun.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": p.id,
            "pipeline_type": p.pipeline_type,
            "status": p.status,
            "current_step": p.current_step,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "completed_at": p.completed_at.isoformat() if p.completed_at else None,
        }
        for p in pipelines
    ]


def list_pending_actions(db: Session, status: str = "pending", limit: int = 50) -> list[dict]:
    """List pending actions for admin review."""
    actions = (
        db.query(PendingAction)
        .filter(PendingAction.status == status)
        .order_by(PendingAction.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": a.id,
            "user_id": a.user_id,
            "action_type": a.action_type,
            "target_chain": a.target_chain,
            "target_address": a.target_address,
            "payload": json.loads(a.payload_json) if a.payload_json else {},
            "status": a.status,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "expires_at": a.expires_at.isoformat() if a.expires_at else None,
        }
        for a in actions
    ]


def cancel_pipeline(db: Session, pipeline_id: str, user_id: str) -> dict:
    """Cancel a running or pending pipeline."""
    pipeline = db.query(PipelineRun).filter(
        PipelineRun.id == pipeline_id,
        PipelineRun.user_id == user_id,
    ).first()
    if not pipeline:
        return {"error": "Pipeline not found"}
    if pipeline.status in ("completed", "failed", "cancelled"):
        return {"error": f"Pipeline is already {pipeline.status}"}

    pipeline.status = "cancelled"
    pipeline.completed_at = datetime.now(timezone.utc)

    # Cancel pending steps
    pending_steps = db.query(PipelineStep).filter(
        PipelineStep.pipeline_id == pipeline_id,
        PipelineStep.status.in_(["pending", "running"]),
    ).all()
    for step in pending_steps:
        step.status = "skipped"
    db.flush()

    return {"pipeline_id": pipeline_id, "status": "cancelled"}


# ── Internal Helpers ──────────────────────────────────────────────

def _build_worker_input(step: PipelineStep, config: dict, accumulated: dict, pipeline: PipelineRun) -> dict:
    """Build the input dict for a worker based on step type and accumulated results."""
    base = dict(config)
    base["user_id"] = pipeline.user_id
    base["pipeline_step_id"] = step.id

    if step.step_name == "compile":
        # Pass source_code, registry_project_id, abi, bytecode from config
        return {
            "source_code": base.get("source_code"),
            "registry_project_id": base.get("registry_project_id"),
            "abi": base.get("abi"),
            "bytecode": base.get("bytecode"),
            "compiler_version": base.get("compiler_version"),
        }

    elif step.step_name == "test":
        # Use compiled output
        return {
            "abi": accumulated.get("abi", base.get("abi", [])),
            "bytecode": accumulated.get("bytecode", base.get("bytecode", "0x")),
            "contract_name": accumulated.get("contract_name", base.get("contract_name", "Contract")),
        }

    elif step.step_name == "rbac_check":
        return {
            "user_id": pipeline.user_id,
            "action_type": "deploy",
            "target_chain": base.get("chain", "sepolia"),
            "pipeline_step_id": step.id,
        }

    elif step.step_name == "deploy":
        return {
            "user_id": pipeline.user_id,
            "abi": accumulated.get("abi", base.get("abi", [])),
            "bytecode": accumulated.get("bytecode", base.get("bytecode")),
            "constructor_args": base.get("constructor_args", []),
            "chain": base.get("chain", "sepolia"),
            "gas_limit": base.get("gas_limit"),
            "rpc_url": base.get("rpc_url"),
        }

    elif step.step_name == "verify":
        return {
            "contract_address": accumulated.get("contract_address"),
            "chain": base.get("chain", "sepolia"),
            "source_code": base.get("source_code"),
            "compiler_version": accumulated.get("compiler_version", base.get("compiler_version")),
            "contract_name": accumulated.get("contract_name", base.get("contract_name")),
        }

    elif step.step_name == "transfer_ownership":
        return {
            "user_id": pipeline.user_id,
            "contract_address": accumulated.get("contract_address"),
            "new_owner": base.get("new_owner") or base.get("user_wallet_address"),
            "chain": base.get("chain", "sepolia"),
            "rpc_url": base.get("rpc_url"),
        }

    # Fallback: pass everything
    return {**base, **accumulated}


def _record_deployment(db: Session, pipeline: PipelineRun, result: dict, config: dict):
    """Create a DeploymentRecord after successful deploy."""
    record = DeploymentRecord(
        id=str(uuid.uuid4()),
        user_id=pipeline.user_id,
        pipeline_run_id=pipeline.id,
        contract_address=result["contract_address"],
        chain=result.get("chain", config.get("chain", "sepolia")),
        chain_id=result.get("chain_id"),
        deployer_address=result.get("deployer_address"),
        owner_address=result.get("deployer_address"),  # GROOT owns initially
        tx_hash=result.get("tx_hash"),
        block_number=result.get("block_number"),
        constructor_args_json=json.dumps(config.get("constructor_args", [])),
        abi_hash=hashlib.sha256(json.dumps(config.get("abi", [])).encode()).hexdigest()[:16],
        ownership_status="groot_owned",
    )
    db.add(record)
    db.flush()
    logger.info("Deployment recorded: id=%s contract=%s", record.id, record.contract_address)


def _update_deployment_ownership(db: Session, pipeline: PipelineRun, result: dict):
    """Update DeploymentRecord after ownership transfer."""
    record = (
        db.query(DeploymentRecord)
        .filter(DeploymentRecord.pipeline_run_id == pipeline.id)
        .first()
    )
    if record:
        record.ownership_status = "user_owned"
        record.owner_address = result.get("new_owner")
        record.transfer_tx_hash = result.get("tx_hash")
        record.transferred_at = datetime.now(timezone.utc)
        db.flush()
        logger.info("Ownership updated: contract=%s new_owner=%s", record.contract_address, result.get("new_owner"))
