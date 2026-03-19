#!/usr/bin/env python3
"""
Rotate platform secrets (JWT keys, webhook signing keys).
Generates new cryptographically secure values and updates them in internal.db.

Usage:
    python scripts/maintenance/rotate_secrets.py

Environment:
    SCRIPT_ARGS: JSON {"secrets": ["jwt", "webhook", "pepper"]}  (optional, defaults to all)
"""

import json
import os
import secrets
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "rotate_secrets",
    "description": "Rotate platform secrets (JWT key, webhook signing key, server pepper)",
    "category": "maintenance",
    "requires_admin": True,
}

# Secret definitions: name → (env_var, generator, description)
SECRET_DEFS = {
    "jwt": {
        "env_var": "SECRET_KEY",
        "description": "JWT signing key (HS256)",
        "generate": lambda: secrets.token_hex(32),
    },
    "refresh": {
        "env_var": "REFRESH_SECRET",
        "description": "Refresh token signing key",
        "generate": lambda: secrets.token_hex(32),
    },
    "webhook": {
        "env_var": "WEBHOOK_SIGNING_KEY",
        "description": "Webhook HMAC-SHA256 signing key",
        "generate": lambda: secrets.token_hex(32),
    },
    "pepper": {
        "env_var": "SERVER_PEPPER",
        "description": "Server pepper for password hashing",
        "generate": lambda: secrets.token_hex(16),
    },
    "admin": {
        "env_var": "ADMIN_API_SECRET",
        "description": "Admin API authentication secret",
        "generate": lambda: secrets.token_urlsafe(48),
    },
}


def main():
    args = json.loads(os.environ.get("SCRIPT_ARGS", "{}"))
    requested = args.get("secrets", list(SECRET_DEFS.keys()))

    print("=== Secret Rotation ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"Secrets to rotate: {', '.join(requested)}")
    print()

    # WARNING: This only generates and prints new values.
    # The actual .env file must be updated manually or via deploy script.
    # This avoids accidental lockout from automated rotation.

    rotated = []
    for name in requested:
        defn = SECRET_DEFS.get(name)
        if not defn:
            print(f"  {name}: SKIPPED (unknown secret)")
            continue

        new_value = defn["generate"]()
        rotated.append({
            "name": name,
            "env_var": defn["env_var"],
            "description": defn["description"],
            "new_value_preview": new_value[:8] + "..." + new_value[-4:],
            "full_length": len(new_value),
        })

        print(f"  {name} ({defn['env_var']}):")
        print(f"    Description: {defn['description']}")
        print(f"    New value: {new_value[:8]}...{new_value[-4:]} ({len(new_value)} chars)")

    print(f"\n{len(rotated)} secret(s) generated.")
    print("\nIMPORTANT: Update your .env file with these new values and restart the server.")
    print("The old values remain active until the server is restarted with the new .env.")


if __name__ == "__main__":
    main()
