"""
REFINET Cloud — SDK Generator Service
Takes parsed ABI data + contract metadata, produces the SDK JSON blob
that GROOT reads and MCP exposes as tools.

Cardinal rule: SDK definitions NEVER contain source code.
"""

import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Optional

from api.services.abi_parser import ParsedABI, ParsedFunction, ParsedEvent, SecuritySummary
from api.services.crypto_utils import sha256_hex


def generate_sdk(
    contract_name: str,
    chain: str,
    contract_address: Optional[str],
    owner_namespace: str,
    language: str,
    version: str,
    description: Optional[str],
    tags: Optional[list[str]],
    parsed: ParsedABI,
    enabled_function_ids: Optional[set[str]] = None,
    sdk_version: str = "1.0.0",
) -> dict:
    """
    Generate the SDK JSON definition from parsed ABI data.

    Args:
        contract_name: Human-readable contract name
        chain: Target blockchain
        contract_address: Deployed address (if known)
        owner_namespace: @username of the contract owner
        language: Contract language (solidity, vyper, etc.)
        version: Contract version
        description: Contract description
        tags: Contract tags
        parsed: ParsedABI from abi_parser
        enabled_function_ids: Set of function names to include (None = all enabled)
        sdk_version: SDK schema version

    Returns:
        SDK JSON dict — ready to serialize and store
    """
    # Separate functions into public and owner/admin groups
    public_functions = []
    admin_functions = []

    for fn in parsed.functions:
        # Skip disabled functions
        if enabled_function_ids is not None and fn.name not in enabled_function_ids:
            continue

        fn_def = _format_function(fn)

        if fn.access_level in ("owner", "admin", "role_based"):
            # Add access warning for restricted functions
            fn_def["access"] = fn.access_modifier or fn.access_level
            if fn.access_roles:
                fn_def["roles"] = fn.access_roles
            fn_def["warning"] = f"RESTRICTED — requires {fn.access_level} access"
            admin_functions.append(fn_def)
        else:
            public_functions.append(fn_def)

    # Format events
    events = [_format_event(e) for e in parsed.events]

    # Build security summary
    security = _format_security_summary(parsed.security)

    sdk = {
        "sdk_version": sdk_version,
        "contract": {
            "name": contract_name,
            "chain": chain,
            "address": contract_address,
            "language": language,
            "version": version,
            "description": description,
            "tags": tags or [],
            "owner": f"@{owner_namespace}",
        },
        "functions": {
            "public": public_functions,
            "owner_admin": admin_functions,
        },
        "events": events,
        "security_summary": security,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    return sdk


def _format_function(fn: ParsedFunction) -> dict:
    """Format a parsed function for SDK output."""
    result = {
        "name": fn.name,
        "signature": fn.signature,
        "mutability": fn.state_mutability,
        "inputs": fn.inputs,
        "outputs": fn.outputs,
    }

    if fn.selector:
        result["selector"] = fn.selector

    if fn.is_dangerous:
        result["is_dangerous"] = True
        if fn.danger_reason:
            result["danger_warning"] = fn.danger_reason

    if fn.natspec_notice:
        result["description"] = fn.natspec_notice

    if fn.state_mutability in ("pure", "view"):
        result["is_read_only"] = True

    return result


def _format_event(event: ParsedEvent) -> dict:
    """Format a parsed event for SDK output."""
    return {
        "name": event.name,
        "signature": event.signature,
        "topic_hash": event.topic_hash,
        "inputs": event.inputs,
    }


def _format_security_summary(security: SecuritySummary) -> dict:
    """Format security summary for SDK output."""
    return {
        "total_functions": security.total_functions,
        "public_functions": security.public_functions,
        "admin_functions": security.admin_functions + security.owner_functions,
        "role_based_functions": security.role_based_functions,
        "dangerous_functions": security.dangerous_count,
        "has_selfdestruct": security.has_selfdestruct,
        "has_delegatecall": security.has_delegatecall,
        "is_proxy": security.is_proxy,
        "access_control_pattern": security.access_control_pattern,
    }


def sdk_to_json(sdk: dict) -> str:
    """Serialize SDK dict to JSON string."""
    return json.dumps(sdk, indent=2, default=str)


def compute_sdk_hash(sdk_json: str) -> str:
    """Compute SHA-256 hash of SDK JSON for integrity verification."""
    return sha256_hex(sdk_json)
