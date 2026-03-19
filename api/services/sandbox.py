"""
REFINET Cloud — Sandbox Service
Provisions isolated Docker containers for admin review of submitted code.
Network-isolated, time-limited, no platform access.

Security hardening:
- Zip slip prevention (path traversal validation on every archive entry)
- User Dockerfiles are NEVER executed — always overwritten with platform-generated ones
- Container names validated against strict alphanumeric pattern
- Resource limits clamped to safe ranges
- Build logs sanitized before returning to clients
- --security-opt=no-new-privileges on all containers
"""

import json
import logging
import os
import re
import random
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from api.models.internal import SandboxEnvironment
from api.models.public import AppSubmission

logger = logging.getLogger("refinet.sandbox")

SANDBOX_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "sandboxes")
SANDBOX_NETWORK = "refinet_sandbox_isolated"

# Default resource limits
DEFAULT_LIMITS = {
    "cpu": "0.5",          # 0.5 CPU cores
    "memory_mb": 512,      # 512MB RAM
    "disk_mb": 500,        # 500MB disk
}

# Hard caps (admin cannot exceed these even if they try)
MAX_LIMITS = {"cpu": 2.0, "memory_mb": 4096, "disk_mb": 5000}
MIN_LIMITS = {"cpu": 0.1, "memory_mb": 128, "disk_mb": 100}

# Sandbox auto-expiry: 4 hours
SANDBOX_TTL_HOURS = 4

# Port range for sandbox containers
PORT_RANGE_MIN = 9100
PORT_RANGE_MAX = 9199

# Max total extracted size: 500MB (zip bomb protection)
MAX_EXTRACTED_SIZE = 500 * 1024 * 1024


def _pick_port() -> int:
    """Pick a random available port in the sandbox range."""
    return random.randint(PORT_RANGE_MIN, PORT_RANGE_MAX)


def _validate_name(name: str) -> bool:
    """Validate container/image names against strict pattern."""
    return bool(re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]*$', name)) and len(name) < 128


def _sanitize_limits(raw: Optional[dict]) -> dict:
    """Clamp resource limits to safe ranges."""
    base = dict(DEFAULT_LIMITS)
    if not raw:
        return base
    try:
        cpu = max(MIN_LIMITS["cpu"], min(MAX_LIMITS["cpu"], float(raw.get("cpu", base["cpu"]))))
        base["cpu"] = str(cpu)
    except (ValueError, TypeError):
        pass
    try:
        base["memory_mb"] = max(MIN_LIMITS["memory_mb"], min(MAX_LIMITS["memory_mb"], int(raw.get("memory_mb", base["memory_mb"]))))
    except (ValueError, TypeError):
        pass
    try:
        base["disk_mb"] = max(MIN_LIMITS["disk_mb"], min(MAX_LIMITS["disk_mb"], int(raw.get("disk_mb", base["disk_mb"]))))
    except (ValueError, TypeError):
        pass
    return base


def _safe_extract_zip(zip_path: str, dest_dir: str):
    """
    Extract ZIP with zip-slip protection and zip-bomb detection.
    Raises ValueError on any dangerous content.
    """
    abs_dest = os.path.realpath(dest_dir)
    total_size = 0

    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            # Zip bomb check
            total_size += member.file_size
            if total_size > MAX_EXTRACTED_SIZE:
                raise ValueError(f"Archive exceeds max extracted size ({MAX_EXTRACTED_SIZE // (1024*1024)}MB) — possible zip bomb")

            # Zip slip check: ensure resolved path stays within dest_dir
            member_path = os.path.realpath(os.path.join(dest_dir, member.filename))
            if not member_path.startswith(abs_dest + os.sep) and member_path != abs_dest:
                raise ValueError(f"Path traversal detected in archive: {member.filename}")

            # Block absolute paths and parent references
            if member.filename.startswith("/") or ".." in member.filename:
                raise ValueError(f"Dangerous path in archive: {member.filename}")

        # Safe to extract
        zf.extractall(dest_dir)


