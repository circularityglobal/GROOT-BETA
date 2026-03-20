# REFINET Cloud — Oracle Cloud ARM Deployment Guide

Deploy GROOT + REFINET Cloud on Oracle Cloud Always Free ARM A1 Flex.
Zero cost. Sovereign infrastructure. Your hardware.

---

## Prerequisites

- Oracle Cloud account (Always Free tier)
- SSH key pair (`ssh-keygen -t ed25519`)
- Domain: `refinet.io` with DNS access
- Local machine with `ssh` and `scp`

---

## Step 1: Provision Oracle Cloud Instance

### 1.1 Create Compute Instance

1. Log into Oracle Cloud Console → Compute → Instances → **Create Instance**
2. Settings:
   - **Name:** `refinet-cloud`
   - **Image:** Ubuntu 22.04 (Canonical) — **ARM (aarch64)**
   - **Shape:** VM.Standard.A1.Flex
     - OCPUs: **4**
     - Memory: **24 GB**
   - **Boot volume:** **200 GB**
   - **SSH key:** Upload your public key
3. Click **Create**
4. Note the **Public IP address** once the instance is running

### 1.2 Configure Network Security

Go to Networking → Virtual Cloud Networks → your VCN → Security Lists → Default:

| Direction | Protocol | Port | Source      |
|-----------|----------|------|-------------|
| Ingress   | TCP      | 22   | 0.0.0.0/0   |
| Ingress   | TCP      | 80   | 0.0.0.0/0   |
| Ingress   | TCP      | 443  | 0.0.0.0/0   |

Also open the **iptables** on the instance (Oracle Cloud uses iptables by default):

```bash
ssh ubuntu@<PUBLIC_IP>
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

> **Note:** Ports 8000 (FastAPI), 8025 (SMTP bridge), 8080 (BitNet), and 50051 (gRPC) remain internal-only. Do NOT expose them externally.

---

## Step 2: Configure DNS

Add these A records in your DNS provider for `refinet.io`:

| Record | Name           | Value         | TTL  |
|--------|----------------|---------------|------|
| A      | api            | `<PUBLIC_IP>` | 300  |
| A      | app            | `<PUBLIC_IP>` | 300  |
| A      | infrastructure | `<PUBLIC_IP>` | 300  |
| A      | browser        | `<PUBLIC_IP>` | 300  |

Verify propagation:
```bash
dig api.refinet.io +short
dig app.refinet.io +short
dig infrastructure.refinet.io +short
dig browser.refinet.io +short
```

All should return your Oracle Cloud public IP.

---

## Step 3: Upload Code to Server

```bash
# From your local machine (in the groot/ directory)
scp -r . ubuntu@<PUBLIC_IP>:/home/ubuntu/groot

# SSH into the server
ssh ubuntu@<PUBLIC_IP>

