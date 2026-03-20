"""
REFINET Cloud — Auth Routes
SIWE-first authentication with multi-chain support.
Password and TOTP are optional profile settings.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from api.database import public_db_dependency, internal_db_dependency
from api.models.public import User
from api.auth.password import (
    hash_password, verify_password, generate_salt,
    derive_user_key, compute_eth_address_hash,
)
from api.auth.totp import (
    generate_totp_secret, generate_qr_code, verify_totp,
    encrypt_totp_secret, decrypt_totp_secret,
)
from api.auth.siwe import create_nonce, build_siwe_message, verify_siwe_signature
from api.auth.jwt import (
    create_access_token, decode_access_token, verify_scope,
    create_refresh_token, rotate_refresh_token, revoke_all_refresh_tokens,
    FULL_USER_SCOPES,
)
from api.auth.chains import (
    get_chain, get_chains_summary, get_supported_chain_ids,
    is_supported_chain, DEFAULT_CHAIN_ID,
)
from api.auth.wallet_identity import (
    get_or_create_wallet_identity,
    get_user_identities,
    get_primary_identity,
    create_wallet_session,
    get_active_sessions,
    revoke_session,
)
from api.schemas.auth import (
    SIWENonceResponse, SIWEVerifyRequest, SIWEVerifyResponse,
    RefreshRequest, RefreshResponse, UserProfile,
    SetPasswordRequest, SetPasswordResponse,
    PasswordLoginRequest, PasswordLoginResponse,
    TOTPSetupResponse, TOTPVerifyRequest, TOTPVerifyResponse,
    UpdateProfileRequest,
    CreateWalletRequest, CreateWalletResponse, CustodialLoginRequest,
    WalletIdentityResponse, WalletIdentityListResponse, UpdateIdentityRequest,
    WalletSessionResponse, WalletSessionListResponse,
    SupportedChainsResponse, ChainInfoResponse,
)
from api.services.wallet_service import (
    create_custodial_wallet, sign_message_with_custodial_wallet,
)
from web3 import Web3
from api.config import get_settings
from api.middleware.rate_limit import limiter
import uuid
import json

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Helpers ─────────────────────────────────────────────────────────

def _get_current_user(request: Request, db: Session) -> tuple[dict, User]:
    """Extract JWT from Authorization header and load user."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    token = auth_header[7:]
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return payload, user


def _generate_username_from_address(eth_address: str) -> str:
    """Generate a username from an Ethereum address: e.g. '0xAbC1...7f9D'."""
    return f"{eth_address[:6]}...{eth_address[-4:]}"


def _identity_to_response(identity) -> WalletIdentityResponse:
    """Convert a WalletIdentity model to a response schema."""
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


# ── Supported Chains ────────────────────────────────────────────────

@router.get("/chains", response_model=SupportedChainsResponse)
def list_supported_chains():
    """List all supported EVM chains for SIWE authentication."""
    chains_data = get_chains_summary()
    return SupportedChainsResponse(
        chains=[ChainInfoResponse(**c) for c in chains_data],
        default_chain_id=DEFAULT_CHAIN_ID,
    )


# ── SIWE (Primary Auth — Multi-Chain) ───────────────────────────────

@router.get("/siwe/nonce", response_model=SIWENonceResponse)
@limiter.limit("10/minute")
def siwe_get_nonce(request: Request, db: Session = Depends(public_db_dependency)):
    """
    Get a nonce for SIWE signing. Public endpoint — no auth required.
    Returns supported chains so the frontend can offer a chain selector.
    """
    nonce_data = create_nonce(db)
    settings = get_settings()

    return SIWENonceResponse(
        nonce=nonce_data["nonce"],
        expires_at=nonce_data["expires_at"],
        message_template=(
            f"{settings.siwe_domain} wants you to sign in with your "
            f"Ethereum account:\n{{address}}\n\n{settings.siwe_statement}"
        ),
        supported_chains=get_chains_summary(),
    )


