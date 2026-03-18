#!/usr/bin/env python3
"""
REFINET Cloud — Knowledge Base Seed Script
Seeds Groot's initial knowledge base with 7 foundational documents.
Idempotent: uses content hash deduplication (built into ingest_document).

Usage:
  python3 scripts/seed_knowledge.py --api-url https://api.refinet.io --token <admin_jwt>

Or run locally (direct DB access, no HTTP):
  python3 scripts/seed_knowledge.py --local
"""

import argparse
import json
import sys
import os

# ── Knowledge Documents ───────────────────────────────────────────

DOCUMENTS = [
    {
        "title": "What is REFINET Cloud",
        "category": "about",
        "content": """REFINET Cloud is a sovereign AI platform built for the Regenerative Finance Network. It provides free, permanent AI infrastructure that runs on hardware REFINET controls — not rented from a vendor, but owned.

At its core, REFINET Cloud runs BitNet b1.58 2B4T, a 1-bit open-source large language model that runs natively on CPU. No GPU required. No API bill. No vendor who can revoke access. The model weights are downloadable, the inference server is a single binary, and the computation happens on REFINET's own ARM server.

The platform provides an OpenAI-compatible API. Any application that works with OpenAI's API works with REFINET Cloud by changing two lines: the base URL and the API key. The endpoint is POST /v1/chat/completions with the same JSON format, same streaming SSE format, and same error handling. The switching cost is near zero in both directions — users stay because the product is good, not because they're locked in.

REFINET Cloud runs on Oracle Cloud's Always Free tier — a permanent allocation of 4 ARM OCPUs, 24GB RAM, 200GB storage, and 10TB monthly egress. This is not a trial; it's a permanent free tier. The entire platform is architecturally designed to fit within these limits: SQLite instead of PostgreSQL, in-memory rate limiting instead of Redis, BitNet instead of GPU-dependent models, Let's Encrypt for TLS. There is no bill. There is no invoice.

The platform features three-layer authentication: password (Argon2id with per-user salt and server pepper), TOTP (Google Authenticator compatible), and Sign-In with Ethereum (EIP-4361). The user's Ethereum address is mixed into their encryption key derivation via HKDF, meaning an attacker who steals the database and the server still cannot decrypt a user's secrets without also compromising their wallet.

REFINET Cloud also serves as a universal connectivity hub. IoT sensors send telemetry via HTTP. PLCs register with Modbus/OPC-UA metadata. DLT nodes register with chain and address. Autonomous agents register and receive remote configuration. Webhook events fire on telemetry receipt, device status changes, and commands. Any device that speaks HTTP is a participant in the REFINET network.

The AI assistant built into REFINET Cloud is called Groot. Groot uses Retrieval-Augmented Generation (RAG) to answer questions with grounded information from the knowledge base, and Contract Augmented Generation (CAG) to explain blockchain smart contracts. When someone asks Groot a question, it searches the knowledge base, finds relevant chunks, and responds with accurate, sourced information.""",
    },
    {
        "title": "REFINET Products",
        "category": "product",
        "content": """REFINET builds sovereign technology products that operate at zero recurring cost. Each product connects to REFINET Cloud as its AI backbone.

QuickCast is an autonomous content publishing platform. It generates podcast episodes and YouTube content using AI-driven workflows. QuickCast registers as an agent on REFINET Cloud, receives remote configuration, and uses the BitNet inference API to generate scripts and content outlines. The audio synthesis happens locally on the user's machine. The content is published automatically. Zero cost. Sovereign compute.

AgentOS is an AI agent platform that enables users to build, deploy, and manage autonomous agents. Each agent registers with REFINET Cloud via POST /agents/register and receives a unique agent_id with remote configuration. Agents use the inference API for reasoning, the knowledge base for context, and webhooks for event-driven actions. AgentOS is designed for developers who want to build AI-powered automation without paying per-token fees.

CIFI Wizards is a gamified learning platform with blockchain identity integration. It teaches concepts in regenerative finance, blockchain technology, and sovereign computing through interactive challenges and quests. Users earn on-chain credentials as they complete learning paths. CIFI Wizards uses REFINET Cloud for AI-powered tutoring, adaptive learning paths, and knowledge assessment.

All three products share the same principles: zero recurring cost, sovereign data ownership, open-source technology, and cryptographic identity. They demonstrate that powerful technology doesn't require subscription fees or vendor lock-in.""",
    },
    {
        "title": "Groot AI Assistant",
        "category": "about",
        "content": """Groot is the AI assistant that lives in REFINET Cloud. Named after the Marvel character who communicates simply but contains deep wisdom, Groot is designed to be helpful, technically precise, and approachable.

Groot is powered by BitNet b1.58 2B4T — a 1-bit ternary-weight language model with 2 billion parameters. Despite being compact, BitNet is remarkably capable for its size because its 1-bit architecture allows it to run entirely on CPU with minimal memory (~500MB). This means Groot runs on the same ARM server as the rest of REFINET Cloud, with no GPU required and no inference cost.

Groot uses Retrieval-Augmented Generation (RAG) to provide accurate answers. Before every inference call, Groot's system searches the knowledge base for relevant document chunks. These chunks are injected into the system prompt as context, so Groot answers with grounded information rather than hallucinating. When you ask "What is REFINET?", Groot searches the knowledge base, finds the relevant documents, and constructs an answer from real content.

Groot also uses Contract Augmented Generation (CAG) for blockchain-related questions. Smart contract definitions — including ABIs, descriptions, and logic summaries — are stored in the knowledge base and searched alongside document chunks. This means Groot can explain what a contract does, what functions are available, and how they work.

You can interact with Groot in three ways:
1. The floating chat widget on any page (bottom-right corner) — click the REFINET logo
2. The full-screen chat at /chat — a dedicated conversation interface
3. The API at POST /v1/chat/completions — OpenAI-compatible, works with any SDK

Groot's knowledge grows as administrators upload new documents to the knowledge base. Every document is automatically chunked and indexed for search. Within seconds of uploading new content, Groot can answer questions about it.""",
    },
    {
        "title": "Getting Started with REFINET Cloud",
        "category": "docs",
        "content": """Getting started with REFINET Cloud takes about 5 minutes. Here's how to go from zero to your first API call.

Step 1: Create Your Account
Visit app.refinet.io and click "Get Started." The registration wizard walks you through three authentication layers:
- Layer 1 (Password): Choose a strong password (12+ characters). It's hashed with Argon2id.
- Layer 2 (TOTP): Scan the QR code with Google Authenticator, Authy, or any TOTP app. Enter the 6-digit code to verify.
- Layer 3 (Ethereum): Connect your MetaMask or other Ethereum wallet. Sign a message to link your address. This address becomes a cryptographic component of your encryption keys.

Step 2: Get an API Key
Go to Settings (/settings) and click "Create Key." Give it a name. The key will be shown once — copy it immediately. API keys start with the prefix "rf_" and have a daily request limit (default: 100 for free tier).

Step 3: Make Your First API Call
Use any OpenAI-compatible SDK:

from openai import OpenAI

client = OpenAI(
    base_url="https://api.refinet.io/v1",
    api_key="rf_your_key_here"
)

response = client.chat.completions.create(
    model="bitnet-b1.58-2b",
    messages=[{"role": "user", "content": "What is REFINET?"}]
)

print(response.choices[0].message.content)

The API supports streaming (stream=True), which returns Server-Sent Events (SSE) in the same format as OpenAI. You can also use curl, JavaScript fetch, or any HTTP client.

Step 4: Explore the Dashboard
Visit /dashboard to see your account stats, API key usage, and connected devices. The dashboard shows your auth layer status, active keys, registered devices, and usage metrics.

Step 5: Register Devices (Optional)
If you're connecting IoT devices, PLCs, or DLT nodes, use POST /devices/register with your JWT. Each device gets its own scoped API key for telemetry ingestion.""",
    },
    {
        "title": "Device Connectivity",
        "category": "docs",
        "content": """REFINET Cloud is not just a chat platform — it's a universal device connectivity hub. Any device that speaks HTTP can connect, register, send telemetry, receive commands, and trigger webhooks.

Device Types:
- IoT: Internet of Things sensors (temperature, humidity, motion, GPS). Register with POST /devices/register and device_type: "iot".
- PLC: Programmable Logic Controllers for industrial automation. Register with POST /devices/register-plc and include Modbus/OPC-UA metadata.
- DLT: Distributed Ledger Technology nodes. Register with POST /devices/register-dlt and include chain name and node address.

Registration:
POST /devices/register
{
    "name": "temperature-sensor-01",
    "device_type": "iot",
    "metadata": {"location": "warehouse-a", "unit": "celsius"}
}

The response includes a device-scoped API key (returned once, starts with "rf_dev_"). Use this key for all subsequent device operations.

Telemetry Ingestion:
POST /devices/{device_id}/telemetry
Authorization: Bearer rf_dev_...
{
    "data": {"temperature": 23.4, "humidity": 45.2},
    "timestamp": "2025-01-15T10:30:00Z"
}

Telemetry records are stored in the database with automatic cleanup (records older than 7 days are deleted by cron).

Commands:
Send commands to devices via POST /devices/{device_id}/command. The device polls for commands or receives them via webhook.

Webhooks:
Subscribe to device events with POST /webhooks/subscribe:
{
    "url": "https://your-app.com/webhook",
    "events": ["telemetry.received", "device.status_changed", "command.sent"],
    "device_id": "optional-filter-by-device"
}

Webhook payloads are signed with HMAC-SHA256. Verify using the X-REFINET-Signature header: sha256={hmac}. The signing secret is returned once when you create the subscription.

Webhook subscriptions auto-disable after 10 consecutive delivery failures.""",
    },
    {
        "title": "Regenerative Finance",
        "category": "about",
        "content": """Regenerative Finance (ReFi) is a movement to redesign financial systems so they regenerate rather than extract. Where traditional finance optimizes for shareholder returns, ReFi optimizes for ecological health, social equity, and long-term sustainability.

REFINET applies ReFi principles to technology infrastructure:

Zero-Cost Infrastructure: Traditional SaaS charges monthly subscriptions that extract value from users. REFINET Cloud runs on permanently free infrastructure (Oracle Cloud Always Free tier), eliminating the extraction model entirely. Users don't pay for intelligence — it's a shared resource.

Open Source: All REFINET code is open-source under AGPL-3.0. Anyone can fork, deploy, and run their own REFINET Cloud. Knowledge should be shared, not locked behind paywalls. The platform's value comes from its network, not from artificial scarcity.

Data Sovereignty: In traditional cloud platforms, your data is the product. REFINET Cloud keeps all data on infrastructure the platform controls. No telemetry to third parties. No data sold. The dual-database architecture (public + internal) ensures admin secrets never touch the public API. The audit log is append-only — it cannot be modified or deleted.

Cryptographic Identity: Instead of email/password authentication that can be phished, REFINET uses Ethereum keypairs as the third authentication layer. Your wallet isn't just for login — it's mathematically woven into your encryption keys. This creates identity that is self-sovereign: you own your keys, you control your access, no central authority can revoke it.

Network Effects That Give Back: Every device that connects to REFINET Cloud, every document in the knowledge base, every contract definition in CAG — these all make the platform more valuable for everyone. But unlike Web2 network effects that concentrate value in a corporation, REFINET's open-source model means the value stays distributed.

The vision is a post-subscription internet where intelligence is a public good, identity is self-sovereign, and infrastructure regenerates rather than extracts.""",
    },
    {
        "title": "Sovereign Infrastructure",
        "category": "about",
        "content": """Sovereign infrastructure means running technology on hardware you control, with software you can audit, using protocols no one can revoke. REFINET Cloud is built entirely on this principle.

Why Sovereignty Matters:
When you use a cloud API, you're renting intelligence. The provider can raise prices, change terms, throttle access, or shut down entirely. Your application's core capability depends on someone else's business decisions. Sovereign infrastructure eliminates this dependency.

REFINET Cloud's Sovereignty Architecture:

1. Hardware: Oracle Cloud Always Free ARM A1 Flex — 4 OCPUs, 24GB RAM, 200GB storage. This is a permanent allocation, not a trial. The server is dedicated to REFINET and cannot be reclaimed (as long as the account remains active and the instance is used).

2. Model: BitNet b1.58 2B4T is fully open-source. The weights are downloadable from HuggingFace. The inference binary (llama-server from llama.cpp) is compiled from source on the ARM server. No API calls to external model providers. No usage-based billing. The intelligence runs locally.

3. Database: Dual SQLite databases in WAL mode. The public database serves the API. The internal database holds secrets, roles, audit logs, and MCP server credentials. The internal database is NEVER accessible via any public endpoint. SQLite files are just files on disk — fully portable, fully backupable, zero external dependencies.

4. TLS: Let's Encrypt provides free, automated TLS certificates. No certificate vendor. No annual renewal fees. Certbot handles renewal automatically.

5. DNS: Standard A records pointing to the server's public IP. Any DNS provider works. No proprietary DNS service required.

6. Authentication: The three-layer auth system uses standard cryptographic primitives: Argon2id (OWASP recommended), TOTP (RFC 6238), and EIP-4361 (Ethereum standard). No proprietary auth service. No OAuth dependency on Google/GitHub/Auth0.

The Dual-Database Design:
REFINET Cloud uses two physically separate SQLite databases. The public database (public.db) contains 12 tables: users, API keys, device registrations, agent registrations, IoT telemetry, webhook subscriptions, usage records, SIWE nonces, refresh tokens, knowledge documents, knowledge chunks, and contract definitions. The internal database (internal.db) contains 6 tables: server secrets, role assignments, admin audit log, product registry, MCP server registry, and system config. This separation means a SQL injection in the public API cannot reach admin secrets or audit logs.

The admin CLI (scripts/admin.py) operates directly on the internal database via local SQLite access — no HTTP, no network, no API. Admin operations require physical server access, which is the strongest access control possible.

Forkability:
Anyone can take the REFINET Cloud codebase, deploy it on their own Oracle Cloud instance (or any ARM server), and run their own sovereign AI platform. The code is AGPL-3.0 licensed. The setup is documented. The bootstrap script is idempotent. This is by design — sovereignty means no one, including REFINET, can be a single point of failure.""",
    },
]


