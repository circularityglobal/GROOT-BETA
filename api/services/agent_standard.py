"""
REFINET Cloud — Agent Standard Validator
Validates refinet-agent.yaml manifests against the platform standard.
Used during App Store submission review and agent registration.
"""

import yaml
from typing import Optional

CURRENT_STANDARD_VERSION = "1.0.0"

VALID_CATEGORIES = {"agent", "tool", "api-service"}
VALID_LANGUAGES = {"python", "node", "rust", "go"}
VALID_FEATURES = {"inference", "webhooks", "knowledge", "messaging", "registry", "chain-events"}
VALID_DELEGATION = {"none", "approve", "auto"}

SAFETY_FIELDS = [
    "no_expose_secrets",
    "no_bypass_auth",
    "no_unauthorized_state_changes",
    "respect_rate_limits",
    "no_autonomous_destructive_onchain",
    "data_isolation",
    "audit_trail",
]


def validate_agent_manifest(content: str) -> dict:
    """
    Validate a refinet-agent.yaml manifest string.
    Returns {"valid": bool, "errors": [...], "warnings": [...], "parsed": dict | None}.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Parse YAML
    try:
        manifest = yaml.safe_load(content)
    except yaml.YAMLError as e:
        return {"valid": False, "errors": [f"Invalid YAML: {str(e)[:200]}"], "warnings": [], "parsed": None}

    if not isinstance(manifest, dict):
        return {"valid": False, "errors": ["Manifest must be a YAML mapping"], "warnings": [], "parsed": None}

    # ── Required top-level fields ──
    for field in ["agent_id", "name", "version", "description", "category"]:
        val = manifest.get(field)
        if not val or (isinstance(val, str) and not val.strip()):
            errors.append(f"Missing required field: {field}")

    # Agent ID format
    agent_id = manifest.get("agent_id", "")
    if agent_id and not _is_valid_id(agent_id):
        errors.append("agent_id must be lowercase alphanumeric with hyphens only")

    # Category
    category = manifest.get("category", "")
    if category and category not in VALID_CATEGORIES:
        errors.append(f"category must be one of: {', '.join(sorted(VALID_CATEGORIES))}")

    # Version (basic semver check)
    version = manifest.get("version", "")
    if version and not _is_semver(version):
        errors.append("version must follow semver (e.g. 1.0.0)")

    # Description length
    desc = manifest.get("description", "")
    if desc and len(desc) > 200:
        warnings.append("description exceeds 200 characters — will be truncated in App Store")

    # ── SOUL ──
    soul = manifest.get("soul")
    if not isinstance(soul, dict):
        errors.append("Missing required section: soul")
    else:
        if not soul.get("identity"):
            errors.append("soul.identity is required")
        goals = soul.get("goals", [])
        if not goals or (isinstance(goals, list) and all(not g for g in goals)):
            errors.append("soul.goals must contain at least one goal")
        constraints = soul.get("constraints", [])
        if not constraints or len(constraints) < 5:
            warnings.append("soul.constraints should include the 5 mandatory platform constraints")
        delegation = soul.get("delegation_policy", "none")
        if delegation not in VALID_DELEGATION:
            errors.append(f"soul.delegation_policy must be one of: {', '.join(VALID_DELEGATION)}")

    # ── Runtime ──
    runtime = manifest.get("runtime")
    if not isinstance(runtime, dict):
        errors.append("Missing required section: runtime")
    else:
        if not runtime.get("entrypoint"):
            errors.append("runtime.entrypoint is required")
        lang = runtime.get("language", "")
        if lang and lang not in VALID_LANGUAGES:
            errors.append(f"runtime.language must be one of: {', '.join(sorted(VALID_LANGUAGES))}")
        features = runtime.get("features", [])
        if features:
            invalid = set(features) - VALID_FEATURES
            if invalid:
                errors.append(f"Invalid features: {', '.join(sorted(invalid))}")
        # Resource bounds
        resources = runtime.get("resources", {})
        if resources:
            cpu = resources.get("cpu", 0.5)
            if not (0.1 <= cpu <= 2.0):
                errors.append("runtime.resources.cpu must be between 0.1 and 2.0")
            mem = resources.get("memory_mb", 512)
            if not (128 <= mem <= 4096):
                errors.append("runtime.resources.memory_mb must be between 128 and 4096")
            disk = resources.get("disk_mb", 500)
            if not (100 <= disk <= 5000):
                errors.append("runtime.resources.disk_mb must be between 100 and 5000")

    # ── Compliance ──
    compliance = manifest.get("compliance")
    if not isinstance(compliance, dict):
        errors.append("Missing required section: compliance")
    else:
        std_ver = compliance.get("standard_version", "")
        if not std_ver:
            errors.append("compliance.standard_version is required")

        safety = compliance.get("safety_acknowledgment", {})
        if not isinstance(safety, dict):
            errors.append("compliance.safety_acknowledgment must be a mapping")
        else:
            for sf in SAFETY_FIELDS:
                if not safety.get(sf):
                    errors.append(f"compliance.safety_acknowledgment.{sf} must be true")

        # External domains validation
        if compliance.get("makes_external_calls") and not compliance.get("external_domains"):
            warnings.append("makes_external_calls is true but external_domains is empty — list all domains contacted")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "parsed": manifest if len(errors) == 0 else None,
    }


def manifest_to_soul_md(manifest: dict) -> str:
    """Convert a validated refinet-agent.yaml into SOUL.md markdown format."""
    soul = manifest.get("soul", {})
    parts = []

    parts.append(f"# Identity\n{soul.get('identity', '')}\n")

    goals = soul.get("goals", [])
    if goals:
        parts.append("# Goals")
        for g in goals:
            if g:
                parts.append(f"- {g}")
        parts.append("")

    constraints = soul.get("constraints", [])
    if constraints:
        parts.append("# Constraints")
        for c in constraints:
            if c:
                parts.append(f"- {c}")
        parts.append("")

    tools = soul.get("tools_allowed", [])
    if tools:
        parts.append("# Tools")
        for t in tools:
            if t:
                parts.append(f"- {t}")
        parts.append("")

    delegation = soul.get("delegation_policy", "none")
    parts.append(f"# Delegation\n{delegation}")

    return "\n".join(parts)


def _is_valid_id(s: str) -> bool:
    """Check agent_id is lowercase alphanumeric with hyphens."""
    import re
    return bool(re.match(r'^[a-z][a-z0-9\-]*$', s))


def _is_semver(s: str) -> bool:
    """Basic semver check (X.Y.Z)."""
    parts = s.split(".")
    if len(parts) != 3:
        return False
    return all(p.isdigit() for p in parts)
