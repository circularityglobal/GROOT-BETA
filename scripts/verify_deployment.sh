#!/bin/bash
# =============================================================================
# REFINET Cloud — Deployment Verification
# Run on the server after deployment to verify all services are healthy
# Usage: bash scripts/verify_deployment.sh [domain]
# =============================================================================

set -euo pipefail

DOMAIN="${1:-localhost}"
API_URL="https://${DOMAIN}"
PASS=0
FAIL=0

check() {
    local name="$1"
    local result="$2"
    if [ "$result" = "0" ]; then
        echo "  [PASS] $name"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] $name"
        FAIL=$((FAIL + 1))
    fi
}

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  REFINET Cloud — Deployment Verification                ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ── 1. System Services ─────────────────────────────────────────────

echo "1. System Services"
systemctl is-active --quiet refinet-bitnet 2>/dev/null
check "refinet-bitnet service running" $?

systemctl is-active --quiet refinet-api 2>/dev/null
check "refinet-api service running" $?

systemctl is-active --quiet nginx 2>/dev/null
check "nginx service running" $?

# ── 2. Port Checks ────────────────────────────────────────────────

echo ""
echo "2. Port Checks"
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/health 2>/dev/null | grep -q "200"
check "BitNet responding on :8080" $?

curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health 2>/dev/null | grep -q "200"
check "FastAPI responding on :8000" $?

# ── 3. API Health ──────────────────────────────────────────────────

echo ""
echo "3. API Endpoints"

HEALTH=$(curl -s http://127.0.0.1:8000/health 2>/dev/null)
echo "$HEALTH" | python3 -c "import sys, json; d=json.load(sys.stdin); exit(0 if d.get('status')=='ok' else 1)" 2>/dev/null
check "Health endpoint returns status=ok" $?

echo "$HEALTH" | python3 -c "import sys, json; d=json.load(sys.stdin); exit(0 if d.get('inference')=='available' else 1)" 2>/dev/null
check "BitNet inference available" $?

MODELS=$(curl -s http://127.0.0.1:8000/v1/models 2>/dev/null)
echo "$MODELS" | python3 -c "import sys, json; d=json.load(sys.stdin); exit(0 if d['data'][0]['id']=='bitnet-b1.58-2b' else 1)" 2>/dev/null
check "Models endpoint returns bitnet-b1.58-2b" $?

# Inference without auth should 401
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:8000/v1/chat/completions -H "Content-Type: application/json" -d '{"messages":[{"role":"user","content":"hi"}]}' 2>/dev/null)
[ "$STATUS" = "401" ]
check "Inference without auth returns 401" $?

# ── 4. Database Files ──────────────────────────────────────────────

echo ""
echo "4. Database"

[ -f /opt/refinet/data/public.db ]
check "public.db exists" $?

[ -f /opt/refinet/data/internal.db ]
check "internal.db exists" $?

PUB_TABLES=$(sqlite3 /opt/refinet/data/public.db ".tables" 2>/dev/null | wc -w)
[ "$PUB_TABLES" -ge 12 ]
check "Public DB has 12+ tables (found: $PUB_TABLES)" $?

INT_TABLES=$(sqlite3 /opt/refinet/data/internal.db ".tables" 2>/dev/null | wc -w)
[ "$INT_TABLES" -ge 6 ]
check "Internal DB has 6+ tables (found: $INT_TABLES)" $?

# ── 5. Files & Permissions ────────────────────────────────────────

echo ""
echo "5. Files & Permissions"

[ -f /opt/refinet/app/.env ]
check ".env file exists" $?

[ "$(stat -c %a /opt/refinet/app/.env 2>/dev/null || echo '0')" = "600" ]
check ".env has 600 permissions" $?

[ -f /opt/refinet/bitnet/llama-server ]
check "llama-server binary exists" $?

[ -f /opt/refinet/bitnet/models/BitNet-b1.58-2B-4T/ggml-model-i2_s.gguf ]
check "BitNet model file exists" $?

# ── 6. Frontend ────────────────────────────────────────────────────

echo ""
echo "6. Frontend"

[ -f /opt/refinet/frontend/out/index.html ]
check "Frontend build exists (index.html)" $?

# ── 7. TLS (only if domain is not localhost) ──────────────────────

if [ "$DOMAIN" != "localhost" ]; then
    echo ""
    echo "7. TLS"

    [ -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]
    check "TLS certificate exists for ${DOMAIN}" $?
fi

# ── 8. Firewall ───────────────────────────────────────────────────

echo ""
echo "8. Security"

ufw status 2>/dev/null | grep -q "Status: active"
check "UFW firewall active" $?

systemctl is-active --quiet fail2ban 2>/dev/null
check "fail2ban running" $?

# ── Summary ───────────────────────────────────────────────────────

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  Results: ${PASS} passed, ${FAIL} failed"
if [ "$FAIL" -eq 0 ]; then
    echo "  Status: ALL CHECKS PASSED"
else
    echo "  Status: ${FAIL} CHECK(S) FAILED — review above"
fi
echo "════════════════════════════════════════════════════════════"

exit $FAIL
