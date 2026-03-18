#!/usr/bin/env python3
"""
REFINET Cloud — Admin CLI
Direct access to internal.db. Runs locally on the server.
Never makes HTTP requests. Every write creates an audit log entry.

Usage:
    python3 admin.py users list
    python3 admin.py users grant-role {user_id} admin
    python3 admin.py users revoke-role {user_id} admin
    python3 admin.py secrets set {name} {value}
    python3 admin.py secrets list
    python3 admin.py secrets rotate {name}
    python3 admin.py products register {name}
    python3 admin.py products list
    python3 admin.py mcp add {name} {url} {transport}
    python3 admin.py mcp list
    python3 admin.py audit tail --lines 50
    python3 admin.py stats today
"""

import sys
import os
import json
import uuid
import hashlib
import getpass
import socket
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import sqlite3

PUBLIC_DB = os.environ.get("PUBLIC_DB_URL", "sqlite:////opt/refinet/data/public.db").replace("sqlite:///", "")
INTERNAL_DB = os.environ.get("INTERNAL_DB_URL", "sqlite:////opt/refinet/data/internal.db").replace("sqlite:///", "")
ENCRYPTION_KEY = os.environ.get("INTERNAL_DB_ENCRYPTION_KEY", "")

HOSTNAME = socket.gethostname()
ADMIN_USER = os.environ.get("USER", "admin")


def get_pub_db():
    conn = sqlite3.connect(PUBLIC_DB)
    conn.row_factory = sqlite3.Row
    return conn


def get_int_db():
    conn = sqlite3.connect(INTERNAL_DB)
    conn.row_factory = sqlite3.Row
    return conn


def audit_log(db, action, target_type, target_id=None, details=None):
    """Append to admin_audit_log. This is the ONLY correct way to log admin actions."""
    db.execute(
        "INSERT INTO admin_audit_log (id, admin_username, action, target_type, target_id, details, ip_address, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), ADMIN_USER, action, target_type, target_id, details, "localhost", datetime.now(timezone.utc).isoformat()),
    )
    db.commit()


