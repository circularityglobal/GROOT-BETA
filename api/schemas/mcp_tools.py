"""REFINET Cloud — MCP Tool Schemas"""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any


# ── MCP Tool Definitions ─────────────────────────────────────────────

class MCPToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]


class MCPToolCallRequest(BaseModel):
    tool: str
    arguments: Dict[str, Any] = {}


class MCPToolCallResponse(BaseModel):
    tool: str
    result: Any = None
    error: Optional[str] = None


# ── Registry Search Tool ─────────────────────────────────────────────

class SearchRegistryArgs(BaseModel):
    query: str
    chain: Optional[str] = None
    category: Optional[str] = None
    page: int = 1
    page_size: int = 20


class GetProjectArgs(BaseModel):
    slug: str


class GetABIArgs(BaseModel):
    abi_id: str


class GetSDKArgs(BaseModel):
    sdk_id: str


class GetExecutionLogicArgs(BaseModel):
    logic_id: str


class ListProjectsArgs(BaseModel):
    chain: Optional[str] = None
    category: Optional[str] = None
    owner: Optional[str] = None
    page: int = 1
    page_size: int = 20
    sort_by: str = "stars"  # stars | recent | name


# ── ABI Utility Tools ────────────────────────────────────────────────

class DecodeFunctionArgs(BaseModel):
    abi_json: str
    calldata: str  # hex-encoded calldata


class EncodeFunctionArgs(BaseModel):
    abi_json: str
    function_name: str
    args: List[Any]


class GetContractInterfaceArgs(BaseModel):
    abi_json: str


class VerifyABIArgs(BaseModel):
    abi_json: str
    chain: str
    address: str


class SimulateCallArgs(BaseModel):
    logic_id: str
    params: Dict[str, Any] = {}


class GetDeploymentInfoArgs(BaseModel):
    abi_id: str


# ── ABI Utility Responses ────────────────────────────────────────────

class DecodedArg(BaseModel):
    name: str
    type: str
    value: Any


class DecodedFunction(BaseModel):
    function_name: str
    args: List[DecodedArg]


class ContractFunction(BaseModel):
    name: str
    type: str  # function | event | constructor | fallback | receive
    state_mutability: Optional[str] = None  # pure | view | nonpayable | payable
    inputs: List[Dict[str, str]] = []
    outputs: List[Dict[str, str]] = []


class ContractInterface(BaseModel):
    functions: List[ContractFunction]
    events: List[ContractFunction]
    total_functions: int
    total_events: int


class VerificationResult(BaseModel):
    is_valid: bool
    message: str
    matched_functions: int = 0


class SimulationResult(BaseModel):
    success: bool
    result: Any = None
    gas_used: Optional[int] = None
    error: Optional[str] = None


class DeploymentInfo(BaseModel):
    contract_name: str
    contract_address: Optional[str] = None
    chain: str
    is_verified: bool
    compiler_version: Optional[str] = None