def _run_docker(args: list[str], timeout: int = 60) -> tuple[int, str, str]:
    """Run a docker command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["docker"] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return -1, "", "Docker not found. Install Docker to use sandbox features."
    except subprocess.TimeoutExpired:
        return -2, "", "Docker command timed out"


def _ensure_isolated_network():
    """Create the isolated Docker network if it doesn't exist."""
    code, out, _ = _run_docker(["network", "ls", "--format", "{{.Name}}"])
    if SANDBOX_NETWORK not in out.split("\n"):
        _run_docker(["network", "create", "--internal", SANDBOX_NETWORK])


def _generate_dockerfile(category: str) -> str:
    """Generate a safe Dockerfile based on submission category."""
    if category in ("dapp", "template"):
        return """FROM node:20-alpine
WORKDIR /app
COPY . .
RUN if [ -f package.json ]; then npm install --production 2>/dev/null || true; fi
EXPOSE 3000
CMD ["sh", "-c", "if [ -f package.json ]; then npx serve -s . -l 3000 2>/dev/null || npx http-server -p 3000 2>/dev/null || python3 -m http.server 3000; else python3 -m http.server 3000; fi"]
"""
    elif category == "agent":
        return """FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt 2>/dev/null || true; fi
EXPOSE 8080
CMD ["sh", "-c", "if [ -f main.py ]; then python main.py; elif [ -f app.py ]; then python app.py; else echo 'No entrypoint found. Files:' && ls -la && sleep 3600; fi"]
"""
    elif category in ("tool", "api-service"):
        return """FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . .
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt 2>/dev/null || true; fi
RUN if [ -f package.json ]; then npm install --production 2>/dev/null || true; fi
EXPOSE 8080
CMD ["sh", "-c", "if [ -f main.py ]; then python main.py; elif [ -f app.py ]; then python app.py; elif [ -f index.js ]; then node index.js; else echo 'No entrypoint. Files:' && ls -la && sleep 3600; fi"]
"""
    else:
        # dataset, digital-asset, or unknown — just serve files
        return """FROM python:3.11-slim
WORKDIR /app
COPY . .
EXPOSE 8080
CMD ["sh", "-c", "echo '=== Submission Contents ===' && find . -type f | head -50 && echo '===' && python3 -m http.server 8080"]
"""


