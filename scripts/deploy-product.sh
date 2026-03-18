#!/usr/bin/env bash
# =============================================================================
# REFINET Cloud — Product Deployment Script
# Deploys an external repo to a product subdomain.
#
# Usage:
#   deploy-product.sh <product-name> [git-repo-url] [branch]
#
# Examples:
#   deploy-product.sh pillars https://github.com/org/refinet-pillars main
#   deploy-product.sh browser   # uses repo/branch from products.json
#
# Directory layout:
#   /opt/refinet/products/<name>/repo/   — git clone
#   /opt/refinet/products/<name>/out/    — built static files (served by nginx)
# =============================================================================

set -euo pipefail

PRODUCTS_DIR="/opt/refinet/products"
PROJECT_ROOT="/opt/refinet/app"

# ── Args ──────────────────────────────────────────────────────────────────────
PRODUCT_NAME="${1:-}"
REPO_URL="${2:-}"
BRANCH="${3:-main}"

if [[ -z "$PRODUCT_NAME" ]]; then
    echo "Error: product name required"
    echo "Usage: deploy-product.sh <product-name> [git-repo-url] [branch]"
    exit 1
fi

PRODUCT_DIR="$PRODUCTS_DIR/$PRODUCT_NAME"
REPO_DIR="$PRODUCT_DIR/repo"
OUT_DIR="$PRODUCT_DIR/out"

# ── Resolve repo URL from products.json if not provided ──────────────────────
if [[ -z "$REPO_URL" ]]; then
    if command -v jq &>/dev/null && [[ -f "$PROJECT_ROOT/products.json" ]]; then
        REPO_URL=$(jq -r --arg name "$PRODUCT_NAME" \
            '.products[] | select(.name == $name) | .repo' \
            "$PROJECT_ROOT/products.json")
        BRANCH=$(jq -r --arg name "$PRODUCT_NAME" \
            '.products[] | select(.name == $name) | .branch // "main"' \
            "$PROJECT_ROOT/products.json")
    fi

    if [[ -z "$REPO_URL" || "$REPO_URL" == "null" || "$REPO_URL" == "" ]]; then
        echo "Error: no repo URL provided and none found in products.json for '$PRODUCT_NAME'"
        exit 1
    fi
fi

echo "═══════════════════════════════════════════════════════════"
echo "  Deploying: $PRODUCT_NAME"
echo "  Repo:      $REPO_URL"
echo "  Branch:    $BRANCH"
echo "  Target:    $OUT_DIR"
echo "═══════════════════════════════════════════════════════════"

# ── Ensure directories exist ─────────────────────────────────────────────────
mkdir -p "$REPO_DIR" "$OUT_DIR"

# ── Clone or pull ────────────────────────────────────────────────────────────
if [[ -d "$REPO_DIR/.git" ]]; then
    echo "[1/5] Pulling latest from $BRANCH..."
    cd "$REPO_DIR"
    git fetch origin
    git checkout "$BRANCH"
    git pull origin "$BRANCH"
else
    echo "[1/5] Cloning $REPO_URL..."
    git clone --branch "$BRANCH" --depth 1 "$REPO_URL" "$REPO_DIR"
    cd "$REPO_DIR"
fi

# ── Detect and install dependencies ──────────────────────────────────────────
echo "[2/5] Installing dependencies..."
if [[ -f "package.json" ]]; then
    npm install --production 2>&1 | tail -3
elif [[ -f "requirements.txt" ]]; then
    pip install -r requirements.txt --quiet
elif [[ -f "Cargo.toml" ]]; then
    cargo build --release
else
    echo "  No recognized dependency file found, skipping."
fi

# ── Build ────────────────────────────────────────────────────────────────────
echo "[3/5] Building..."
BUILD_CMD=""
if command -v jq &>/dev/null && [[ -f "$PROJECT_ROOT/products.json" ]]; then
    BUILD_CMD=$(jq -r --arg name "$PRODUCT_NAME" \
        '.products[] | select(.name == $name) | .build_cmd // ""' \
        "$PROJECT_ROOT/products.json")
fi

if [[ -n "$BUILD_CMD" && "$BUILD_CMD" != "null" ]]; then
    eval "$BUILD_CMD"
elif [[ -f "package.json" ]]; then
    npm run build 2>&1
else
    echo "  No build command found, skipping."
fi

# ── Detect output directory and copy ─────────────────────────────────────────
echo "[4/5] Copying build output to $OUT_DIR..."
BUILD_OUT_DIR=""
if command -v jq &>/dev/null && [[ -f "$PROJECT_ROOT/products.json" ]]; then
    BUILD_OUT_DIR=$(jq -r --arg name "$PRODUCT_NAME" \
        '.products[] | select(.name == $name) | .out_dir // "out"' \
        "$PROJECT_ROOT/products.json")
fi
BUILD_OUT_DIR="${BUILD_OUT_DIR:-out}"

if [[ -d "$REPO_DIR/$BUILD_OUT_DIR" ]]; then
    rm -rf "${OUT_DIR:?}"/*
    cp -r "$REPO_DIR/$BUILD_OUT_DIR/"* "$OUT_DIR/"
elif [[ -d "$REPO_DIR/dist" ]]; then
    rm -rf "${OUT_DIR:?}"/*
    cp -r "$REPO_DIR/dist/"* "$OUT_DIR/"
elif [[ -d "$REPO_DIR/build" ]]; then
    rm -rf "${OUT_DIR:?}"/*
    cp -r "$REPO_DIR/build/"* "$OUT_DIR/"
else
    echo "  Warning: no build output directory found ($BUILD_OUT_DIR, dist, build)"
    echo "  Copying entire repo as fallback."
    rm -rf "${OUT_DIR:?}"/*
    cp -r "$REPO_DIR/"* "$OUT_DIR/"
fi

# ── Set permissions and reload nginx ─────────────────────────────────────────
echo "[5/5] Setting permissions and reloading nginx..."
chown -R www-data:www-data "$PRODUCT_DIR"
nginx -t && systemctl reload nginx

echo ""
echo "✓ $PRODUCT_NAME deployed successfully"
echo "  Serving from: $OUT_DIR"
echo ""
