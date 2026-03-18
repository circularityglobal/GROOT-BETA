"""REFINET Cloud — Registry Schemas"""

import json
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime


# ── Project ──────────────────────────────────────────────────────────

class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None
    readme: Optional[str] = None
    visibility: str = Field(default="public", pattern=r"^(public|private|platform)$")
    category: str = Field(default="utility", pattern=r"^(defi|token|governance|bridge|utility|oracle|nft|dao|sdk|library)$")
    chain: str = Field(default="ethereum", pattern=r"^(ethereum|base|arbitrum|polygon|solana|multi-chain)$")
    tags: Optional[List[str]] = None
    license: Optional[str] = None
    website_url: Optional[str] = None
    repo_url: Optional[str] = None


class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    readme: Optional[str] = None
    visibility: Optional[str] = Field(default=None, pattern=r"^(public|private|platform)$")
    category: Optional[str] = Field(default=None, pattern=r"^(defi|token|governance|bridge|utility|oracle|nft|dao|sdk|library)$")
    chain: Optional[str] = Field(default=None, pattern=r"^(ethereum|base|arbitrum|polygon|solana|multi-chain)$")
    tags: Optional[List[str]] = None
    license: Optional[str] = None
    website_url: Optional[str] = None
    repo_url: Optional[str] = None


class ProjectSummary(BaseModel):
    id: str
    slug: str
    name: str
    description: Optional[str] = None
    owner_id: str
    owner_username: Optional[str] = None
    visibility: str
    category: str
    chain: str
    tags: Optional[List[str]] = None
    stars_count: int = 0
    forks_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ProjectDetail(ProjectSummary):
    readme: Optional[str] = None
    license: Optional[str] = None
    website_url: Optional[str] = None
    repo_url: Optional[str] = None
    logo_url: Optional[str] = None
    watchers_count: int = 0
    is_starred: bool = False
    abi_count: int = 0
    sdk_count: int = 0
    logic_count: int = 0


# ── ABI ──────────────────────────────────────────────────────────────

class ABICreateRequest(BaseModel):
    contract_name: str = Field(min_length=1, max_length=200)
    abi_json: str  # Full ABI JSON string
    contract_address: Optional[str] = Field(default=None, pattern=r"^0x[0-9a-fA-F]{40}$")
    chain: str = Field(default="ethereum", pattern=r"^(ethereum|base|arbitrum|polygon|solana|multi-chain)$")
    compiler_version: Optional[str] = None
    optimization_enabled: bool = False
    source_hash: Optional[str] = None
    bytecode_hash: Optional[str] = None

    @field_validator("abi_json")
    @classmethod
    def validate_abi_json(cls, v: str) -> str:
        try:
            parsed = json.loads(v)
            if not isinstance(parsed, list):
                raise ValueError("ABI must be a JSON array")
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in abi_json")
        return v


class ABIItem(BaseModel):
    id: str
    project_id: str
    contract_name: str
    contract_address: Optional[str] = None
    chain: str
    abi_json: Optional[str] = None  # Omitted in list views for size
    compiler_version: Optional[str] = None
    optimization_enabled: bool = False
    source_hash: Optional[str] = None
    is_verified: bool = False
    created_at: Optional[datetime] = None


class ABIDetail(ABIItem):
    abi_json: str
    bytecode_hash: Optional[str] = None
    updated_at: Optional[datetime] = None


# ── SDK ──────────────────────────────────────────────────────────────

class SDKCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    language: str = Field(pattern=r"^(solidity|vyper|rust|typescript|python|go|java)$")
    version: str = Field(min_length=1, max_length=50)
    package_name: Optional[str] = None
    install_command: Optional[str] = None
    reference_url: Optional[str] = None
    documentation: Optional[str] = None
    code_samples: Optional[str] = None  # JSON array of {title, language, code}
    readme_content: Optional[str] = None


class SDKItem(BaseModel):
    id: str
    project_id: str
    name: str
    language: str
    version: str
    package_name: Optional[str] = None
    install_command: Optional[str] = None
    reference_url: Optional[str] = None
    created_at: Optional[datetime] = None


class SDKDetail(SDKItem):
    documentation: Optional[str] = None
    code_samples: Optional[str] = None
    readme_content: Optional[str] = None
    updated_at: Optional[datetime] = None


# ── Execution Logic ──────────────────────────────────────────────────

class ExecutionLogicCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    logic_type: str = Field(pattern=r"^(function|workflow|script|hook|trigger)$")
    description: Optional[str] = None
    function_signature: Optional[str] = None  # e.g. "stake(uint256)"
    input_schema: Optional[str] = None  # JSON Schema
    output_schema: Optional[str] = None  # JSON Schema
    code_reference: Optional[str] = None
    chain: Optional[str] = None
    gas_estimate: Optional[int] = Field(default=None, ge=0)
    is_read_only: bool = False
    preconditions: Optional[str] = None  # JSON array
    abi_id: Optional[str] = None  # Link to specific ABI
    version: Optional[str] = None


class ExecutionLogicItem(BaseModel):
    id: str
    project_id: str
    name: str
    version: Optional[str] = None
    logic_type: str
    description: Optional[str] = None
    function_signature: Optional[str] = None
    chain: Optional[str] = None
    gas_estimate: Optional[int] = None
    is_read_only: bool = False
    is_verified: bool = False
    execution_count: int = 0
    created_at: Optional[datetime] = None


class ExecutionLogicDetail(ExecutionLogicItem):
    abi_id: Optional[str] = None
    input_schema: Optional[str] = None
    output_schema: Optional[str] = None
    code_reference: Optional[str] = None
    preconditions: Optional[str] = None
    verified_by: Optional[str] = None
    updated_at: Optional[datetime] = None


# ── Search & Pagination ──────────────────────────────────────────────

class PaginatedProjects(BaseModel):
    items: List[ProjectSummary]
    total: int
    page: int
    page_size: int
    has_next: bool


# ── User Profile (Registry) ─────────────────────────────────────────

class UserRegistryProfile(BaseModel):
    username: str
    eth_address: Optional[str] = None
    tier: str = "free"
    project_count: int = 0
    stars_given: int = 0
    total_stars_received: int = 0
    joined_at: Optional[datetime] = None
    pinned_projects: List[ProjectSummary] = []
