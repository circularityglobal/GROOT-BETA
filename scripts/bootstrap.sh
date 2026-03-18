#!/bin/bash
# =============================================================================
# REFINET Cloud — Bootstrap Script
# Idempotent server setup for Ubuntu 22.04 ARM64 (Oracle Cloud ARM A1 Flex)
# Run as root: sudo bash scripts/bootstrap.sh
# =============================================================================

set -euo pipefail

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  REFINET Cloud — Bootstrap                               ║"
echo "║  Grass Root Project Intelligence                         ║"
echo "╚══════════════════════════════════════════════════════════╝"

# ── System packages ────────────────────────────────────────────────

echo "[1/10] Updating system packages..."
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq \
    build-essential cmake git curl wget unzip \
    python3 python3-pip python3-venv \
    nginx certbot python3-certbot-nginx \
    fail2ban ufw \
    sqlite3 jq \
    nodejs npm

# ── Firewall ───────────────────────────────────────────────────────

echo "[2/10] Configuring firewall..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
ufw --force enable

# ── Fail2ban ───────────────────────────────────────────────────────

echo "[3/10] Configuring fail2ban..."
cat > /etc/fail2ban/jail.local << 'EOF'
[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 5
bantime = 3600
findtime = 600
EOF
systemctl enable fail2ban
systemctl restart fail2ban

# ── Application directory ─────────────────────────────────────────

echo "[4/10] Setting up application directory..."
mkdir -p /opt/refinet/data
mkdir -p /opt/refinet/app
mkdir -p /opt/refinet/logs

# Product subdomain directories
mkdir -p /opt/refinet/products/pillars/{repo,out}
mkdir -p /opt/refinet/products/browser/{repo,out}

# Copy placeholder pages if no content exists yet
if [ -f /opt/refinet/app/products/pillars/index.html ] && [ ! -f /opt/refinet/products/pillars/out/index.html ]; then
    cp /opt/refinet/app/products/pillars/index.html /opt/refinet/products/pillars/out/
fi
if [ -f /opt/refinet/app/products/browser/index.html ] && [ ! -f /opt/refinet/products/browser/out/index.html ]; then
    cp /opt/refinet/app/products/browser/index.html /opt/refinet/products/browser/out/
fi

# ── Python environment ─────────────────────────────────────────────

echo "[5/10] Setting up Python environment..."
if [ ! -d /opt/refinet/venv ]; then
    python3 -m venv /opt/refinet/venv
fi
source /opt/refinet/venv/bin/activate

pip install --upgrade pip
pip install \
    fastapi uvicorn[standard] \
    sqlalchemy pydantic pydantic-settings \
    argon2-cffi passlib[argon2] \
    pyotp qrcode[pil] \
    PyJWT cryptography \
    web3 eth-account \
    httpx slowapi \
    python-dotenv

# ── BitNet setup ───────────────────────────────────────────────────

echo "[6/10] Setting up BitNet inference..."
if [ ! -d /opt/refinet/bitnet ]; then
    cd /opt/refinet
    git clone --depth 1 https://github.com/microsoft/BitNet.git bitnet-src
    cd bitnet-src
    
    # Build llama.cpp with BitNet support for ARM
    pip install -r requirements.txt
    python setup_env.py --hf-repo microsoft/BitNet-b1.58-2B-4T -q i2_s
    
    mkdir -p /opt/refinet/bitnet
    cp -r build/bin/* /opt/refinet/bitnet/ 2>/dev/null || true
    cp -r models/* /opt/refinet/bitnet/models/ 2>/dev/null || true
fi

# ── Systemd services ──────────────────────────────────────────────

echo "[7/10] Creating systemd services..."

cat > /etc/systemd/system/refinet-bitnet.service << 'EOF'
[Unit]
Description=REFINET BitNet Inference Server
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/refinet/bitnet
ExecStart=/opt/refinet/bitnet/llama-server \
    -m /opt/refinet/bitnet/models/BitNet-b1.58-2B-4T/ggml-model-i2_s.gguf \
    --host 127.0.0.1 \
    --port 8080 \
    -c 2048 \
    -t 4 \
    --log-disable
Restart=always
RestartSec=5
Environment=LLAMA_ARG_HOST=127.0.0.1
Environment=LLAMA_ARG_PORT=8080

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/refinet-api.service << 'EOF'
[Unit]
Description=REFINET Cloud API Server
After=network.target refinet-bitnet.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/refinet/app
EnvironmentFile=/opt/refinet/app/.env
ExecStart=/opt/refinet/venv/bin/uvicorn api.main:app \
    --host 127.0.0.1 \
    --port 8000 \
    --workers 2 \
    --log-level info
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable refinet-bitnet refinet-api

# ── Database initialization ────────────────────────────────────────

echo "[8/10] Initializing databases..."
chown -R www-data:www-data /opt/refinet/data

# ── Cron jobs ──────────────────────────────────────────────────────

echo "[9/10] Setting up cron jobs..."
cat > /etc/cron.d/refinet << 'EOF'
# Telemetry cleanup — delete records older than 7 days (daily at 3am)
0 3 * * * www-data /opt/refinet/venv/bin/python3 -c "
import sys; sys.path.insert(0, '/opt/refinet/app')
from api.database import get_public_db
from api.services.device_telemetry import cleanup_old_telemetry
with get_public_db() as db:
    deleted = cleanup_old_telemetry(db)
    print(f'Cleaned {deleted} old telemetry records')
" >> /opt/refinet/logs/cleanup.log 2>&1

# SIWE nonce cleanup (every hour)
0 * * * * www-data /opt/refinet/venv/bin/python3 -c "
import sys; sys.path.insert(0, '/opt/refinet/app')
from api.database import get_public_db
from api.auth.siwe import cleanup_expired_nonces
with get_public_db() as db:
    deleted = cleanup_expired_nonces(db)
    print(f'Cleaned {deleted} expired nonces')
" >> /opt/refinet/logs/cleanup.log 2>&1

# API key daily counter reset (midnight UTC)
0 0 * * * www-data sqlite3 /opt/refinet/data/public.db "UPDATE api_keys SET requests_today = 0, last_reset_date = date('now')" >> /opt/refinet/logs/cleanup.log 2>&1
EOF

# ── Final permissions ──────────────────────────────────────────────

echo "[10/10] Setting permissions..."
chown -R www-data:www-data /opt/refinet
chmod 700 /opt/refinet/data
chmod 600 /opt/refinet/app/.env 2>/dev/null || true

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Bootstrap complete!                                     ║"
echo "║                                                          ║"
echo "║  Next steps:                                             ║"
echo "║  1. Copy your code to /opt/refinet/app/                  ║"
echo "║  2. Copy .env.example to /opt/refinet/app/.env           ║"
echo "║  3. Fill in all secret values in .env                    ║"
echo "║  4. Run: sudo systemctl start refinet-bitnet             ║"
echo "║  5. Run: sudo systemctl start refinet-api                ║"
echo "║  6. Configure Nginx (see nginx/refinet.conf)             ║"
echo "║  7. Run certbot for TLS (all subdomains)                 ║"
echo "║  8. Deploy products: deploy-product.sh <name> <repo>     ║"
echo "╚══════════════════════════════════════════════════════════╝"