# Move code to the app directory
sudo mkdir -p /opt/refinet/app
sudo cp -r ~/groot/* /opt/refinet/app/
sudo cp -r ~/groot/.env.example /opt/refinet/app/
```

---

## Step 4: Run Bootstrap

```bash
sudo bash /opt/refinet/app/scripts/bootstrap.sh
```

This script is idempotent and does 10 things:
1. Installs system packages (build-essential, cmake, python3, nginx, certbot, nodejs)
2. Configures UFW firewall (ports 22, 80, 443)
3. Sets up fail2ban for SSH brute-force protection
4. Creates `/opt/refinet/{app,data,logs}` directories
5. Creates Python virtual environment at `/opt/refinet/venv`
6. **Builds BitNet b1.58 2B4T** (clones Microsoft/BitNet, builds llama.cpp for ARM, quantizes model)
7. Creates systemd services (`refinet-bitnet`, `refinet-api`)
8. Initializes database directory with correct permissions
9. Sets up cron jobs (telemetry cleanup, nonce cleanup, API key reset)
10. Sets file permissions (www-data ownership, .env at 600)

**BitNet build takes 15-30 minutes on ARM.** This is normal.

---

## Step 5: Generate Production Secrets

```bash
cd /opt/refinet/app
sudo bash scripts/generate_env.sh api.refinet.io app.refinet.io > /tmp/env_new
sudo mv /tmp/env_new /opt/refinet/app/.env
sudo chmod 600 /opt/refinet/app/.env
sudo chown www-data:www-data /opt/refinet/app/.env
```

Verify the secrets were generated:
```bash
sudo grep -c "CHANGE_ME" /opt/refinet/app/.env
# Should output: 0
```

The `.env` file configures:
- **Core secrets**: SECRET_KEY, REFRESH_SECRET, SERVER_PEPPER, WEBHOOK_SIGNING_KEY, INTERNAL_DB_ENCRYPTION_KEY, ADMIN_API_SECRET
- **SIWE settings**: SIWE_DOMAIN, SIWE_CHAIN_ID, SIWE_SUPPORTED_CHAINS (1,137,42161,10,8453,11155111)
- **Identity**: WALLET_EMAIL_DOMAIN (cifi.global)
- **SMTP**: SMTP_HOST, SMTP_PORT, SMTP_ENABLED
- **Rate limits**: RATE_LIMIT_PER_MINUTE, FREE_TIER_DAILY_REQUESTS
- **Product keys**: QUICKCAST_BUILD_KEY, AGENTOS_BUILD_KEY

---

## Step 6: Start Services

### 6.1 Start BitNet Inference

```bash
sudo systemctl start refinet-bitnet
sudo systemctl status refinet-bitnet
```

Wait 10 seconds for the model to load, then verify:
```bash
curl http://127.0.0.1:8080/health
# Should return: {"status":"ok"}
```

### 6.2 Start the API

The API server starts FastAPI (port 8000) along with:
- gRPC server (port 50051) — optional, graceful degradation if grpcio not installed
- SMTP bridge (port 8025) — optional, graceful degradation if disabled
- Background workers: P2P cleanup, health monitor, auth cleanup, webhook delivery

```bash
sudo systemctl start refinet-api
sudo systemctl status refinet-api
```

Verify:
```bash
curl http://127.0.0.1:8000/health
# Should return: {"status":"ok","inference":"available","model":"bitnet-b1.58-2b",...}
```

If `inference` shows `"unavailable"`, BitNet hasn't finished loading — wait and retry.

### 6.3 Verify Internal Services

```bash
# Check gRPC (optional)
# If grpcio is installed, port 50051 should be listening
ss -tlnp | grep 50051

# Check SMTP bridge (optional)
# If SMTP_ENABLED=true, port 8025 should be listening
ss -tlnp | grep 8025
```

---

## Step 7: Build & Deploy Frontend

```bash
cd /opt/refinet/app/frontend

# Install Node.js dependencies
npm install --production

# Build static export with your API URL
NEXT_PUBLIC_API_URL=https://api.refinet.io npm run build

# Deploy to Nginx serving directory
sudo mkdir -p /opt/refinet/frontend/out
sudo cp -r out/* /opt/refinet/frontend/out/
sudo chown -R www-data:www-data /opt/refinet/frontend
```

---

## Step 8: Configure Nginx & TLS

### 8.1 Install Nginx Config

```bash
sudo cp /opt/refinet/app/nginx/refinet.conf /etc/nginx/sites-available/refinet
sudo ln -sf /etc/nginx/sites-available/refinet /etc/nginx/sites-enabled/refinet
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
```

The Nginx config handles:
- HTTP → HTTPS redirect
- TLS termination
- API proxy to `127.0.0.1:8000`
- SSE passthrough for `/v1/*` (proxy_buffering off)
- WebSocket upgrade for `/ws` (Connection: upgrade)
- Rate limiting zones (auth: 5 req/s, api: 30 req/s)
- Security headers (X-Frame-Options, HSTS, etc.)
- Static file serving for frontend and product subdomains

### 8.2 Get TLS Certificates (requires DNS to be pointing to this server)

First, temporarily comment out the SSL server blocks in the nginx config and add a basic HTTP server for certbot:

```bash
# Get certificates
sudo certbot --nginx -d api.refinet.io -d app.refinet.io -d infrastructure.refinet.io -d browser.refinet.io --non-interactive --agree-tos -m your-email@refinet.io

# Restart nginx with full TLS config
sudo systemctl restart nginx
```

### 8.3 Verify HTTPS

```bash
curl https://api.refinet.io/health
# Should return the health JSON

curl -s -o /dev/null -w "%{http_code}" https://app.refinet.io/
# Should return: 200
```

---

## Step 9: Create First Admin

### 9.1 Connect Wallet via Frontend

Visit `https://app.refinet.io/settings` and connect your Ethereum wallet via SIWE. Complete the onboarding to create your account.

### 9.2 Grant Admin Role

```bash
cd /opt/refinet/app
source /opt/refinet/venv/bin/activate
python3 scripts/admin.py users list
python3 scripts/admin.py users grant-role <USER_ID> admin
```

### 9.3 Seed Knowledge Base (Optional)

As admin, visit `https://app.refinet.io/knowledge` and upload documents for GROOT to learn from:
- REFINET whitepaper
- Product documentation
- FAQ documents
- Smart contract ABIs

Or use the API:
```bash
curl -X POST https://api.refinet.io/knowledge/documents \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -F "file=@whitepaper.pdf" \
  -F "title=REFINET Whitepaper" \
  -F "category=about"
```

---

## Step 10: Verify Deployment

```bash
sudo bash /opt/refinet/app/scripts/verify_deployment.sh api.refinet.io
```

This runs 20+ automated checks: services, ports, databases, files, TLS, firewall.

### Manual Verification Checklist

| Check | Command | Expected |
|---|---|---|
| API health | `curl https://api.refinet.io/health` | `{"status":"ok","inference":"available"}` |
| Frontend | `curl -s -o /dev/null -w "%{http_code}" https://app.refinet.io/` | 200 |
| SIWE nonce | `curl -X POST https://api.refinet.io/auth/siwe/nonce -H "Content-Type: application/json" -d '{"chain_id":1}'` | 200 + nonce |
| Models | `curl https://api.refinet.io/v1/models` | Model list |
| Explore | `curl https://api.refinet.io/explore/contracts` | Contract list (may be empty) |
| WebSocket | Connect to `wss://api.refinet.io/ws` | Connection established |
| GraphQL | `curl -X POST https://api.refinet.io/graphql -H "Content-Type: application/json" -d '{"query":"{ __typename }"}'` | Response (if strawberry installed) |

---

## Quick Reference

### Service Management

```bash
# Status
sudo systemctl status refinet-bitnet refinet-api nginx

# Restart API (after code changes)
sudo systemctl restart refinet-api

# Restart BitNet (only if model changes)
sudo systemctl restart refinet-bitnet

# View logs
sudo journalctl -u refinet-api -f
sudo journalctl -u refinet-bitnet -f
```

### Redeployment

After pushing code updates:
```bash
cd /opt/refinet/app
sudo bash scripts/deploy.sh
```

### Secret Rotation

```bash
sudo bash /opt/refinet/app/scripts/rotate_secrets.sh
# Copy new values to .env, then:
sudo systemctl restart refinet-api
```

### Database Access

```bash
# Public DB (user data — 30+ tables)
sqlite3 /opt/refinet/data/public.db

# Internal DB (admin/secrets — 10+ tables, NEVER expose via API)
sqlite3 /opt/refinet/data/internal.db

# Admin CLI
cd /opt/refinet/app && source /opt/refinet/venv/bin/activate
python3 scripts/admin.py --help
```

---

## Architecture on Oracle Cloud

```
Oracle Cloud ARM A1 Flex (4 OCPUs, 24GB RAM, 200GB)
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  Nginx (:80/:443)                                       │
│  ├── api.refinet.io    → proxy → FastAPI (:8000)        │
│  ├── app.refinet.io    → static files (frontend)        │
│  ├── infrastructure.refinet.io → REFINET Pillars        │
│  └── browser.refinet.io → REFINET Browser               │
│                                                         │
│  FastAPI/uvicorn (:8000)                                │
│  ├── Auth (SIWE multi-chain + optional password/TOTP)   │
│  ├── Inference → proxy → BitNet (:8080)                 │
│  ├── RAG (hybrid keyword + semantic, 384-dim embeddings)│
│  ├── CAG (contract ABI parsing + SDK generation)        │
│  ├── Registry (GitHub-style smart contract projects)    │
│  ├── GROOT Brain (personal contract repository)         │
│  ├── Messaging (wallet DMs, groups, email bridge)       │
│  ├── P2P (presence, gossip, peer discovery)             │
│  ├── Identity (multi-chain wallets, ENS, pseudo-IPv6)   │
│  ├── Devices (IoT, PLC, DLT + telemetry)               │
│  ├── Webhooks (HMAC-SHA256 signed, retry with backoff)  │
│  ├── GraphQL (/graphql, optional)                       │
│  ├── SOAP (/soap, optional)                             │
│  ├── WebSocket (/ws, real-time events)                  │
│  └── SQLite (public.db 30+ tbl + internal.db 10+ tbl)  │
│                                                         │
│  gRPC Server (:50051, optional)                         │
│  └── Registry service methods                           │
│                                                         │
│  SMTP Bridge (:8025, optional)                          │
│  └── Email-to-DM routing via wallet aliases             │
│                                                         │
│  BitNet llama-server (:8080)                            │
│  └── BitNet b1.58 2B4T (i2_s, ~500MB)                  │
│                                                         │
│  Background Workers                                     │
│  ├── P2P cleanup (60s)                                  │
│  ├── Health monitor (60s)                               │
│  ├── Auth cleanup (3600s)                               │
│  └── Webhook delivery (async queue)                     │
│                                                         │
│  Cost: $0/month (Always Free tier)                      │
└─────────────────────────────────────────────────────────┘
```

---

## Troubleshooting

### BitNet build fails
```bash
# Check build dependencies
sudo apt install build-essential cmake git python3-dev
# Retry build
cd /opt/refinet/bitnet-src
pip install -r requirements.txt
python setup_env.py --hf-repo microsoft/BitNet-b1.58-2B-4T -q i2_s
```

### API won't start
```bash
sudo journalctl -u refinet-api --no-pager -n 50
# Common: missing .env, wrong DB path, import errors, missing Python dependencies
# Check all deps installed:
source /opt/refinet/venv/bin/activate
pip install -r /opt/refinet/app/requirements.txt
```

### gRPC not starting
```bash
# gRPC is optional — check if grpcio is installed
source /opt/refinet/venv/bin/activate
python3 -c "import grpc; print('gRPC available')"
# If not installed: pip install grpcio
# The API will start fine without it (graceful degradation)
```

### SMTP bridge not starting
```bash
# Check if enabled in .env
grep SMTP_ENABLED /opt/refinet/app/.env
# Should be: SMTP_ENABLED=true
# Check if aiosmtpd is installed:
python3 -c "import aiosmtpd; print('aiosmtpd available')"
```

### Certbot fails
```bash
# Verify DNS is pointing to this server first
dig api.refinet.io +short
# Must return this server's public IP
# Then retry:
sudo certbot --nginx -d api.refinet.io -d app.refinet.io
```

### Oracle Cloud iptables blocking traffic
```bash
sudo iptables -L INPUT -n --line-numbers
# Ensure ports 80 and 443 are ACCEPT before the REJECT rule
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

### Sentence-transformers model download
```bash
# The first startup may be slow as it downloads the embedding model
# Check logs for progress:
sudo journalctl -u refinet-api -f
# If download fails behind a proxy, pre-download:
source /opt/refinet/venv/bin/activate
python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

---

## Product Subdomains

REFINET Cloud serves as a central platform for multiple products, each on its own subdomain:

| Subdomain | Product | Directory |
|-----------|---------|-----------|
| `infrastructure.refinet.io` | REFINET Pillars | `/opt/refinet/products/pillars/out` |
| `browser.refinet.io` | REFINET Browser | `/opt/refinet/products/browser/out` |

### Deploy a Product

Products are tracked in `products.json`. To deploy a product from its GitHub repo:

```bash
# Deploy by name (uses repo URL from products.json)
sudo bash /opt/refinet/app/scripts/deploy-product.sh pillars

# Or specify repo explicitly
sudo bash /opt/refinet/app/scripts/deploy-product.sh pillars https://github.com/org/refinet-pillars main
```

The script clones/pulls the repo, installs dependencies, builds, copies output to the serving directory, and reloads nginx.

### Add a New Product

1. Add entry to `products.json` with name, subdomain, repo URL, build command
2. Add `server {}` block in `nginx/refinet.conf`
3. Create directories: `mkdir -p /opt/refinet/products/<name>/{repo,out}`
4. Add DNS A record: `<subdomain> → <PUBLIC_IP>`
5. Get TLS cert: `sudo certbot --nginx -d <subdomain>.refinet.io`
6. Deploy: `sudo bash scripts/deploy-product.sh <name>`

---

## Step 11: Set Up Autonomous Agent Pipeline (Optional)

The platform includes a zero-cost autonomous agent pipeline that can monitor health, run maintenance, and send admin email alerts without any paid API calls.

### 11.1 Verify Prerequisites

```bash
# Claude Code CLI (primary — highest quality)
claude --version

# Ollama (secondary — local CPU, optional)
curl http://localhost:11434/api/tags

# BitNet (tertiary — already running via refinet-bitnet service)
curl http://localhost:8080/health

# Gemini Flash (quaternary — set GEMINI_API_KEY in .env for free tier access)
```

### 11.2 Run Initial Health Check

```bash
cd /opt/refinet/app
source /opt/refinet/venv/bin/activate

# Run comprehensive health check
python3 skills/refinet-platform-ops/scripts/health_check.py --email --always
```

### 11.3 Set Up Cron for Autonomous Monitoring

```bash
# Edit crontab
crontab -e

# Add these entries:
# Heartbeat health check every 5 minutes
*/5 * * * * cd /opt/refinet/app && ./skills/refinet-platform-ops/scripts/run_agent.sh platform-ops "Run health check. If any subsystem fails, send HEALTH alert."

