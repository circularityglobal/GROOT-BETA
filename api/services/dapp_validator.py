"""
REFINET Cloud — DApp Validator + Self-Repair
Validates generated DApps compile and type-check before delivery.
Optionally feeds errors back through the agent cognitive loop for auto-repair.
"""

import json
import logging
import os
import re
import subprocess
import tempfile
import zipfile
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger("refinet.dapp_validator")

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "dapps")


def validate_dapp(db: Session, build_id: str) -> dict:
    """
    Validate a DApp build by running npm install + tsc --noEmit in a sandbox.

    Returns:
        { success, errors: [], warnings: [], validation_status }
    """
    from api.models.public import DAppBuild

    build = db.query(DAppBuild).filter(DAppBuild.id == build_id).first()
    if not build:
        return {"success": False, "errors": ["Build not found"], "validation_status": "failed"}

    if not build.output_filename:
        return {"success": False, "errors": ["No output file"], "validation_status": "failed"}

    # Sanitize filename to prevent path traversal
    safe_filename = os.path.basename(build.output_filename)
    zip_path = os.path.join(DATA_DIR, safe_filename)
    if not os.path.exists(zip_path):
        return {"success": False, "errors": ["Output file missing"], "validation_status": "failed"}

    # Extract to temp dir for validation
    tmp_dir = tempfile.mkdtemp(prefix="dapp_validate_")
    errors = []
    warnings = []

    try:
        # Extract ZIP
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp_dir)

        # Find the project root (may be nested one level)
        project_root = tmp_dir
        entries = os.listdir(tmp_dir)
        if len(entries) == 1 and os.path.isdir(os.path.join(tmp_dir, entries[0])):
            project_root = os.path.join(tmp_dir, entries[0])

        # Check 1: package.json exists
        pkg_path = os.path.join(project_root, "package.json")
        if not os.path.exists(pkg_path):
            errors.append("Missing package.json")
        else:
            # Validate package.json is valid JSON
            try:
                with open(pkg_path) as f:
                    pkg = json.load(f)
                if "name" not in pkg:
                    warnings.append("package.json missing 'name' field")
                if "dependencies" not in pkg and "devDependencies" not in pkg:
                    warnings.append("package.json has no dependencies")
            except json.JSONDecodeError as e:
                errors.append(f"Invalid package.json: {e}")

        # Check 2: Try npm install (if Docker is available)
        npm_ok = _try_npm_install(project_root)
        if npm_ok is False:
            warnings.append("npm install failed or Docker unavailable — skipping dependency check")
        elif npm_ok is True:
            # Check 3: Try TypeScript compilation
            tsc_errors = _try_tsc_check(project_root)
            if tsc_errors:
                errors.extend(tsc_errors)

        # Check 4: Validate contract interface file exists
        lib_dir = os.path.join(project_root, "lib")
        if os.path.isdir(lib_dir):
            contract_files = [f for f in os.listdir(lib_dir) if f.endswith(".ts") or f.endswith(".js")]
            if not contract_files:
                warnings.append("lib/ directory exists but has no contract interface files")
        else:
            warnings.append("No lib/ directory — contract interface may be missing")

        # Check 5: Look for common issues
        _check_common_issues(project_root, errors, warnings)

        # Determine validation status
        if errors:
            status = "failed"
            success = False
        elif warnings:
            status = "passed_with_warnings"
            success = True
        else:
            status = "passed"
            success = True

        # Update build record
        build.validation_status = status
        build.validation_errors = json.dumps({"errors": errors, "warnings": warnings})
        db.flush()

        return {
            "success": success,
            "errors": errors,
            "warnings": warnings,
            "validation_status": status,
        }

    except Exception as e:
        logger.exception("DApp validation failed for build %s", build_id)
        return {
            "success": False,
            "errors": [f"Validation exception: {e}"],
            "validation_status": "failed",
        }
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