def provision_sandbox(
    db: Session,
    submission_id: str,
    created_by: str,
    resource_limits: Optional[dict] = None,
) -> dict:
    """Provision an isolated Docker sandbox for a submission."""
    # Get submission from public DB
    from api.database import get_public_session
    with get_public_session() as pub_db:
        sub = pub_db.query(AppSubmission).filter(AppSubmission.id == submission_id).first()
        if not sub:
            return {"error": "Submission not found"}
        if not sub.artifact_path or not os.path.exists(sub.artifact_path):
            return {"error": "No artifact uploaded for this submission"}
        artifact_path = sub.artifact_path
        category = sub.category

    # Check if sandbox already exists
    existing = db.query(SandboxEnvironment).filter(
        SandboxEnvironment.submission_id == submission_id,
        SandboxEnvironment.status.in_(["provisioning", "ready", "running"]),
    ).first()
    if existing:
        return {"error": "Sandbox already exists for this submission", "sandbox_id": existing.id}

    # Check Docker is available
    code, _, err = _run_docker(["info"], timeout=10)
    if code != 0:
        return {"error": "Docker is not available on this host"}

    # Sanitize resource limits (clamp to safe ranges)
    limits = _sanitize_limits(resource_limits)
    port = _pick_port()

    # Validate container name (submission_id is a UUID, but verify anyway)
    sandbox_name = f"refinet-sandbox-{re.sub(r'[^a-zA-Z0-9]', '', submission_id[:12])}"
    if not _validate_name(sandbox_name):
        return {"error": "Invalid submission ID format"}

    sandbox = SandboxEnvironment(
        submission_id=submission_id,
        status="provisioning",
        container_name=sandbox_name,
        port=port,
        network_isolated=True,
        resource_limits=json.dumps(limits),
        created_by=created_by,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=SANDBOX_TTL_HOURS),
    )
    db.add(sandbox)
    db.flush()

    build_logs = []

    try:
        # 1. Extract artifact with zip-slip and zip-bomb protection
        sandbox_dir = os.path.join(SANDBOX_DIR, sandbox.id)
        extract_dir = os.path.join(sandbox_dir, "app")
        os.makedirs(extract_dir, exist_ok=True)

        try:
            _safe_extract_zip(artifact_path, extract_dir)
        except ValueError as e:
            sandbox.status = "failed"
            sandbox.logs = f"Extraction blocked: {e}"
            db.flush()
            return {"error": f"Artifact rejected: {e}"}

        build_logs.append("Extracted artifact to sandbox directory")

        # 2. SECURITY: Always overwrite Dockerfile — never execute user-provided ones
        dockerfile_path = os.path.join(extract_dir, "Dockerfile")
        if os.path.exists(dockerfile_path):
            build_logs.append("WARNING: User-provided Dockerfile found and overwritten for security")
        with open(dockerfile_path, "w") as f:
            f.write(_generate_dockerfile(category))
        build_logs.append(f"Generated platform Dockerfile for category: {category}")

        # 3. Ensure isolated network
        _ensure_isolated_network()

        # 4. Build the image
        image_tag = f"refinet-sandbox:{re.sub(r'[^a-zA-Z0-9]', '', sandbox.id[:12])}"
        code, out, err = _run_docker(
            ["build", "-t", image_tag, extract_dir],
            timeout=300,
        )
        build_logs.append(f"Docker build: exit={code}")
        if err:
            # Sanitize: strip filesystem paths from error output
            sanitized = re.sub(r'/[^\s:]+/data/sandboxes/[^\s:]+', '<sandbox-dir>', err[-500:])
            build_logs.append(f"Build output: {sanitized}")

        if code != 0:
            sandbox.status = "failed"
            sandbox.logs = "\n".join(build_logs)
            db.flush()
            return {"error": "Docker build failed. Check sandbox logs for details."}

        sandbox.image_tag = image_tag

        # 5. Run the container with maximum isolation
        run_args = [
            "run", "-d",
            "--name", sandbox_name,
            "--network", SANDBOX_NETWORK,
            "-p", f"{port}:3000",
            "-p", f"{port + 100}:8080",
            "--cpus", str(limits["cpu"]),
            "--memory", f"{limits['memory_mb']}m",
            "--read-only",
            "--tmpfs", "/tmp:size=50m",
            "--no-healthcheck",
            "--security-opt", "no-new-privileges",    # Prevent privilege escalation
            "--cap-drop", "ALL",                       # Drop all Linux capabilities
            "--pids-limit", "100",                     # Limit number of processes
            "--label", f"refinet.sandbox={sandbox.id}",
            "--label", f"refinet.submission={submission_id}",
            image_tag,
        ]
        code, container_id, err = _run_docker(run_args, timeout=30)
        build_logs.append(f"Docker run: exit={code}")

        if code != 0:
            sandbox.status = "failed"
            sandbox.logs = "\n".join(build_logs)
            db.flush()
            return {"error": "Container start failed. Check sandbox logs for details."}

        sandbox.container_id = container_id
        sandbox.status = "running"
        sandbox.access_url = f"http://localhost:{port}"
        sandbox.logs = "\n".join(build_logs)
        db.flush()

        # Update submission with sandbox ID (cross-DB)
        with get_public_session() as pub_db:
            sub = pub_db.query(AppSubmission).filter(AppSubmission.id == submission_id).first()
            if sub:
                sub.sandbox_id = sandbox.id
                pub_db.commit()

        return {
            "sandbox_id": sandbox.id,
            "status": "running",
            "access_url": sandbox.access_url,
            "port": port,
            "container_name": sandbox_name,
            "expires_at": sandbox.expires_at.isoformat(),
        }

    except Exception as e:
        sandbox.status = "failed"
        build_logs.append(f"Error: provisioning failed")
        sandbox.logs = "\n".join(build_logs)
        db.flush()
        logger.exception("Sandbox provisioning failed for submission %s", submission_id)
        return {"error": "Sandbox provisioning failed. See server logs for details."}


