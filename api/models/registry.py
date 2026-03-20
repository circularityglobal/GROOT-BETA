"""
REFINET Cloud — Registry Models
GitHub-style registry for smart contract ABIs, SDKs, and execution logic.
All tables in public.db (user-facing data).
"""

from sqlalchemy import (
    Column, String, Boolean, Integer, DateTime, Text, ForeignKey, UniqueConstraint
)
from sqlalchemy.sql import func
from api.database import PublicBase
import uuid


def new_uuid() -> str:
    return str(uuid.uuid4())


class RegistryProject(PublicBase):
    """Top-level registry container — like a GitHub repository."""
    __tablename__ = "registry_projects"

    id = Column(String, primary_key=True, default=new_uuid)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    slug = Column(String, unique=True, nullable=False, index=True)  # username/project-name
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    readme = Column(Text, nullable=True)  # Markdown content
    visibility = Column(String, default="public", index=True)  # public | private | platform
    category = Column(String, default="utility", index=True)  # defi | token | governance | bridge | utility | oracle | nft | dao | sdk | library
    chain = Column(String, default="ethereum", index=True)  # ethereum | base | arbitrum | polygon | solana | multi-chain
    tags = Column(Text, nullable=True)  # JSON array
    license = Column(String, nullable=True)
    website_url = Column(String, nullable=True)
    repo_url = Column(String, nullable=True)
    logo_url = Column(String, nullable=True)
    stars_count = Column(Integer, default=0)
    forks_count = Column(Integer, default=0)
    watchers_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())


class RegistryABI(PublicBase):
    """Contract ABI entry within a registry project."""
    __tablename__ = "registry_abis"

    id = Column(String, primary_key=True, default=new_uuid)
    project_id = Column(String, ForeignKey("registry_projects.id"), nullable=False, index=True)
    contract_name = Column(String, nullable=False)  # e.g. "StakingPool"
    contract_address = Column(String, nullable=True)
    chain = Column(String, nullable=False)
    abi_json = Column(Text, nullable=False)  # Full ABI JSON
    compiler_version = Column(String, nullable=True)
    optimization_enabled = Column(Boolean, default=False)
    source_hash = Column(String, nullable=True)  # SHA256 for verification
    bytecode_hash = Column(String, nullable=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())


class RegistrySDK(PublicBase):
    """SDK definition within a registry project."""
    __tablename__ = "registry_sdks"

    id = Column(String, primary_key=True, default=new_uuid)
    project_id = Column(String, ForeignKey("registry_projects.id"), nullable=False, index=True)
    name = Column(String, nullable=False)  # e.g. "python-sdk", "typescript-sdk"
    language = Column(String, nullable=False)  # solidity | vyper | rust | typescript | python
    version = Column(String, nullable=False)
    package_name = Column(String, nullable=True)  # npm/pypi package name
    install_command = Column(String, nullable=True)  # e.g. "npm install @refinet/staking"
    reference_url = Column(String, nullable=True)
    documentation = Column(Text, nullable=True)  # Markdown
    code_samples = Column(Text, nullable=True)  # JSON array of {title, language, code}
    readme_content = Column(Text, nullable=True)  # Markdown
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())


class ExecutionLogic(PublicBase):
    """
    Core execution logic entries — functions, workflows, scripts, hooks, triggers
    that define how to interact with smart contracts.
    """
    __tablename__ = "execution_logic"

    id = Column(String, primary_key=True, default=new_uuid)
    project_id = Column(String, ForeignKey("registry_projects.id"), nullable=False, index=True)
    abi_id = Column(String, ForeignKey("registry_abis.id"), nullable=True)  # links to specific ABI
    name = Column(String, nullable=False)  # e.g. "stake", "unstake", "claim"
    version = Column(String, nullable=True)
    logic_type = Column(String, nullable=False)  # function | workflow | script | hook | trigger
    description = Column(Text, nullable=True)
    function_signature = Column(String, nullable=True)  # e.g. "stake(uint256)"
    input_schema = Column(Text, nullable=True)  # JSON Schema for parameters
    output_schema = Column(Text, nullable=True)  # JSON Schema for return values
    code_reference = Column(Text, nullable=True)  # pointer to source code
    chain = Column(String, nullable=True)
    gas_estimate = Column(Integer, nullable=True)
    is_read_only = Column(Boolean, default=False)
    preconditions = Column(Text, nullable=True)  # JSON array of checks
    is_verified = Column(Boolean, default=False)
    verified_by = Column(String, nullable=True)
    execution_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())


class ContractSecurityFlag(PublicBase):
    """Security flag detected during ABI analysis."""
    __tablename__ = "contract_security_flags"

    id = Column(String, primary_key=True, default=new_uuid)
    abi_id = Column(String, ForeignKey("registry_abis.id", ondelete="CASCADE"), nullable=False, index=True)
    pattern = Column(String, nullable=False)  # delegatecall | selfdestruct | CLEAN | etc.
    severity = Column(String, nullable=False)  # CRITICAL | HIGH | MEDIUM | LOW | NONE
    location = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    risk = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class RegistryStar(PublicBase):
    """User star (like) on a registry project."""
    __tablename__ = "registry_stars"
    __table_args__ = (
        UniqueConstraint("user_id", "project_id", name="uq_star_user_project"),
    )

    id = Column(String, primary_key=True, default=new_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    project_id = Column(String, ForeignKey("registry_projects.id"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())


class RegistryFork(PublicBase):
    """Fork record linking source and forked projects."""
    __tablename__ = "registry_forks"
    __table_args__ = (
        UniqueConstraint("source_project_id", "forked_by", name="uq_fork_source_user"),
    )

    id = Column(String, primary_key=True, default=new_uuid)
    source_project_id = Column(String, ForeignKey("registry_projects.id"), nullable=False, index=True)
    forked_project_id = Column(String, ForeignKey("registry_projects.id"), nullable=False, index=True)
    forked_by = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())