# Daily platform summary at 06:00 UTC
0 6 * * * cd /opt/refinet/app && ./skills/refinet-platform-ops/scripts/run_agent.sh platform-ops "Compile 24h platform summary: requests served, agents run, errors. Email admin."

# Weekly full audit on Monday at 06:00 UTC
0 6 * * 1 cd /opt/refinet/app && ./skills/refinet-platform-ops/scripts/run_agent.sh platform-ops "Full platform audit: DB size, memory usage, certificate expiry, chain listener health. Email detailed report."
```

### 11.4 Configure Admin Email

Ensure these are set in `.env`:
```bash
ADMIN_EMAIL=admin@refinet.io     # Alert recipient
SMTP_HOST=127.0.0.1              # Local SMTP bridge
SMTP_PORT=8025                   # REFINET SMTP bridge port
MAIL_FROM=groot@refinet.io       # Sender identity
SMTP_ENABLED=true                # Enable SMTP bridge
```

### 11.5 Verify Agent Memory Directories

```bash
ls -la /opt/refinet/app/memory/
# Should show: working/ episodic/ semantic/ procedural/ (each with .gitkeep)
```

Agent run results are written to `memory/episodic/{agent_name}.jsonl` and working state to `memory/working/{agent_name}.json`.

### 11.6 Install Knowledge Curator Cron (Optional)

```bash
sudo bash /opt/refinet/app/scripts/install_knowledge_curator_cron.sh
```

This installs 3 cron entries: 6-hourly orphan repair + CAG sync, daily embedding benchmark, daily knowledge digest.

### 11.7 Install Contract Watcher Cron (Optional)

```bash
sudo bash /opt/refinet/app/scripts/install_contract_watcher_cron.sh
```

This installs 4 cron entries: 15-minute ABI scan, 4-hourly activity check, 12-hourly bridge correlation, weekly chain intelligence report.

### 11.8 Verify All Agent Crons

```bash
crontab -l | grep "REFINET"
# Should show entries for REFINET-KNOWLEDGE and REFINET-CHAIN
```
