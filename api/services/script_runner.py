"""
REFINET Cloud — Script Runner Service
Discovers, executes, and tracks Python scripts for agents and admins.
Scripts are Python files in scripts/ with a SCRIPT_META dict.
"""

import asyncio
import importlib.util
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from api.models.internal import ScriptExecution

logger = logging.getLogger("refinet.scripts")

# Directory where executable scripts live
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"


# ── Script Discovery ─────────────────────────────────────────────

def discover_scripts() -> list[dict]:
    """
    Scan scripts/ directory for Python files with SCRIPT_META.
    Returns metadata for all discovered scripts.
    """
    scripts = []

    for category_dir in ["ops", "analysis", "maintenance", "chain", "dapp"]:
        dir_path = SCRIPTS_DIR / category_dir
        if not dir_path.is_dir():
            continue

        for py_file in sorted(dir_path.glob("*.py")):
            if py_file.name.startswith("_"):
                continue

            meta = _load_script_meta(py_file)
            if meta:
                meta["path"] = str(py_file)
                meta["category"] = category_dir
                meta["file_name"] = py_file.name
                scripts.append(meta)

    return scripts


def _load_script_meta(path: Path) -> Optional[dict]:
    """Load SCRIPT_META from a Python file without executing it."""
    try:
        with open(path) as f:
            content = f.read()

        # Quick check: does the file contain SCRIPT_META?
        if "SCRIPT_META" not in content:
            return {
                "name": path.stem,
                "description": f"Script: {path.stem}",
                "requires_admin": False,
            }

        # Load the module to extract SCRIPT_META
        spec = importlib.util.spec_from_file_location(f"script_{path.stem}", path)
        module = importlib.util.module_from_spec(spec)

        # Only extract SCRIPT_META, don't run the module's main
        try:
            spec.loader.exec_module(module)
        except Exception:
            pass

        meta = getattr(module, "SCRIPT_META", None)
        if isinstance(meta, dict):
            return meta

        return {
            "name": path.stem,
            "description": f"Script: {path.stem}",
            "requires_admin": False,
        }
    except Exception as e:
        logger.warning(f"Failed to load script meta from {path}: {e}")
        return None


# ── Script Execution ─────────────────────────────────────────────

async def execute_script(
    db: Session,
    script_name: str,
    args: Optional[dict] = None,
    started_by: Optional[str] = None,
) -> dict:
    """
    Execute a script by name and record the execution.
    Runs in a thread pool to avoid blocking the event loop.
    """
    # Find the script
    scripts = discover_scripts()
    script = next((s for s in scripts if s["name"] == script_name), None)
    if not script:
        return {"error": f"Script '{script_name}' not found"}

    # Check admin requirement
    if script.get("requires_admin") and not started_by:
        return {"error": "Admin authentication required"}

    # Create execution record
    execution = ScriptExecution(
        id=str(uuid.uuid4()),
        script_name=script_name,
        args_json=json.dumps(args) if args else None,
        status="running",
        started_by=started_by,
        started_at=datetime.now(timezone.utc),
    )
    db.add(execution)
    db.flush()

    # Run the script
    start_time = time.time()
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None, _run_script_sync, script["path"], args,
        )

        duration_ms = int((time.time() - start_time) * 1000)
        execution.status = "completed"
        execution.output = result.get("output", "")[:10000]  # Cap output size
        execution.duration_ms = duration_ms
        execution.completed_at = datetime.now(timezone.utc)
        db.flush()

        return {
            "execution_id": execution.id,
            "status": "completed",
            "output": result.get("output", ""),
            "duration_ms": duration_ms,
        }

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        execution.status = "failed"
        execution.error = str(e)[:5000]
        execution.duration_ms = duration_ms
        execution.completed_at = datetime.now(timezone.utc)
        db.flush()

        return {
            "execution_id": execution.id,
            "status": "failed",
            "error": str(e),
            "duration_ms": duration_ms,
        }


def _run_script_sync(script_path: str, args: Optional[dict]) -> dict:
    """Run a script synchronously (called in thread pool)."""
    import subprocess
    import sys

    cmd = [sys.executable, script_path]

    # Pass args as JSON via environment variable
    env = os.environ.copy()
    if args:
        env["SCRIPT_ARGS"] = json.dumps(args)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,  # 5 minute timeout
        env=env,
        cwd=str(SCRIPTS_DIR.parent),
    )

    if result.returncode != 0:
        raise RuntimeError(f"Script exited with code {result.returncode}: {result.stderr}")

    return {"output": result.stdout}


# ── Execution History ────────────────────────────────────────────

def list_executions(
    db: Session,
    script_name: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """List past script executions."""
    q = db.query(ScriptExecution)
    if script_name:
        q = q.filter(ScriptExecution.script_name == script_name)

    executions = q.order_by(ScriptExecution.started_at.desc()).limit(limit).all()

    return [
        {
            "id": e.id,
            "script_name": e.script_name,
            "status": e.status,
            "started_by": e.started_by,
            "started_at": e.started_at.isoformat() if e.started_at else None,
            "completed_at": e.completed_at.isoformat() if e.completed_at else None,
            "duration_ms": e.duration_ms,
            "error": e.error,
        }
        for e in executions
    ]
