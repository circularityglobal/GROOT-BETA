"""
REFINET Cloud — GROOT Brain Schemas
Pydantic request/response models for the contract registry,
ABI parsing, SDK generation, and explore APIs.
"""

import json
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


# ── Request Schemas ─────────────────────────────────────────────────

class RepoInitRequest(BaseModel):
    bio: Optional[str] = Field(None, max_length=500)
    website: Optional[str] = Field(None, max_length=200)


class ContractUploadRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    chain: str = Field(default="ethereum", pattern=r"^(ethereum|base|arbitrum|polygon|solana|multi-chain)$")
    language: str = Field(default="solidity", pattern=r"^(solidity|vyper|rust|move)$")
    abi_json: str = Field(min_length=2, description="Full ABI JSON array")
    source_code: Optional[str] = Field(None, description="Contract source code (kept private)")
    address: Optional[str] = Field(None, description="Deployed contract address")
    version: Optional[str] = Field(None, max_length=20)
    description: Optional[str] = Field(None, max_length=1000)
    tags: Optional[List[str]] = Field(None, max_length=10)

    @field_validator("abi_json")
    @classmethod
    def validate_abi_json(cls, v: str) -> str:
        try:
            parsed = json.loads(v)
            if not isinstance(parsed, list):
                raise ValueError("ABI must be a JSON array")
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON format for ABI")
        return v


class ContractUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    address: Optional[str] = None
    version: Optional[str] = Field(None, max_length=20)
    tags: Optional[List[str]] = Field(None, max_length=10)
    abi_json: Optional[str] = None
    source_code: Optional[str] = None

    @field_validator("abi_json")
    @classmethod
    def validate_abi_json(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            try:
                parsed = json.loads(v)
                if not isinstance(parsed, list):
                    raise ValueError("ABI must be a JSON array")
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON format for ABI")
        return v


class VisibilityToggleRequest(BaseModel):
    is_public: bool


class FunctionToggleRequest(BaseModel):
    is_sdk_enabled: bool


# ── Response Schemas ────────────────────────────────────────────────

class UserRepoResponse(BaseModel):
    id: str
    namespace: str
    bio: Optional[str] = None
    website: Optional[str] = None
    total_contracts: int = 0
    total_public: int = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ContractSummary(BaseModel):
    id: str
    slug: str
    name: str
    chain: str
    language: str
    address: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None
    is_public: bool = False
    is_verified: bool = False
    status: str = "draft"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ContractDetail(ContractSummary):
    abi_json: Optional[str] = None  # ABI is visible to owner — source_code is NOT
    parse_errors: Optional[str] = None


class ParsedFunctionResponse(BaseModel):
    id: str
    function_name: str
    function_type: str
    selector: Optional[str] = None
    signature: Optional[str] = None
    visibility: str
    state_mutability: str
    access_level: str
    access_modifier: Optional[str] = None
    inputs: Optional[str] = None
    outputs: Optional[str] = None
    is_sdk_enabled: bool = True
    is_dangerous: bool = False
    danger_reason: Optional[str] = None
    gas_estimate: Optional[str] = None

    class Config:
        from_attributes = True


class ParsedEventResponse(BaseModel):
    id: str
    event_name: str
    signature: Optional[str] = None
    topic_hash: Optional[str] = None
    inputs: Optional[str] = None
    is_sdk_enabled: bool = True

    class Config:
        from_attributes = True


class SDKResponse(BaseModel):
    id: str
    contract_id: str
    sdk_version: str
    sdk_json: str
    sdk_hash: str
    is_public: bool = False
    chain: str
    contract_address: Optional[str] = None
    generated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ExploreContractSummary(BaseModel):
    """Public-facing contract summary — never includes source code."""
    id: str
    slug: str
    name: str
    chain: str
    language: str
    address: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None
    owner_namespace: str = ""
    is_verified: bool = False
    function_count: int = 0
    event_count: int = 0
    created_at: Optional[datetime] = None


class PaginatedContracts(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    has_next: bool