def seed_via_api(api_url: str, token: str):
    """Seed knowledge base via HTTP API."""
    import urllib.request

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    for doc in DOCUMENTS:
        print(f"  Uploading: {doc['title']}...")
        payload = json.dumps({
            "title": doc["title"],
            "content": doc["content"],
            "category": doc["category"],
        }).encode()

        req = urllib.request.Request(
            f"{api_url}/knowledge/documents",
            data=payload,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
                print(f"    -> {result.get('message', 'OK')} (chunks: {result.get('chunk_count', '?')})")
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            print(f"    -> ERROR {e.code}: {body}")
        except Exception as e:
            print(f"    -> ERROR: {e}")


def seed_via_local():
    """Seed knowledge base via direct database access (no HTTP)."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from api.database import get_public_db
    from api.services.rag import ingest_document
    import api.models  # noqa — register models

    with get_public_db() as db:
        for doc in DOCUMENTS:
            print(f"  Ingesting: {doc['title']}...")
            result = ingest_document(
                db,
                title=doc["title"],
                content=doc["content"],
                category=doc["category"],
                uploaded_by="seed_script",
            )
            print(f"    -> Chunks: {result.chunk_count}")

    print(f"\n  Done. {len(DOCUMENTS)} documents seeded.")


def main():
    parser = argparse.ArgumentParser(description="Seed REFINET Cloud knowledge base")
    parser.add_argument("--api-url", help="API base URL (e.g., https://api.refinet.io)")
    parser.add_argument("--token", help="Admin JWT token")
    parser.add_argument("--local", action="store_true", help="Use direct DB access (no HTTP)")
    args = parser.parse_args()

    print("REFINET Cloud — Knowledge Base Seed")
    print(f"  Documents: {len(DOCUMENTS)}")
    print()

    if args.local:
        seed_via_local()
    elif args.api_url and args.token:
        seed_via_api(args.api_url, args.token)
    else:
        print("Usage:")
        print("  python3 scripts/seed_knowledge.py --local")
        print("  python3 scripts/seed_knowledge.py --api-url https://api.refinet.io --token <jwt>")
        sys.exit(1)


if __name__ == "__main__":
    main()