@router.post("/siwe/verify", response_model=SIWEVerifyResponse)
@limiter.limit("10/minute")
def siwe_verify(
    req: SIWEVerifyRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """
    Verify SIWE signature. Creates account if wallet is new.
    Supports multi-chain — chain_id is extracted from the signed message.
    Creates a WalletIdentity record and tracks the login session.
    """
    try:
        result = verify_siwe_signature(db, req.message, req.signature, req.nonce)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signature verification error: {e}")

    eth_address = result["address"]
    chain_id = result.get("chain_id", req.chain_id)
    chain = get_chain(chain_id)
    chain_name = chain.name if chain else f"Chain {chain_id}"
    is_new_user = False

    # Look up existing user by eth_address
    try:
        user = db.query(User).filter(User.eth_address == eth_address).first()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    if not user:
        # Auto-create account for new wallet
        is_new_user = True
        user = User(
            id=str(uuid.uuid4()),
            username=_generate_username_from_address(eth_address),
            eth_address=eth_address,
            eth_address_hash=compute_eth_address_hash(eth_address),
            siwe_enabled=True,
            is_active=True,
            auth_layer_3_complete=True,
            primary_chain_id=chain_id,
        )
        db.add(user)

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    user.last_login_at = datetime.now(timezone.utc)
    db.flush()  # Single flush for user creation + login timestamp

    # Create or update wallet identity — ENS deferred to background thread
    identity = get_or_create_wallet_identity(
        db, user.id, eth_address, chain_id,
        is_primary=(is_new_user or chain_id == user.primary_chain_id),
        skip_ens=True,
    )

    # Track login session
    ip = request.client.host if request.client else None
    ua = request.headers.get("User-Agent")
    create_wallet_session(
        db, user.id, eth_address, chain_id,
        wallet_identity_id=identity.id,
        ip_address=ip, user_agent=ua,
    )

    # Issue full JWT + refresh token
    access_token = create_access_token(user.id, FULL_USER_SCOPES)
    refresh_token, _ = create_refresh_token(db, user.id)

    return SIWEVerifyResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        eth_address=eth_address,
        chain_id=chain_id,
        chain_name=chain_name,
        is_new_user=is_new_user,
        message="Welcome!" if is_new_user else "Signed in.",
        identity=_identity_to_response(identity),
    )


# ── Token Refresh ──────────────────────────────────────────────────

