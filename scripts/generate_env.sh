#!/bin/bash
# =============================================================================
# REFINET Cloud — Production .env Generator
# Generates cryptographically secure secrets for production deployment
# Usage: bash scripts/generate_env.sh > /opt/refinet/app/.env
# =============================================================================

set -euo pipefail

# Accept domain overrides via arguments
API_DOMAIN="${1:-api.refinet.io}"
APP_DOMAIN="${2:-app.refinet.io}"

# Generate secrets
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(64))")
REFRESH_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(64))")
SERVER_PEPPER=$(python3 -c "import secrets; print(secrets.token_hex(64))")
WEBHOOK_SIGNING_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
INTERNAL_DB_ENCRYPTION_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
ADMIN_API_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
QUICKCAST_KEY=$(python3 -c "import secrets; print('rf_qc_' + secrets.token_hex(16))")
AGENTOS_KEY=$(python3 -c "import secrets; print('rf_ao_' + secrets.token_hex(16))")

cat << EOF
# =============================================================================
# REFINET Cloud — Production Environment
# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# NEVER commit this file to version control
# =============================================================================

# Core identity
REFINET_ENV=production
REFINET_DOMAIN=${API_DOMAIN}
REFINET_FRONTEND_URL=https://${APP_DOMAIN}

# Security — all unique, cryptographically random
SECRET_KEY=${SECRET_KEY}
REFRESH_SECRET=${REFRESH_SECRET}
SERVER_PEPPER=${SERVER_PEPPER}
WEBHOOK_SIGNING_KEY=${WEBHOOK_SIGNING_KEY}
INTERNAL_DB_ENCRYPTION_KEY=${INTERNAL_DB_ENCRYPTION_KEY}
ADMIN_API_SECRET=${ADMIN_API_SECRET}

# JWT
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=30

# Databases
PUBLIC_DB_URL=sqlite:////opt/refinet/data/public.db
INTERNAL_DB_URL=sqlite:////opt/refinet/data/internal.db

# BitNet sidecar
BITNET_HOST=http://127.0.0.1:8080

# Rate limits
RATE_LIMIT_PER_MINUTE=60
FREE_TIER_DAILY_REQUESTS=100
MAX_REQUEST_BODY_BYTES=10485760

# SIWE
SIWE_DOMAIN=${API_DOMAIN}
SIWE_CHAIN_ID=1
SIWE_STATEMENT=Sign in to REFINET Cloud. Your Ethereum address is used as a cryptographic key component.

# Products (embedded build keys)
QUICKCAST_BUILD_KEY=${QUICKCAST_KEY}
AGENTOS_BUILD_KEY=${AGENTOS_KEY}
EOF
