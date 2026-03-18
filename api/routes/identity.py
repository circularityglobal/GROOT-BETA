"""
REFINET Cloud — Identity Resolution Routes
ENS resolution, pseudo-IP lookup, network topology, and peer discovery.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from web3 import Web3

from api.database import public_db_dependency
from api.auth.jwt import decode_access_token
from api.auth.ens import (
    resolve_ens_name,
    resolve_ens_reverse,
    resolve_ens_profile,
    get_cache_stats,
)
from api.auth.network_identity import (
    compute_network_address,
    lookup_by_pseudo_ip,
    get_chain_peers,
    get_chain_subnets,
    get_peer_count,
    get_reverse_index_size,
)
from api.auth.chains import get_chain, is_supported_chain
from api.auth.wallet_identity import (
    lookup_identity_by_address,
    refresh_ens_for_user,
)
from api.models.public import User
from api.schemas.auth import (
    ENSResolveRequest,
    ENSProfileResponse,
    NetworkAddressResponse,
    NetworkLookupResponse,
    NetworkTopologyResponse,
    ChainSubnetResponse,
    ChainPeersResponse,
    PeerResponse,
    WalletIdentityResponse,
)

router = APIRouter(prefix="/identity", tags=["identity"])


# ── Helpers ──────────────────────────────────────────────────────────

def _get_current_user(request: Request, db: Session) -> tuple[dict, User]:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    try:
        payload = decode_access_token(auth_header[7:])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return payload, user


def _identity_to_response(identity) -> WalletIdentityResponse:
    return WalletIdentityResponse(
        id=identity.id,
        eth_address=identity.eth_address,
        chain_id=identity.chain_id,
        chain_name=identity.chain_name,
        is_primary=identity.is_primary,
        pseudo_ipv6=identity.pseudo_ipv6,
        subnet_prefix=identity.subnet_prefix,
        interface_id=identity.interface_id,
        ens_name=identity.ens_name,
        ens_avatar=identity.ens_avatar,
        ens_description=identity.ens_description,
        ens_url=identity.ens_url,
        ens_twitter=identity.ens_twitter,
        ens_github=identity.ens_github,
        ens_email=identity.ens_email,
        ens_resolved_at=identity.ens_resolved_at,
        display_name=identity.display_name,
        email_alias=identity.email_alias,
        public_key=identity.public_key,
        xmtp_enabled=identity.xmtp_enabled,
        verified_at=identity.verified_at,
        last_active_chain_at=identity.last_active_chain_at,
    )


# ── ENS Resolution ──────────────────────────────────────────────────

@router.post("/ens/resolve", response_model=ENSProfileResponse)
def ens_resolve(req: ENSResolveRequest):
    """
    Resolve an ENS name → address, or an address → ENS profile.
    Public endpoint — no auth required.
    """
    query = req.query.strip()

    # If it looks like an ENS name
    if query.endswith(".eth"):
        address = resolve_ens_name(query)
        if address:
            profile = resolve_ens_profile(address)
            return ENSProfileResponse(
                address=profile.address,
                name=profile.name,
                avatar=profile.avatar,
                description=profile.description,
                url=profile.url,
                twitter=profile.twitter,
                github=profile.github,
                email=profile.email,
                resolved=profile.resolved,
                error=profile.error,
            )
        return ENSProfileResponse(
            address="",
            resolved=False,
            error=f"ENS name '{query}' not found",
        )

    # If it looks like an address
    if query.startswith("0x") and len(query) == 42:
        try:
            checksummed = Web3.to_checksum_address(query)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid Ethereum address")

        profile = resolve_ens_profile(checksummed)
        return ENSProfileResponse(
            address=profile.address,
            name=profile.name,
            avatar=profile.avatar,
            description=profile.description,
            url=profile.url,
            twitter=profile.twitter,
            github=profile.github,
            email=profile.email,
            resolved=profile.resolved,
            error=profile.error,
        )

    raise HTTPException(status_code=400, detail="Query must be an ENS name (*.eth) or Ethereum address (0x...)")


@router.get("/ens/{name}", response_model=ENSProfileResponse)
def ens_lookup(name: str):
    """Resolve an ENS name to its full profile. Public endpoint."""
    if not name.endswith(".eth"):
        name = f"{name}.eth"

    address = resolve_ens_name(name)
    if not address:
        return ENSProfileResponse(address="", resolved=False, error=f"'{name}' not found")

    profile = resolve_ens_profile(address)
    return ENSProfileResponse(
        address=profile.address,
        name=profile.name,
        avatar=profile.avatar,
        description=profile.description,
        url=profile.url,
        twitter=profile.twitter,
        github=profile.github,
        email=profile.email,
        resolved=profile.resolved,
        error=profile.error,
    )


@router.post("/ens/refresh")
def ens_refresh_user(
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Force-refresh ENS data for the current user's identities."""
    _, user = _get_current_user(request, db)
    updated = refresh_ens_for_user(db, user.id)
    return {"updated": updated, "message": f"ENS data refreshed for {updated} identities."}