@router.post("/token/refresh", response_model=RefreshResponse)
@limiter.limit("10/minute")
def refresh(req: RefreshRequest, request: Request, db: Session = Depends(public_db_dependency)):
    try:
        access, refresh_tok, expires = rotate_refresh_token(db, req.refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    return RefreshResponse(
        access_token=access,
        refresh_token=refresh_tok,
        expires_at=expires.isoformat(),
    )


# ── Logout ─────────────────────────────────────────────────────────

@router.post("/logout")
def logout(request: Request, db: Session = Depends(public_db_dependency)):
    payload, user = _get_current_user(request, db)
    count = revoke_all_refresh_tokens(db, user.id)
    return {"message": f"Logged out. {count} refresh tokens revoked."}


# ── Profile ────────────────────────────────────────────────────────

@router.get("/me", response_model=UserProfile)
def get_me(request: Request, db: Session = Depends(public_db_dependency)):
    payload, user = _get_current_user(request, db)

    # Load wallet identities
    identities = get_user_identities(db, user.id)
    identity_responses = [_identity_to_response(i) for i in identities]

    return UserProfile(
        id=user.id,
        username=user.username,
        tier=user.tier,
        eth_address=user.eth_address,
        email=user.email,
        primary_chain_id=user.primary_chain_id or 1,
        password_enabled=bool(user.hashed_password),
        totp_enabled=user.totp_enabled,
        is_custodial_wallet=user.is_custodial_wallet or False,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        identities=identity_responses,
    )


@router.put("/me", response_model=UserProfile)
def update_profile(
    req: UpdateProfileRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Update username or email."""
    payload, user = _get_current_user(request, db)

    if req.username:
        existing = db.query(User).filter(
            User.username == req.username, User.id != user.id
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Username already taken")
        user.username = req.username

    if req.email:
        existing = db.query(User).filter(
            User.email == req.email, User.id != user.id
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")
        user.email = req.email

    db.flush()

    identities = get_user_identities(db, user.id)
    identity_responses = [_identity_to_response(i) for i in identities]

    return UserProfile(
        id=user.id,
        username=user.username,
        tier=user.tier,
        eth_address=user.eth_address,
        email=user.email,
        primary_chain_id=user.primary_chain_id or 1,
        password_enabled=bool(user.hashed_password),
        totp_enabled=user.totp_enabled,
        is_custodial_wallet=user.is_custodial_wallet or False,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        identities=identity_responses,
    )


# ── Wallet Identity Management ────────────────────────────────────

@router.get("/identity", response_model=WalletIdentityListResponse)
def list_identities(request: Request, db: Session = Depends(public_db_dependency)):
    """List all wallet identities across chains for the current user."""
    payload, user = _get_current_user(request, db)
    identities = get_user_identities(db, user.id)
    return WalletIdentityListResponse(
        identities=[_identity_to_response(i) for i in identities],
        primary_chain_id=user.primary_chain_id or 1,
    )


@router.put("/identity/{identity_id}", response_model=WalletIdentityResponse)
def update_identity(
    identity_id: str,
    req: UpdateIdentityRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Update display name or messaging permissions for a wallet identity."""
    payload, user = _get_current_user(request, db)

    from api.models.public import WalletIdentity
    identity = db.query(WalletIdentity).filter(
        WalletIdentity.id == identity_id,
        WalletIdentity.user_id == user.id,
    ).first()

    if not identity:
        raise HTTPException(status_code=404, detail="Identity not found")

    if req.display_name is not None:
        identity.display_name = req.display_name
    if req.messaging_permissions is not None:
        identity.messaging_permissions = json.dumps(req.messaging_permissions)

    db.flush()
    return _identity_to_response(identity)


# ── Wallet Sessions ───────────────────────────────────────────────

@router.get("/sessions", response_model=WalletSessionListResponse)
def list_sessions(request: Request, db: Session = Depends(public_db_dependency)):
    """List all active login sessions for the current user."""
    payload, user = _get_current_user(request, db)
    sessions = get_active_sessions(db, user.id)
    return WalletSessionListResponse(
        sessions=[
            WalletSessionResponse(
                id=s.id,
                chain_id=s.chain_id,
                eth_address=s.eth_address,
                device_label=s.device_label,
                ip_address=s.ip_address,
                is_active=s.is_active,
                created_at=s.created_at,
            )
            for s in sessions
        ]
    )


@router.delete("/sessions/{session_id}")
def revoke_session_endpoint(
    session_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Revoke a specific login session."""
    payload, user = _get_current_user(request, db)
    if not revoke_session(db, session_id, user.id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session revoked."}


# ── Profile Settings: Password (Optional) ─────────────────────────

@router.post("/settings/password", response_model=SetPasswordResponse)
def set_password(
    req: SetPasswordRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """
    Set email + password for the account. Optional — adds password login
    as an alternative to SIWE. Requires active SIWE session.
    """
    payload, user = _get_current_user(request, db)

    # Check email uniqueness
    if req.email != user.email:
        existing = db.query(User).filter(
            User.email == req.email, User.id != user.id
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")

    email_salt = user.email_salt or generate_salt()
    hashed = hash_password(req.password, email_salt)

    user.email = req.email
    user.email_salt = email_salt
    user.hashed_password = hashed
    user.auth_layer_1_complete = True

    if req.username:
        existing = db.query(User).filter(
            User.username == req.username, User.id != user.id
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Username already taken")
        user.username = req.username

    db.flush()

    return SetPasswordResponse(
        email=user.email,
        username=user.username,
    )


@router.post("/login", response_model=PasswordLoginResponse)
@limiter.limit("5/minute")
def password_login(
    req: PasswordLoginRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """
    Log in with email + password. Only works if user has set up a password.
    If TOTP is enabled, returns a partial token requiring TOTP verification.
    """
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not user.is_active or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(req.password, user.email_salt, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user.last_login_at = datetime.now(timezone.utc)

    if user.totp_enabled:
        # Issue limited token — user must verify TOTP to get full access
        token = create_access_token(user.id, ["auth:totp_pending"])
        return PasswordLoginResponse(
            access_token=token,
            refresh_token="",
            requires_totp=True,
            message="Password verified. Enter TOTP code to complete login.",
        )

    # No TOTP — issue full access
    access_token = create_access_token(user.id, FULL_USER_SCOPES)
    refresh_token, _ = create_refresh_token(db, user.id)

    return PasswordLoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        message="Signed in with password.",
    )


@router.post("/login/totp", response_model=PasswordLoginResponse)
def totp_login(
    req: TOTPVerifyRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Complete password login by verifying TOTP code."""
    payload, user = _get_current_user(request, db)

    if not verify_scope(payload, "auth:totp_pending"):
        raise HTTPException(status_code=403, detail="Requires pending TOTP verification")

    if not user.totp_enabled or not user.totp_secret:
        raise HTTPException(status_code=400, detail="TOTP not enabled")

    secret = user.totp_secret
    if user.eth_address:
        server_key = derive_user_key("", user.email_salt, user.eth_address)
        try:
            secret = decrypt_totp_secret(secret, server_key)
        except Exception:
            pass

    if not verify_totp(secret, req.code):
        raise HTTPException(status_code=401, detail="Invalid TOTP code")

    access_token = create_access_token(user.id, FULL_USER_SCOPES)
    refresh_token, _ = create_refresh_token(db, user.id)

    return PasswordLoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        message="Signed in with password + TOTP.",
    )


# ── Profile Settings: TOTP (Optional) ─────────────────────────────

@router.post("/settings/totp/setup", response_model=TOTPSetupResponse)
def totp_setup(request: Request, db: Session = Depends(public_db_dependency)):
    """Set up TOTP 2FA. Optional — adds extra security to password login."""
    payload, user = _get_current_user(request, db)

    if user.totp_enabled:
        raise HTTPException(status_code=400, detail="TOTP already enabled")

    secret = generate_totp_secret()
    issuer_email = user.email or user.eth_address
    qr_base64 = generate_qr_code(secret, issuer_email)

    # Store temporarily unencrypted — encrypted on verify
    user.totp_secret = secret
    db.flush()

    return TOTPSetupResponse(
        qr_code_base64=qr_base64,
        manual_entry_key=secret,
    )


@router.post("/settings/totp/verify", response_model=TOTPVerifyResponse)
def totp_verify_setup(
    req: TOTPVerifyRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Verify TOTP code to enable 2FA."""
    payload, user = _get_current_user(request, db)

    if not user.totp_secret:
        raise HTTPException(status_code=400, detail="Call /settings/totp/setup first")

    if not verify_totp(user.totp_secret, req.code):
        raise HTTPException(status_code=401, detail="Invalid TOTP code")

    user.totp_enabled = True
    user.auth_layer_2_complete = True

    # Encrypt the TOTP secret if we have an eth_address
    if user.eth_address:
        try:
            user_key = derive_user_key("", user.email_salt or "", user.eth_address)
            user.totp_secret = encrypt_totp_secret(user.totp_secret, user_key)
        except Exception:
            pass

    db.flush()

    return TOTPVerifyResponse(
        totp_enabled=True,
        message="TOTP enabled. Password logins will now require a TOTP code.",
    )


@router.delete("/settings/totp", response_model=TOTPVerifyResponse)
def totp_disable(
    req: TOTPVerifyRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Disable TOTP 2FA. Requires current TOTP code for verification."""
    payload, user = _get_current_user(request, db)

    if not user.totp_enabled or not user.totp_secret:
        raise HTTPException(status_code=400, detail="TOTP not enabled")

    secret = user.totp_secret
    if user.eth_address:
        server_key = derive_user_key("", user.email_salt or "", user.eth_address)
        try:
            secret = decrypt_totp_secret(secret, server_key)
        except Exception:
            pass

    if not verify_totp(secret, req.code):
        raise HTTPException(status_code=401, detail="Invalid TOTP code")

    user.totp_enabled = False
    user.totp_secret = None
    user.auth_layer_2_complete = False
    db.flush()

    return TOTPVerifyResponse(
        totp_enabled=False,
        message="TOTP disabled.",
    )


# ── Custodial Wallet (Server-Managed, SSS-Secured) ────────────────

@router.post("/wallet/create", response_model=CreateWalletResponse)
def wallet_create(
    req: CreateWalletRequest,
    request: Request,
    pub_db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """
    Create a free custodial EVM wallet secured with Shamir Secret Sharing.
    Supports multi-chain — specify chain_id for the primary chain.
    """
    # Validate chain
    if not is_supported_chain(req.chain_id):
        raise HTTPException(
            status_code=400,
            detail=f"Chain ID {req.chain_id} is not supported. Use GET /auth/chains for supported chains.",
        )

    ip = request.client.host if request.client else None
    ua = request.headers.get("User-Agent")

    user_id = str(uuid.uuid4())

    try:
        wallet_result = create_custodial_wallet(
            internal_db=int_db,
            user_id=user_id,
            chain_id=req.chain_id,
            ip_address=ip,
            user_agent=ua,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    eth_address = wallet_result["eth_address"]

    # Create user record
    user = User(
        id=user_id,
        username=_generate_username_from_address(eth_address),
        eth_address=eth_address,
        eth_address_hash=compute_eth_address_hash(eth_address),
        siwe_enabled=True,
        is_active=True,
        auth_layer_3_complete=True,
        is_custodial_wallet=True,
        primary_chain_id=req.chain_id,
    )
    pub_db.add(user)
    pub_db.flush()

    # Create wallet identity
    identity = get_or_create_wallet_identity(
        pub_db, user_id, eth_address, req.chain_id, is_primary=True,
    )

    # Server-side SIWE authentication
    nonce_data = create_nonce(pub_db)
    message = build_siwe_message(eth_address, nonce_data["nonce"], req.chain_id)

    try:
        signature = sign_message_with_custodial_wallet(
            internal_db=int_db,
            user_id=user_id,
            message=message,
            ip_address=ip,
            user_agent=ua,
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Wallet signing failed: {e}")

    try:
        verify_siwe_signature(pub_db, message, signature, nonce_data["nonce"])
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"SIWE verification failed: {e}")

    # Track session
    create_wallet_session(
        pub_db, user_id, eth_address, req.chain_id,
        wallet_identity_id=identity.id,
        ip_address=ip, user_agent=ua,
    )

    user.last_login_at = datetime.now(timezone.utc)
    pub_db.flush()

    access_token = create_access_token(user_id, FULL_USER_SCOPES)
    refresh_token, _ = create_refresh_token(pub_db, user_id)

    chain = get_chain(req.chain_id)
    return CreateWalletResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        eth_address=eth_address,
        is_new_user=True,
        is_custodial=True,
        chain_id=req.chain_id,
        message=f"Wallet created on {chain.name if chain else 'Chain ' + str(req.chain_id)}. Welcome to REFINET Cloud!",
    )


@router.post("/wallet/siwe", response_model=SIWEVerifyResponse)
def custodial_siwe_login(
    req: CustodialLoginRequest,
    request: Request,
    pub_db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """
    Sign in with a custodial wallet. No browser wallet needed —
    the server signs the SIWE message on behalf of the user.
    """
    ip = request.client.host if request.client else None
    ua = request.headers.get("User-Agent")

    try:
        eth_address = Web3.to_checksum_address(req.eth_address)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Ethereum address")

    user = pub_db.query(User).filter(User.eth_address == eth_address).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_custodial_wallet:
        raise HTTPException(
            status_code=400,
            detail="This wallet is not custodial. Use SIWE with your browser wallet.",
        )

    chain_id = user.primary_chain_id or DEFAULT_CHAIN_ID

    nonce_data = create_nonce(pub_db)
    message = build_siwe_message(eth_address, nonce_data["nonce"], chain_id)

    try:
        signature = sign_message_with_custodial_wallet(
            internal_db=int_db,
            user_id=user.id,
            message=message,
            ip_address=ip,
            user_agent=ua,
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Wallet signing failed: {e}")

    try:
        verify_siwe_signature(pub_db, message, signature, nonce_data["nonce"])
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"SIWE verification failed: {e}")

    user.last_login_at = datetime.now(timezone.utc)
    pub_db.flush()

    # Update identity + track session
    identity = get_or_create_wallet_identity(
        pub_db, user.id, eth_address, chain_id, is_primary=True,
    )
    create_wallet_session(
        pub_db, user.id, eth_address, chain_id,
        wallet_identity_id=identity.id,
        ip_address=ip, user_agent=ua,
    )

    access_token = create_access_token(user.id, FULL_USER_SCOPES)
    refresh_token, _ = create_refresh_token(pub_db, user.id)

    chain = get_chain(chain_id)
    return SIWEVerifyResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        eth_address=eth_address,
        chain_id=chain_id,
        chain_name=chain.name if chain else f"Chain {chain_id}",
        is_new_user=False,
        message="Signed in with custodial wallet.",
        identity=_identity_to_response(identity),
    )