def encrypt_value(plaintext):
    """AES-256-GCM encrypt using INTERNAL_DB_ENCRYPTION_KEY."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    import base64
    key = bytes.fromhex(ENCRYPTION_KEY)
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


# ── Commands ───────────────────────────────────────────────────────

def cmd_users_list():
    db = get_pub_db()
    users = db.execute("SELECT id, email, username, tier, is_active, created_at FROM users ORDER BY created_at DESC").fetchall()
    print(f"{'ID':<38} {'Email':<30} {'Username':<20} {'Tier':<10} {'Active'}")
    print("-" * 130)
    for u in users:
        print(f"{u['id']:<38} {u['email']:<30} {u['username']:<20} {u['tier']:<10} {u['is_active']}")


def cmd_users_grant_role(user_id, role):
    if role not in ("admin", "operator", "readonly"):
        print(f"Invalid role: {role}")
        return
    db = get_int_db()
    db.execute(
        "INSERT INTO role_assignments (id, user_id, role, granted_by, granted_at, is_active) VALUES (?, ?, ?, ?, ?, 1)",
        (str(uuid.uuid4()), user_id, role, ADMIN_USER, datetime.now(timezone.utc).isoformat()),
    )
    audit_log(db, "GRANT_ROLE", "user", user_id, json.dumps({"role": role}))
    print(f"Granted {role} to {user_id}")


def cmd_users_revoke_role(user_id, role):
    db = get_int_db()
    db.execute(
        "UPDATE role_assignments SET is_active = 0, revoked_at = ? WHERE user_id = ? AND role = ? AND is_active = 1",
        (datetime.now(timezone.utc).isoformat(), user_id, role),
    )
    audit_log(db, "REVOKE_ROLE", "user", user_id, json.dumps({"role": role}))
    print(f"Revoked {role} from {user_id}")


def cmd_secrets_set(name, value):
    db = get_int_db()
    encrypted = encrypt_value(value)
    existing = db.execute("SELECT id FROM server_secrets WHERE name = ?", (name,)).fetchone()
    if existing:
        db.execute("UPDATE server_secrets SET encrypted_value = ?, rotated_at = ? WHERE name = ?",
                    (encrypted, datetime.now(timezone.utc).isoformat(), name))
    else:
        db.execute(
            "INSERT INTO server_secrets (id, name, encrypted_value, created_by, created_at) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), name, encrypted, ADMIN_USER, datetime.now(timezone.utc).isoformat()),
        )
    audit_log(db, "WRITE_SECRET", "secret", name)
    print(f"Secret '{name}' stored (encrypted)")


def cmd_secrets_list():
    db = get_int_db()
    secrets = db.execute("SELECT name, description, created_by, created_at, rotated_at FROM server_secrets").fetchall()
    print(f"{'Name':<30} {'Created By':<15} {'Created':<25} {'Rotated'}")
    print("-" * 100)
    for s in secrets:
        print(f"{s['name']:<30} {s['created_by']:<15} {s['created_at'] or '':<25} {s['rotated_at'] or 'never'}")


def cmd_secrets_rotate(name):
    value = getpass.getpass(f"New value for '{name}': ")
    cmd_secrets_set(name, value)


def cmd_products_register(name):
    db = get_int_db()
    build_key = f"rf_{name[:2]}_{os.urandom(48).hex()}"
    key_hash = hashlib.sha256(build_key.encode()).hexdigest()
    db.execute(
        "INSERT INTO product_registry (id, name, build_key_hash, registered_at) VALUES (?, ?, ?, ?)",
        (str(uuid.uuid4()), name, key_hash, datetime.now(timezone.utc).isoformat()),
    )
    audit_log(db, "REGISTER_PRODUCT", "product", name)
    print(f"Product '{name}' registered")
    print(f"Build key: {build_key}")
    print("Save this key — it cannot be recovered.")


def cmd_products_list():
    db = get_int_db()
    products = db.execute("SELECT name, current_version, connection_count, last_connected_at FROM product_registry").fetchall()
    for p in products:
        print(f"{p['name']:<20} v{p['current_version'] or '?':<10} connections={p['connection_count']}")


def cmd_mcp_add(name, url, transport):
    db = get_int_db()
    db.execute(
        "INSERT INTO mcp_server_registry (id, name, url, transport, registered_at) VALUES (?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), name, url, transport, datetime.now(timezone.utc).isoformat()),
    )
    audit_log(db, "REGISTER_MCP", "mcp", name)
    print(f"MCP server '{name}' registered at {url}")


def cmd_mcp_list():
    db = get_int_db()
    servers = db.execute("SELECT name, url, transport, status, is_healthy FROM mcp_server_registry").fetchall()
    for s in servers:
        health = "✓" if s['is_healthy'] else "✗"
        print(f"{health} {s['name']:<20} {s['url']:<50} {s['transport']}")


def cmd_audit_tail(lines=50):
    db = get_int_db()
    logs = db.execute(
        "SELECT timestamp, admin_username, action, target_type, target_id FROM admin_audit_log ORDER BY timestamp DESC LIMIT ?",
        (lines,)
    ).fetchall()
    for l in logs:
        print(f"{l['timestamp']}  {l['admin_username']:<15} {l['action']:<20} {l['target_type']}:{l['target_id'] or '-'}")


def cmd_stats_today():
    pub = get_pub_db()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    users = pub.execute("SELECT COUNT(*) as c FROM users").fetchone()['c']
    devices = pub.execute("SELECT COUNT(*) as c FROM device_registrations WHERE status='active'").fetchone()['c']
    agents = pub.execute("SELECT COUNT(*) as c FROM agent_registrations").fetchone()['c']
    print(f"Total users:   {users}")
    print(f"Active devices: {devices}")
    print(f"Agents:        {agents}")


# ── CLI Router ─────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        return

    domain, action = args[0], args[1]

    if domain == "users" and action == "list":
        cmd_users_list()
    elif domain == "users" and action == "grant-role" and len(args) >= 4:
        cmd_users_grant_role(args[2], args[3])
    elif domain == "users" and action == "revoke-role" and len(args) >= 4:
        cmd_users_revoke_role(args[2], args[3])
    elif domain == "secrets" and action == "set" and len(args) >= 4:
        cmd_secrets_set(args[2], args[3])
    elif domain == "secrets" and action == "list":
        cmd_secrets_list()
    elif domain == "secrets" and action == "rotate" and len(args) >= 3:
        cmd_secrets_rotate(args[2])
    elif domain == "products" and action == "register" and len(args) >= 3:
        cmd_products_register(args[2])
    elif domain == "products" and action == "list":
        cmd_products_list()
    elif domain == "mcp" and action == "add" and len(args) >= 5:
        cmd_mcp_add(args[2], args[3], args[4])
    elif domain == "mcp" and action == "list":
        cmd_mcp_list()
    elif domain == "audit" and action == "tail":
        lines = 50
        if "--lines" in args:
            idx = args.index("--lines")
            if idx + 1 < len(args):
                lines = int(args[idx + 1])
        cmd_audit_tail(lines)
    elif domain == "stats" and action == "today":
        cmd_stats_today()
    else:
        print(f"Unknown command: {domain} {action}")
        print(__doc__)


if __name__ == "__main__":
    main()
