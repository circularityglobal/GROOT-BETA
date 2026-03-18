#!/bin/bash
# =============================================================================
# REFINET Cloud — Deploy Script
# Pull latest code and restart services
# =============================================================================

set -euo pipefail

APP_DIR="/opt/refinet/app"

echo "Deploying REFINET Cloud..."

cd "${APP_DIR}"

# Pull latest
git pull origin main

# Install any new Python dependencies
source /opt/refinet/venv/bin/activate
pip install -r requirements.txt --quiet

# Build frontend
cd frontend
npm install --production
npm run build
cp -r out/* /opt/refinet/frontend/out/ 2>/dev/null || true
cd ..

# Restart services
sudo systemctl restart refinet-api
echo "API server restarted"

# Don't restart BitNet unless explicitly requested
# sudo systemctl restart refinet-bitnet

# ── Deploy products with configured repos ─────────────────────────
if command -v jq &>/dev/null && [ -f "$APP_DIR/products.json" ]; then
    echo ""
    echo "Checking product deployments..."
    PRODUCT_COUNT=$(jq '.products | length' "$APP_DIR/products.json")
    for i in $(seq 0 $((PRODUCT_COUNT - 1))); do
        PNAME=$(jq -r ".products[$i].name" "$APP_DIR/products.json")
        PREPO=$(jq -r ".products[$i].repo" "$APP_DIR/products.json")
        if [[ -n "$PREPO" && "$PREPO" != "null" && "$PREPO" != "" ]]; then
            echo "Deploying product: $PNAME"
            bash "$APP_DIR/scripts/deploy-product.sh" "$PNAME"
        else
            echo "Skipping $PNAME (no repo configured)"
        fi
    done
fi

echo ""
echo "Deploy complete."
echo "Check status: sudo systemctl status refinet-api"
