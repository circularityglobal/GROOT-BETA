"""
REFINET Cloud — ABI Parser Service
Parses smart contract ABIs, detects access control patterns,
flags dangerous operations, and classifies functions.

Pure logic — no database dependency. Testable in isolation.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from api.services.crypto_utils import compute_selector, compute_topic_hash


# ── Dataclasses ─────────────────────────────────────────────────────

@dataclass
class ParsedFunction:
    name: str
    function_type: str  # function | constructor | fallback | receive
    signature: str
    selector: str
    visibility: str  # public | external | internal | private
    state_mutability: str  # pure | view | nonpayable | payable
    access_level: str  # public | owner | admin | role_based | unknown
    access_modifier: Optional[str]
    access_roles: list[str]
    inputs: list[dict]
    outputs: list[dict]
    is_dangerous: bool
    danger_reason: Optional[str]
    natspec_notice: Optional[str] = None
    natspec_dev: Optional[str] = None


@dataclass
class ParsedEvent:
    name: str
    signature: str
    topic_hash: str
    inputs: list[dict]


@dataclass
class SecuritySummary:
    total_functions: int = 0
    public_functions: int = 0
    admin_functions: int = 0
    owner_functions: int = 0
    role_based_functions: int = 0
    unknown_functions: int = 0
    dangerous_count: int = 0
    has_selfdestruct: bool = False
    has_delegatecall: bool = False
    is_proxy: bool = False
    access_control_pattern: str = "none"  # none | ownable | access_control | custom


@dataclass
class ParsedABI:
    functions: list[ParsedFunction] = field(default_factory=list)
    events: list[ParsedEvent] = field(default_factory=list)
    security: SecuritySummary = field(default_factory=SecuritySummary)
    errors: list[str] = field(default_factory=list)


# ── Access Control Detection Patterns ───────────────────────────────

OWNER_PATTERNS = [
    (r'onlyOwner', "onlyOwner"),
    (r'require\s*\(\s*msg\.sender\s*==\s*owner', "msg.sender == owner"),
    (r'_checkOwner\(\)', "_checkOwner()"),
    (r'modifier\s+onlyOwner', "onlyOwner modifier"),
]

ADMIN_PATTERNS = [
    (r'onlyAdmin', "onlyAdmin"),
    (r'DEFAULT_ADMIN_ROLE', "DEFAULT_ADMIN_ROLE"),
    (r'onlyRole\s*\(\s*ADMIN', "onlyRole(ADMIN)"),
]

ROLE_PATTERNS = [
    (r'onlyRole\s*\(', "onlyRole"),
    (r'require\s*\(\s*hasRole\s*\(', "hasRole"),
    (r'_checkRole\s*\(', "_checkRole"),
    (r'modifier\s+only[A-Z]\w+', "custom only* modifier"),
]

DANGEROUS_PATTERNS = [
    (r'\bselfdestruct\b', "contains selfdestruct"),
    (r'\bsuicide\b', "contains suicide (deprecated selfdestruct)"),
    (r'\bdelegatecall\b', "uses delegatecall"),
    (r'\bSELFDESTRUCT\b', "contains SELFDESTRUCT opcode"),
]

PROXY_PATTERNS = [
    r'upgradeTo\s*\(',
    r'upgradeToAndCall\s*\(',
    r'_authorizeUpgrade\s*\(',
    r'ERC1967',
    r'TransparentUpgradeableProxy',
    r'UUPSUpgradeable',
]

ACCESS_CONTROL_SIGNATURES = {
    "ownable": [r'Ownable', r'onlyOwner', r'_checkOwner'],
    "access_control": [r'AccessControl', r'hasRole', r'grantRole', r'revokeRole'],
    "custom": [r'onlyRole', r'_checkRole', r'ADMIN_ROLE', r'MINTER_ROLE'],
}


# ── Core Parser ─────────────────────────────────────────────────────

def parse_abi(abi_json: str, source_code: Optional[str] = None) -> ParsedABI:
    """
    Parse an ABI JSON string into structured data with access control classification.

    Args:
        abi_json: Raw ABI JSON array string
        source_code: Optional Solidity/Vyper source for deeper analysis

    Returns:
        ParsedABI with functions, events, and security summary
    """
    result = ParsedABI()

    try:
        abi_data = json.loads(abi_json)
    except json.JSONDecodeError as e:
        result.errors.append(f"Invalid ABI JSON: {e}")
        return result

    if not isinstance(abi_data, list):
        result.errors.append("ABI must be a JSON array")
        return result

    for entry in abi_data:
        entry_type = entry.get("type", "function")

        if entry_type == "event":
            event = _parse_event(entry)
            if event:
                result.events.append(event)

        elif entry_type in ("function", "constructor", "fallback", "receive"):
            fn = _parse_function(entry, source_code)
            if fn:
                result.functions.append(fn)

        # errors and other types are informational, skip

    # Build security summary
    result.security = _build_security_summary(result.functions, source_code)

    return result


# ── Function Parsing ────────────────────────────────────────────────

def _parse_function(entry: dict, source_code: Optional[str] = None) -> Optional[ParsedFunction]:
    """Parse a single ABI function entry."""
    entry_type = entry.get("type", "function")
    name = entry.get("name", "")

    # Constructor, fallback, receive don't always have names
    if entry_type == "constructor":
        name = name or "constructor"
    elif entry_type == "fallback":
        name = name or "fallback"
    elif entry_type == "receive":
        name = name or "receive"

    if not name:
        return None

    inputs = [
        {"name": i.get("name", ""), "type": i.get("type", "")}
        for i in entry.get("inputs", [])
    ]
    outputs = [
        {"name": o.get("name", ""), "type": o.get("type", "")}
        for o in entry.get("outputs", [])
    ]

    # Build canonical signature
    input_types = ",".join(i["type"] for i in inputs)
    signature = f"{name}({input_types})"

    # Compute selector (only for regular functions)
    selector = ""
    if entry_type == "function" and name:
        selector = compute_selector(signature)

    # State mutability
    state_mutability = entry.get("stateMutability", "nonpayable")

    # Determine visibility from ABI (ABIs only expose public/external)
    visibility = "external"

    # Access control detection
    access_level = "unknown"
    access_modifier = None
    access_roles: list[str] = []

    if source_code:
        access_level, access_modifier, access_roles = _detect_access_control(name, source_code)
    elif entry_type == "constructor":
        access_level = "admin"
        access_modifier = "constructor"
    elif state_mutability in ("pure", "view"):
        # Read-only functions are generally safe to call publicly
        access_level = "public"

    # Dangerous pattern detection
    is_dangerous, danger_reason = _detect_dangerous_function(name, entry, source_code)

    return ParsedFunction(
        name=name,
        function_type=entry_type,
        signature=signature,
        selector=selector,
        visibility=visibility,
        state_mutability=state_mutability,
        access_level=access_level,
        access_modifier=access_modifier,
        access_roles=access_roles,
        inputs=inputs,
        outputs=outputs,
        is_dangerous=is_dangerous,
        danger_reason=danger_reason,
    )


# ── Event Parsing ──────────────────────────────────────────────────

def _parse_event(entry: dict) -> Optional[ParsedEvent]:
    """Parse a single ABI event entry."""
    name = entry.get("name", "")
    if not name:
        return None

    inputs = [
        {
            "name": i.get("name", ""),
            "type": i.get("type", ""),
            "indexed": i.get("indexed", False),
        }
        for i in entry.get("inputs", [])
    ]

    input_types = ",".join(i["type"] for i in inputs)
    signature = f"{name}({input_types})"
    topic_hash = compute_topic_hash(signature)

    return ParsedEvent(
        name=name,
        signature=signature,
        topic_hash=topic_hash,
        inputs=inputs,
    )


# ── Access Control Detection ───────────────────────────────────────

def _detect_access_control(
    function_name: str,
    source_code: str,
) -> tuple[str, Optional[str], list[str]]:
    """
    Detect access control level for a function by analyzing source code.

    Returns:
        (access_level, access_modifier, access_roles)
    """
    # Find the function definition block in source code
    # Look for: function functionName(...) ... {
    fn_pattern = rf'function\s+{re.escape(function_name)}\s*\([^)]*\)[^{{]*\{{'
    fn_match = re.search(fn_pattern, source_code, re.DOTALL)

    if not fn_match:
        return "unknown", None, []

    # Get the function header (everything between 'function name(' and '{')
    fn_header = fn_match.group(0)

    # Check owner patterns
    for pattern, modifier_name in OWNER_PATTERNS:
        if re.search(pattern, fn_header):
            return "owner", modifier_name, []

    # Check admin patterns
    for pattern, modifier_name in ADMIN_PATTERNS:
        if re.search(pattern, fn_header):
            return "admin", modifier_name, ["ADMIN_ROLE"]

    # Check role-based patterns
    for pattern, modifier_name in ROLE_PATTERNS:
        match = re.search(pattern, fn_header)
        if match:
            # Try to extract role name
            roles = _extract_roles(fn_header)
            return "role_based", modifier_name, roles

    # Also check the function body for require(msg.sender == ...) patterns
    # Find function body (rough heuristic — up to 500 chars after opening brace)
    fn_start = fn_match.end()
    fn_body = source_code[fn_start:fn_start + 500]

    if re.search(r'require\s*\(\s*msg\.sender\s*==\s*owner', fn_body):
        return "owner", "require(msg.sender == owner)", []
    if re.search(r'require\s*\(\s*hasRole\s*\(', fn_body):
        roles = _extract_roles(fn_body)
        return "role_based", "require(hasRole(...))", roles
    if re.search(r'_checkOwner\s*\(\s*\)', fn_body):
        return "owner", "_checkOwner()", []

    # No access control detected — it's public
    return "public", None, []


def _extract_roles(text: str) -> list[str]:
    """Extract role constant names from source text."""
    role_pattern = r'([A-Z_]+_ROLE)'
    matches = re.findall(role_pattern, text)
    return list(set(matches)) if matches else []


# ── Dangerous Pattern Detection ────────────────────────────────────

def _detect_dangerous_function(
    name: str,
    entry: dict,
    source_code: Optional[str],
) -> tuple[bool, Optional[str]]:
    """Detect if a function is potentially dangerous."""
    # Check function name patterns
    dangerous_names = {
        "selfdestruct": "contains selfdestruct",
        "destroy": "contains selfdestruct (destroy function)",
        "kill": "contains selfdestruct (kill function)",
        "upgradeTo": "proxy upgrade function — uses delegatecall",
        "upgradeToAndCall": "proxy upgrade function — uses delegatecall",
    }
    if name in dangerous_names:
        return True, dangerous_names[name]

    # Check source code if available
    if source_code:
        # Find the function body
        fn_pattern = rf'function\s+{re.escape(name)}\s*\([^)]*\)[^{{]*\{{'
        fn_match = re.search(fn_pattern, source_code, re.DOTALL)
        if fn_match:
            fn_start = fn_match.end()
            # Rough body extraction — scan for matching brace
            fn_body = source_code[fn_start:fn_start + 2000]

            for pattern, reason in DANGEROUS_PATTERNS:
                if re.search(pattern, fn_body):
                    return True, reason

    return False, None


# ── Security Summary Builder ───────────────────────────────────────

def _build_security_summary(
    functions: list[ParsedFunction],
    source_code: Optional[str],
) -> SecuritySummary:
    """Build a security summary from parsed functions."""
    summary = SecuritySummary()
    summary.total_functions = len(functions)

    for fn in functions:
        if fn.access_level == "public":
            summary.public_functions += 1
        elif fn.access_level == "owner":
            summary.owner_functions += 1
        elif fn.access_level == "admin":
            summary.admin_functions += 1
        elif fn.access_level == "role_based":
            summary.role_based_functions += 1
        else:
            summary.unknown_functions += 1

        if fn.is_dangerous:
            summary.dangerous_count += 1
            reason = (fn.danger_reason or "").lower()
            if "selfdestruct" in reason or "destroy" in reason or "suicide" in reason:
                summary.has_selfdestruct = True
            if "delegatecall" in reason:
                summary.has_delegatecall = True

    # Detect contract-level patterns from source
    if source_code:
        summary.access_control_pattern = _detect_access_control_pattern(source_code)
        summary.is_proxy = _detect_proxy(source_code)

    return summary


def _detect_access_control_pattern(source_code: str) -> str:
    """Detect the primary access control pattern used in the contract."""
    for pattern_name, patterns in ACCESS_CONTROL_SIGNATURES.items():
        for pattern in patterns:
            if re.search(pattern, source_code):
                if pattern_name == "ownable":
                    return "Ownable"
                elif pattern_name == "access_control":
                    return "AccessControl"
                elif pattern_name == "custom":
                    return "Custom Role-Based"
    return "none"


def _detect_proxy(source_code: str) -> bool:
    """Detect if the contract is a proxy."""
    for pattern in PROXY_PATTERNS:
        if re.search(pattern, source_code):
            return True
    return False