def get_sandbox_status(db: Session, sandbox_id: str) -> Optional[dict]:
    """Get sandbox status and logs."""
    sandbox = db.query(SandboxEnvironment).filter(SandboxEnvironment.id == sandbox_id).first()
    if not sandbox:
        return None

    # Check if container is still running
    if sandbox.container_id and sandbox.status == "running":
        code, out, _ = _run_docker(["inspect", "--format", "{{.State.Status}}", sandbox.container_id], timeout=5)
        if code == 0:
            container_status = out.strip()
            if container_status != "running":
                sandbox.status = "stopped"
                db.flush()

    # Check expiry
    if sandbox.expires_at and datetime.now(timezone.utc) > sandbox.expires_at and sandbox.status == "running":
        destroy_sandbox(db, sandbox_id)
        sandbox.status = "destroyed"
        db.flush()

    return {
        "id": sandbox.id,
        "submission_id": sandbox.submission_id,
        "status": sandbox.status,
        "container_name": sandbox.container_name,
        "port": sandbox.port,
        "access_url": sandbox.access_url,
        "network_isolated": sandbox.network_isolated,
        "resource_limits": json.loads(sandbox.resource_limits) if sandbox.resource_limits else DEFAULT_LIMITS,
        "created_by": sandbox.created_by,
        "created_at": sandbox.created_at.isoformat() if sandbox.created_at else None,
        "expires_at": sandbox.expires_at.isoformat() if sandbox.expires_at else None,
        "destroyed_at": sandbox.destroyed_at.isoformat() if sandbox.destroyed_at else None,
        "logs": sandbox.logs,
    }


def get_sandbox_logs(db: Session, sandbox_id: str, tail: int = 100) -> dict:
    """Get runtime logs from the sandbox container."""
    sandbox = db.query(SandboxEnvironment).filter(SandboxEnvironment.id == sandbox_id).first()
    if not sandbox:
        return {"error": "Sandbox not found"}

    if not sandbox.container_id:
        return {"build_logs": sandbox.logs or "", "runtime_logs": ""}

    # Clamp tail to safe range
    tail = max(1, min(500, tail))

    code, out, err = _run_docker(["logs", "--tail", str(tail), sandbox.container_id], timeout=10)
    return {
        "build_logs": sandbox.logs or "",
        "runtime_logs": out if code == 0 else "Error fetching logs",
    }


def destroy_sandbox(db: Session, sandbox_id: str) -> dict:
    """Tear down a sandbox container and clean up."""
    sandbox = db.query(SandboxEnvironment).filter(SandboxEnvironment.id == sandbox_id).first()
    if not sandbox:
        return {"error": "Sandbox not found"}

    if sandbox.status == "destroyed":
        return {"message": "Already destroyed"}

    # Stop and remove container
    if sandbox.container_id:
        _run_docker(["stop", sandbox.container_id], timeout=15)
        _run_docker(["rm", "-f", sandbox.container_id], timeout=10)

    # Remove image
    if sandbox.image_tag:
        _run_docker(["rmi", "-f", sandbox.image_tag], timeout=10)

    # Clean up sandbox directory
    sandbox_dir = os.path.join(SANDBOX_DIR, sandbox.id)
    if os.path.exists(sandbox_dir):
        shutil.rmtree(sandbox_dir, ignore_errors=True)

    sandbox.status = "destroyed"
    sandbox.destroyed_at = datetime.now(timezone.utc)
    db.flush()

    return {"message": "Sandbox destroyed", "sandbox_id": sandbox_id}


def list_active_sandboxes(db: Session) -> list[dict]:
    """List all active (non-destroyed) sandboxes."""
    sandboxes = db.query(SandboxEnvironment).filter(
        SandboxEnvironment.status.in_(["provisioning", "ready", "running", "stopped"]),
    ).order_by(SandboxEnvironment.created_at.desc()).all()

    return [
        {
            "id": s.id,
            "submission_id": s.submission_id,
            "status": s.status,
            "container_name": s.container_name,
            "port": s.port,
            "access_url": s.access_url,
            "created_by": s.created_by,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "expires_at": s.expires_at.isoformat() if s.expires_at else None,
        }
        for s in sandboxes
    ]
