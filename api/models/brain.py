"""
REFINET Cloud — GROOT Brain Models
User-managed smart contract repository with ABI parsing,
access control classification, and SDK generation.
All tables in public.db (user-facing data).

Cardinal rule: GROOT never sees source_code — only sdk_definitions.
"""

from sqlalchemy import (
    Column, String, Boolean, Integer, DateTime, Text, ForeignKey, UniqueConstraint
)
from sqlalchemy.sql import func
from api.database import PublicBase
import uuid


def new_uuid() -> str:
    return str(uuid.uuid4())


class UserRepository(PublicBase):
    """Per-user namespace — like a GitHub account. One per user."""
    __tablename__ = "user_repositories"

    id = Column(String, primary_key=True, default=new_uuid)
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    namespace = Column(String, unique=True, nullable=False, index=True)  # @username
    bio = Column(Text, nullable=True)
    website = Column(String, nullable=True)
    total_contracts = Column(Integer, default=0)
    total_public = Column(Integer, default=0)
    storage_used_bytes = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())


class ContractRepo(PublicBase):
    """Each uploaded contract — like a GitHub repository."""
    __tablename__ = "contract_repos"
    __table_args__ = (
        UniqueConstraint("repo_id", "slug", name="uq_repo_slug"),
    )

    id = Column(String, primary_key=True, default=new_uuid)
    repo_id = Column(String, ForeignKey("user_repositories.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, unique=True, index=True)  # username/contract-name
    chain = Column(String, nullable=False, default="ethereum", index=True)
    language = Column(String, nullable=False, default="solidity")  # solidity | vyper | rust | move
    address = Column(String, nullable=True)  # deployed contract address
    version = Column(String, nullable=True, default="1.0.0")
    description = Column(Text, nullable=True)
    tags = Column(Text, nullable=True)  # JSON array: ["defi", "token", "erc20"]

    # Visibility
    is_public = Column(Boolean, default=False, index=True)  # toggle → makes SDK visible to GROOT
    is_verified = Column(Boolean, default=False)  # admin-verified trust signal

    # Content — PRIVATE: GROOT NEVER reads these columns
    source_code = Column(Text, nullable=True)  # full source (.sol, .vy, .rs)
    source_hash = Column(String, nullable=True)  # SHA256 of source

    # Parsed data
    abi_json = Column(Text, nullable=True)  # full ABI JSON
    abi_hash = Column(String, nullable=True)  # SHA256 of ABI

    # Status
    status = Column(String, default="draft", index=True)  # draft | parsed | published | archived
    parse_errors = Column(Text, nullable=True)  # JSON array of parsing issues

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())


class ContractFunction(PublicBase):
    """Parsed function from ABI — the SDK building blocks."""
    __tablename__ = "contract_functions"

    id = Column(String, primary_key=True, default=new_uuid)
    contract_id = Column(String, ForeignKey("contract_repos.id"), nullable=False, index=True)
    function_name = Column(String, nullable=False)
    function_type = Column(String, nullable=False, default="function")  # function | constructor | fallback | receive
    selector = Column(String, nullable=True)  # 4-byte hex: 0xabcdef12
    signature = Column(String, nullable=True)  # transfer(address,uint256)

    # Access classification
    visibility = Column(String, nullable=False, default="public")  # public | external | internal | private
    state_mutability = Column(String, nullable=False, default="nonpayable")  # pure | view | nonpayable | payable
    access_level = Column(String, nullable=False, default="public")  # public | owner | admin | role_based | unknown
    access_modifier = Column(String, nullable=True)  # onlyOwner | onlyRole(ADMIN_ROLE) | null
    access_roles = Column(Text, nullable=True)  # JSON array of detected roles

    # Parameters
    inputs = Column(Text, nullable=True)  # JSON array: [{"name":"to","type":"address"}]
    outputs = Column(Text, nullable=True)  # JSON array: [{"name":"","type":"bool"}]

    # SDK flags
    is_sdk_enabled = Column(Boolean, default=True)  # user can disable individual functions
    is_dangerous = Column(Boolean, default=False)  # flagged as potentially dangerous
    danger_reason = Column(String, nullable=True)

    # Metadata
    gas_estimate = Column(String, nullable=True)
    natspec_notice = Column(Text, nullable=True)  # @notice from NatSpec
    natspec_dev = Column(Text, nullable=True)  # @dev from NatSpec

    created_at = Column(DateTime, server_default=func.now())


class ContractEvent(PublicBase):
    """Parsed event from ABI."""
    __tablename__ = "contract_events"

    id = Column(String, primary_key=True, default=new_uuid)
    contract_id = Column(String, ForeignKey("contract_repos.id"), nullable=False, index=True)
    event_name = Column(String, nullable=False)
    signature = Column(String, nullable=True)  # Transfer(address,address,uint256)
    topic_hash = Column(String, nullable=True)  # keccak256 of signature
    inputs = Column(Text, nullable=True)  # JSON array with indexed flag
    is_sdk_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class SDKDefinition(PublicBase):
    """Generated SDK JSON — this is what GROOT reads and MCP exposes."""
    __tablename__ = "sdk_definitions"

    id = Column(String, primary_key=True, default=new_uuid)
    contract_id = Column(String, ForeignKey("contract_repos.id"), nullable=False, unique=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    sdk_version = Column(String, nullable=False, default="1.0.0")
    sdk_json = Column(Text, nullable=False)  # complete SDK definition
    sdk_hash = Column(String, nullable=False)  # SHA256 for integrity
    is_public = Column(Boolean, default=False, index=True)  # mirrors contract_repos.is_public
    chain = Column(String, nullable=False)
    contract_address = Column(String, nullable=True)
    generated_at = Column(DateTime, server_default=func.now())
