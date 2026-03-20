"""
REFINET Cloud — Chain & Deployment Models
Dynamic EVM chain registry and multi-chain contract deployment tracking.
"""

from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from api.database import PublicBase
import uuid


def new_uuid() -> str:
    return str(uuid.uuid4())


class SupportedChain(PublicBase):
    """
    Dynamic EVM chain registry. Replaces all hardcoded chain dicts.
    Admin can add new chains via dashboard or chainlist.org import.
    """
    __tablename__ = "supported_chains"

    chain_id = Column(Integer, primary_key=True)            # EIP-155 chain ID (1, 137, 8453, etc.)
    name = Column(String, nullable=False)                    # "Ethereum Mainnet", "Base", etc.
    short_name = Column(String, nullable=False, unique=True, index=True)  # "ethereum", "base", etc.
    currency = Column(String, default="ETH")                 # Native currency symbol
    rpc_url = Column(String, nullable=False)                 # Primary RPC endpoint
    explorer_url = Column(String, nullable=True)             # Block explorer URL (e.g., https://etherscan.io)
    explorer_api_url = Column(String, nullable=True)         # Explorer API (e.g., https://api.etherscan.io/api)
    icon_url = Column(String, nullable=True)                 # Chain logo URL
    is_testnet = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True, index=True)
    added_by = Column(String, nullable=True)                 # User ID or "system"
    created_at = Column(DateTime, server_default=func.now())


class ContractDeployment(PublicBase):
    """
    Maps a chain-agnostic contract to its on-chain deployment addresses.
    One contract can be deployed on many chains (USDC on ETH, Base, Polygon, etc.).
    """
    __tablename__ = "contract_deployments"
    __table_args__ = (
        UniqueConstraint("chain_id", "address", name="uq_chain_address"),
    )

    id = Column(String, primary_key=True, default=new_uuid)
    contract_id = Column(String, ForeignKey("contract_repos.id", ondelete="CASCADE"), nullable=False, index=True)
    chain_id = Column(Integer, ForeignKey("supported_chains.chain_id"), nullable=False, index=True)
    address = Column(String, nullable=False, index=True)     # Deployed contract address on this chain
    is_verified = Column(Boolean, default=False)              # Verified on block explorer
    deployed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