# ── Address Lookup ───────────────────────────────────────────────────

@router.get("/address/{eth_address}", response_model=list[WalletIdentityResponse])
def lookup_address(
    eth_address: str,
    db: Session = Depends(public_db_dependency),
):
    """
    Look up all registered identities for a wallet address.
    Public endpoint — returns identity data for any registered address.
    """
    try:
        checksummed = Web3.to_checksum_address(eth_address)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Ethereum address")

    identities = lookup_identity_by_address(db, checksummed)
    if not identities:
        raise HTTPException(status_code=404, detail="No identity found for this address")

    return [_identity_to_response(i) for i in identities]


# ── Network Topology (static routes BEFORE parameterized) ───────────

@router.get("/network/topology", response_model=NetworkTopologyResponse)
def get_topology():
    """
    Get the network topology: chain subnets and peer counts.
    Shows how wallets are distributed across chain subnets.
    """
    subnets_data = get_chain_subnets()
    total = sum(s["peer_count"] for s in subnets_data)
    return NetworkTopologyResponse(
        subnets=[ChainSubnetResponse(**s) for s in subnets_data],
        total_peers=total,
    )


@router.get("/network/peers/{chain_id}", response_model=ChainPeersResponse)
def get_chain_peer_list(chain_id: int):
    """
    Get all registered peers on a specific chain.
    Shows wallets that have authenticated on this chain.
    """
    if not is_supported_chain(chain_id):
        raise HTTPException(status_code=400, detail=f"Chain {chain_id} not supported")

    chain = get_chain(chain_id)
    from api.auth.network_identity import chain_to_subnet_prefix
    subnet = f"{chain_to_subnet_prefix(chain_id)}::/48"
    peers = get_chain_peers(chain_id)

    return ChainPeersResponse(
        chain_id=chain_id,
        chain_name=chain.name if chain else f"Chain {chain_id}",
        subnet_prefix=subnet,
        peers=[
            PeerResponse(
                eth_address=p.eth_address,
                pseudo_ipv6=p.pseudo_ipv6,
                chain_id=p.chain_id,
                chain_name=p.chain_name,
                subnet=p.subnet,
                display_name=p.display_name,
                ens_name=p.ens_name,
            )
            for p in peers
        ],
    )


@router.get("/network/lookup/{pseudo_ipv6:path}", response_model=NetworkLookupResponse)
def reverse_lookup_ip(pseudo_ipv6: str):
    """
    Reverse lookup: find the wallet address for a pseudo-IPv6.
    Only works for wallets that have authenticated (registered in routing table).
    """
    address = lookup_by_pseudo_ip(pseudo_ipv6)
    return NetworkLookupResponse(
        pseudo_ipv6=pseudo_ipv6,
        eth_address=address,
        found=address is not None,
    )


# ── Network Identity (parameterized — must come after static) ──────

@router.get("/network/{eth_address}", response_model=NetworkAddressResponse)
def get_network_address(eth_address: str, chain_id: int = 1):
    """
    Compute the network identity for any wallet address on a chain.
    Public endpoint — deterministic computation, no registration needed.
    """
    try:
        checksummed = Web3.to_checksum_address(eth_address)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Ethereum address")

    if not is_supported_chain(chain_id):
        raise HTTPException(status_code=400, detail=f"Chain {chain_id} not supported")

    net_addr = compute_network_address(checksummed, chain_id)
    return NetworkAddressResponse(
        eth_address=net_addr.eth_address,
        chain_id=net_addr.chain_id,
        pseudo_ipv6=net_addr.pseudo_ipv6,
        subnet_prefix=net_addr.subnet_prefix,
        interface_id=net_addr.interface_id,
        cidr=net_addr.cidr,
    )


# ── Status ──────────────────────────────────────────────────────────

@router.get("/status")
def identity_status():
    """Identity system status: ENS cache stats, peer counts, reverse index size."""
    ens_cache = get_cache_stats()
    peer_counts = get_peer_count()
    return {
        "ens_cache": ens_cache,
        "peer_counts": peer_counts,
        "reverse_index_size": get_reverse_index_size(),
        "total_peers": sum(peer_counts.values()),
    }
