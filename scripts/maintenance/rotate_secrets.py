#!/usr/bin/env python3
"""
Rotate platform secrets (JWT keys, webhook signing keys).
Generates new cryptographically secure values and persists them to internal.db
encrypted with AES-256-GCM.

After running, the server must be restarted to pick up the new .env values.
The old secrets remain in the ServerSecret table (rotated_at updated) for audit.

Usage:
    python scripts/maintenance/rotate_secrets.py

Environment:
    SCRIPT_ARGS: JSON {"secrets": ["jwt", "webhook", "pepper"]}  (optional, defaults to all)
    INTERNAL_DB_ENCRYPTION_KEY: required for AES-256-GCM encryption
"""

import json
import os
import secrets
import sys
import uuid
import base64
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "rotate_secrets",
    "description": "Rotate platform secrets and persist encrypted values to internal.db",
    "category": "maintenance",
    "requires_admin": True,
}

# Secret definitions: name → (env_var, generator, description)
SECRET_DEFS = {
    "jwt": {
        "env_var": "SECRET_KEY",
        "db_name": "secret_key",
        "description": "JWT signing key (HS256)",
        "generate": lambda: secrets.token_hex(32),
    },
    "refresh": {
        "env_var": "REFRESH_SECRET",
        "db_name": "refresh_secret",
        "description": "Refresh token signing key",
        "generate": lambda: secrets.token_hex(32),
    },
    "webhook": {
        "env_var": "WEBHOOK_SIGNING_KEY",
        "db_name": "webhook_signing_key",
        "description": "Webhook HMAC-SHA256 signing key",
        "generate": lambda: secrets.token_hex(32),
    },
    "pepper": {
        "env_var": "SERVER_PEPPER",
        "db_name": "server_pepper",
        "description": "Server pepper for password hashing",
        "generate": lambda: secrets.token_hex(16),
    },
    "admin": {
        "env_var": "ADMIN_API_SECRET",
        "db_name": "admin_api_secret",
        "description": "Admin API authentication secret",
        "generate": lambda: secrets.token_urlsafe(48),
    },
}


def _encrypt_value(plaintext: str, encryption_key_hex: str) -> str:
    """AES-256-GCM encrypt a value using the internal DB encryption key."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = bytes.fromhex(encryption_key_hex)
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def main():
    args = json.loads(os.environ.get("SCRIPT_ARGS", "{}"))
    requested = args.get("secrets", list(SECRET_DEFS.keys()))

    # Require the encryption key
    encryption_key = os.environ.get("INTERNAL_DB_ENCRYPTION_KEY", "")
    if not encryption_key:
        # Try loading from .env
        env_path = Path(__file__).parent.parent.parent / ".env"
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("INTERNAL_DB_ENCRYPTION_KEY="):
                        encryption_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break

    if not encryption_key:
        print("ERROR: INTERNAL_DB_ENCRYPTION_KEY not found in environment or .env file.")
        print("Cannot encrypt secrets without the encryption key.")
        sys.exit(1)

    print("=== Secret Rotation ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"Secrets to rotate: {', '.join(requested)}")
    print()

    # Connect to internal.db
    try:
        from api.database import init_databases, get_internal_session
        init_databases()
    except Exception as e:
        print(f"ERROR: Failed to initialize databases: {e}")
        sys.exit(1)

    from api.models.internal import ServerSecret, AdminAuditLog

    env_updates = {}
    rotated = 0
    errors = 0

    with get_internal_session() as db:
        for name in requested:
            defn = SECRET_DEFS.get(name)
            if not defn:
                print(f"  {name}: SKIPPED (unknown secret)")
                continue

            try:
                new_value = defn["generate"]()
                encrypted = _encrypt_value(new_value, encryption_key)

                # Upsert into ServerSecret table
                existing = db.query(ServerSecret).filter(
                    ServerSecret.name == defn["db_name"],
                ).first()

                if existing:
                    existing.encrypted_value = encrypted
                    existing.rotated_at = datetime.now(timezone.utc)
                    print(f"  {name} ({defn['env_var']}): ROTATED")
                else:
                    secret = ServerSecret(
                        id=str(uuid.uuid4()),
                        name=defn["db_name"],
                        encrypted_value=encrypted,
                        description=defn["description"],
                        created_by="rotate_secrets",
                    )
                    db.add(secret)
                    print(f"  {name} ({defn['env_var']}): CREATED")

                # Track for .env update instructions
                env_updates[defn["env_var"]] = new_value
                rotated += 1

                print(f"    Preview: {new_value[:8]}...{new_value[-4:]} ({len(new_value)} chars)")

            except Exception as e:
                print(f"  {name}: ERROR — {e}")
                errors += 1

        # Write audit log entry
        try:
            db.add(AdminAuditLog(
                id=str(uuid.uuid4()),
                admin_username="rotate_secrets",
                action="ROTATE_SECRETS",
                target_type="secret",
                target_id=",".join(requested),
                details=f"rotated={rotated}, errors={errors}",
            ))
        except Exception as e:
            print(f"  WARNING: Failed to write audit log: {e}")

        db.commit()

    print(f"\n{rotated} secret(s) rotated in internal.db, {errors} error(s).")

    if env_updates:
        print("\n" + "=" * 60)
        print("UPDATE YOUR .env FILE WITH THESE NEW VALUES:")
        print("=" * 60)
        for env_var, value in env_updates.items():
            print(f'{env_var}="{value}"')
        print("=" * 60)
        print("\nThen restart the server: sudo systemctl restart refinet-api")
        print("WARNING: Active JWT tokens will be invalidated if SECRET_KEY was rotated.")
        print("WARNING: Active refresh tokens will be invalidated if REFRESH_SECRET was rotated.")
        print("WARNING: Password verification will break if SERVER_PEPPER was rotated (users must reset passwords).")


if __name__ == "__main__":
    main()
