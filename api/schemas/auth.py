"""REFINET Cloud — Auth Schemas (Multi-Chain + Wallet Identity + ENS + Network)"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


# ── SIWE (Primary Auth — Multi-Chain) ────────────────────────────────

class SIWENonceResponse(BaseModel):
    nonce: str
    expires_at: str
    message_template: str
    supported_chains: list[dict] = []


class SIWEVerifyRequest(BaseModel):
    message: str
    signature: str
    nonce: str
    chain_id: int = Field(default=1, ge=1)


class SIWEVerifyResponse(BaseModel):
    access_token: str
    refresh_token: str
    eth_address: str
    chain_id: int = 1
    chain_name: str = "Ethereum Mainnet"
    is_new_user: bool = False
    message: str
    identity: Optional["WalletIdentityResponse"] = None


# ── Token Refresh ──────────────────────────────────────────────────

class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_at: str


# ── Profile Settings (Optional Auth Layers) ───────────────────────

class SetPasswordRequest(BaseModel):
    email: EmailStr
    username: Optional[str] = Field(None, min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(min_length=12, max_length=128)


class SetPasswordResponse(BaseModel):
    email: str
    username: str
    password_enabled: bool = True
    message: str = "Password set. You can now also log in with email + password."


class PasswordLoginRequest(BaseModel):
    email: EmailStr
    password: str


class PasswordLoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    requires_totp: bool = False
    message: str


class TOTPSetupResponse(BaseModel):
    qr_code_base64: str
    manual_entry_key: str
    message: str = "Scan the QR code with your authenticator app."


class TOTPVerifyRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class TOTPVerifyResponse(BaseModel):
    totp_enabled: bool
    message: str


# ── User Profile (enhanced with identity) ─────────────────────────

class UserProfile(BaseModel):
    id: str
    username: str
    tier: str
    eth_address: Optional[str] = None
    email: Optional[str] = None
    primary_chain_id: int = 1
    password_enabled: bool = False
    totp_enabled: bool = False
    is_custodial_wallet: bool = False
    created_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    marketing_consent: bool = False
    onboarding_completed_at: Optional[datetime] = None
    # CIFI Federation
    cifi_verified: bool = False
    cifi_username: Optional[str] = None
    cifi_display_name: Optional[str] = None
    cifi_kyc_level: Optional[str] = None
    display_name: Optional[str] = None  # cifi_display_name if verified, else None
    identities: list["WalletIdentityResponse"] = []


class UpdateProfileRequest(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_-]+$")
    email: Optional[EmailStr] = None
    marketing_consent: Optional[bool] = None


# ── Wallet Identity ──────────────────────────────────────────────

class WalletIdentityResponse(BaseModel):
    id: str
    eth_address: str
    chain_id: int
    chain_name: str
    is_primary: bool = False
    # Network identity
    pseudo_ipv6: Optional[str] = None
    subnet_prefix: Optional[str] = None
    interface_id: Optional[str] = None
    # ENS
    ens_name: Optional[str] = None
    ens_avatar: Optional[str] = None
    ens_description: Optional[str] = None
    ens_url: Optional[str] = None
    ens_twitter: Optional[str] = None
    ens_github: Optional[str] = None
    ens_resolved_at: Optional[datetime] = None
    ens_email: Optional[str] = None
    # Display + messaging
    display_name: Optional[str] = None
    email_alias: Optional[str] = None
    public_key: Optional[str] = None
    xmtp_enabled: bool = False
    verified_at: Optional[datetime] = None
    last_active_chain_at: Optional[datetime] = None


class WalletIdentityListResponse(BaseModel):
    identities: list[WalletIdentityResponse]
    primary_chain_id: int = 1


class UpdateIdentityRequest(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=64)
    messaging_permissions: Optional[dict] = None


# ── Wallet Sessions ──────────────────────────────────────────────

class WalletSessionResponse(BaseModel):
    id: str
    chain_id: int
    eth_address: str
    device_label: Optional[str] = None
    ip_address: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None


class WalletSessionListResponse(BaseModel):
    sessions: list[WalletSessionResponse]


# ── Chain Info ───────────────────────────────────────────────────

class ChainInfoResponse(BaseModel):
    chain_id: int
    name: str
    short_name: str
    currency: str
    explorer_url: str
    is_testnet: bool = False


class SupportedChainsResponse(BaseModel):
    chains: list[ChainInfoResponse]
    default_chain_id: int = 1


# ── ENS Resolution ──────────────────────────────────────────────

class ENSResolveRequest(BaseModel):
    """Resolve an ENS name to an address, or an address to ENS."""
    query: str = Field(..., min_length=3, description="ENS name (e.g. 'vitalik.eth') or Ethereum address")


class ENSProfileResponse(BaseModel):
    address: str
    name: Optional[str] = None
    avatar: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    twitter: Optional[str] = None
    github: Optional[str] = None
    email: Optional[str] = None
    resolved: bool = False
    error: Optional[str] = None


# ── Network Identity ────────────────────────────────────────────

class NetworkAddressResponse(BaseModel):
    eth_address: str
    chain_id: int
    pseudo_ipv6: str
    subnet_prefix: str
    interface_id: str
    cidr: str


class NetworkLookupResponse(BaseModel):
    pseudo_ipv6: str
    eth_address: Optional[str] = None
    found: bool = False


class ChainSubnetResponse(BaseModel):
    chain_id: int
    chain_name: str
    subnet_prefix: str
    peer_count: int = 0


class NetworkTopologyResponse(BaseModel):
    subnets: list[ChainSubnetResponse]
    total_peers: int = 0


class PeerResponse(BaseModel):
    eth_address: str
    pseudo_ipv6: str
    chain_id: int
    chain_name: str
    subnet: str
    display_name: Optional[str] = None
    ens_name: Optional[str] = None


class ChainPeersResponse(BaseModel):
    chain_id: int
    chain_name: str
    subnet_prefix: str
    peers: list[PeerResponse]


# ── CIFI Federation ──────────────────────────────────────────────

class CIFIRegisterRequest(BaseModel):
    username: str = Field(
        ..., min_length=5, max_length=15,
        pattern=r"^[a-z0-9_-]+$",
        description="CIFI username (5-15 chars, lowercase alphanumeric, underscore, or hyphen)",
    )


class CIFIVerifyResponse(BaseModel):
    verified: bool
    registered: bool
    cifi_username: Optional[str] = None
    cifi_display_name: Optional[str] = None
    cifi_kyc_level: Optional[str] = None
    profile: Optional[UserProfile] = None


# ── Custodial Wallet ──────────────────────────────────────────────

class CreateWalletRequest(BaseModel):
    chain_id: int = Field(default=1, ge=1)


class CreateWalletResponse(BaseModel):
    access_token: str
    refresh_token: str
    eth_address: str
    is_new_user: bool = True
    is_custodial: bool = True
    chain_id: int = 1
    message: str


class CustodialLoginRequest(BaseModel):
    eth_address: str


# Forward ref resolution
SIWEVerifyResponse.model_rebuild()
UserProfile.model_rebuild()