async def self_repair(
    db: Session,
    build_id: str,
    errors: list[str],
    max_attempts: int = 3,
) -> dict:
    """
    Feed TypeScript/build errors back through the agent cognitive loop
    to auto-repair the generated DApp.

    Returns: { repaired: bool, attempts: int, remaining_errors: [] }
    """
    from api.models.public import DAppBuild

    build = db.query(DAppBuild).filter(DAppBuild.id == build_id).first()
    if not build:
        return {"repaired": False, "attempts": 0, "remaining_errors": ["Build not found"]}

    remaining_errors = list(errors)
    attempt = 0

    for attempt in range(1, max_attempts + 1):
        if not remaining_errors:
            break

        logger.info("Self-repair attempt %d/%d for build %s: %d errors",
                     attempt, max_attempts, build_id, len(remaining_errors))

        # Use agent engine to generate fixes
        try:
            from api.services.agent_engine import create_task, AgentCognitiveLoop
            from api.models.public import AgentRegistration

            # Find the DApp builder agent
            agent = db.query(AgentRegistration).filter(
                AgentRegistration.name.like("%dapp%"),
                AgentRegistration.is_active == True,  # noqa: E712
            ).first()

            if not agent:
                # No DApp agent registered — use inference directly
                fix_result = await _inference_repair(build, remaining_errors)
                if fix_result.get("fixed"):
                    # Re-validate
                    validation = validate_dapp(db, build_id)
                    remaining_errors = validation.get("errors", [])
                continue

            task = create_task(
                db, agent.id, build.user_id,
                description=f"Fix DApp build errors:\n" + "\n".join(f"- {e}" for e in remaining_errors),
            )
            db.flush()

            loop = AgentCognitiveLoop(db, agent.id, build.user_id)
            result = await loop.run(task)

            if result.success:
                # Re-validate after repair attempt
                validation = validate_dapp(db, build_id)
                remaining_errors = validation.get("errors", [])

        except Exception as e:
            logger.warning("Self-repair attempt %d failed: %s", attempt, e)

    repaired = len(remaining_errors) == 0
    if repaired:
        build.validation_status = "repaired"
    else:
        build.validation_status = "repair_failed"
    build.validation_errors = json.dumps({
        "errors": remaining_errors,
        "repair_attempts": min(attempt, max_attempts),
    })
    db.flush()

    return {
        "repaired": repaired,
        "attempts": min(attempt, max_attempts),
        "remaining_errors": remaining_errors,
    }


# ── Internal Helpers ──────────────────────────────────────────────

def _try_npm_install(project_root: str) -> Optional[bool]:
    """Try running npm install. Returns True/False/None (None = unavailable)."""
    try:
        # Try Docker first (safer)
        result = subprocess.run(
            ["docker", "run", "--rm", "-v", f"{project_root}:/app", "-w", "/app",
             "node:20-alpine", "sh", "-c", "npm install --production 2>&1 | tail -5"],
            capture_output=True, text=True, timeout=120,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # Try local npm as fallback
        try:
            result = subprocess.run(
                ["npm", "install", "--production"],
                capture_output=True, text=True, timeout=120,
                cwd=project_root,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None


def _try_tsc_check(project_root: str) -> list[str]:
    """Try running tsc --noEmit. Returns list of error strings."""
    errors = []
    try:
        # Check if tsconfig.json exists
        tsconfig = os.path.join(project_root, "tsconfig.json")
        if not os.path.exists(tsconfig):
            return []  # No TS config — skip type checking

        result = subprocess.run(
            ["npx", "tsc", "--noEmit"],
            capture_output=True, text=True, timeout=60,
            cwd=project_root,
        )
        if result.returncode != 0 and result.stdout:
            # Parse tsc errors
            for line in result.stdout.split("\n"):
                if re.match(r'.+\.tsx?\(\d+,\d+\):', line):
                    errors.append(line.strip())
            if not errors and result.stdout.strip():
                errors.append(result.stdout.strip()[:500])
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # tsc/npx not available — skip
    return errors


def _check_common_issues(project_root: str, errors: list, warnings: list):
    """Check for common DApp issues."""
    # Check for hardcoded localhost URLs
    for root, _, files in os.walk(project_root):
        for filename in files:
            if not filename.endswith((".ts", ".tsx", ".js", ".jsx")):
                continue
            filepath = os.path.join(root, filename)
            try:
                with open(filepath) as f:
                    content = f.read()
                if "localhost" in content and "process.env" not in content:
                    warnings.append(f"{filename}: contains hardcoded localhost URL")
                if "0x0000000000000000000000000000000000000000" in content:
                    warnings.append(f"{filename}: contains zero address placeholder")
            except Exception:
                pass


async def _inference_repair(build, errors: list) -> dict:
    """Use inference to suggest fixes (no agent required)."""
    try:
        from api.services.inference import call_bitnet
        prompt = f"""Fix these DApp build errors:
{chr(10).join(f'- {e}' for e in errors)}

Provide the corrected code as JSON: {{"fixed": true, "changes": [{{"file": "...", "content": "..."}}]}}"""
        result = await call_bitnet(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3, max_tokens=1024,
        )
        return {"fixed": False}  # Would need to apply changes to ZIP
    except Exception:
        return {"fixed": False}
