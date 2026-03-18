#!/bin/bash
# =============================================================================
# REFINET Cloud — BitNet Local Start (macOS ARM)
# Launches the BitNet inference server for local development.
# Existing start.sh (Linux production) is untouched.
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN_DIR="${SCRIPT_DIR}/bin"
MODEL_PATH="${SCRIPT_DIR}/models/BitNet-b1.58-2B-4T/ggml-model-i2_s.gguf"
SERVER_BIN="${BIN_DIR}/llama-server"

# ── Validate binary and model ───────────────────────────────────────────────

if [ ! -f "${SERVER_BIN}" ]; then
    echo "ERROR: llama-server not found at ${SERVER_BIN}"
    echo "Run setup first:  bash bitnet/setup_local.sh"
    exit 1
fi

if [ ! -f "${MODEL_PATH}" ]; then
    echo "ERROR: Model not found at ${MODEL_PATH}"
    echo "Run setup first:  bash bitnet/setup_local.sh"
    exit 1
fi

# ── Check port availability ─────────────────────────────────────────────────

PORT="${BITNET_PORT:-8080}"

if lsof -i ":${PORT}" &>/dev/null; then
    echo "ERROR: Port ${PORT} is already in use."
    echo "Either stop the existing process or set a different port:"
    echo "  BITNET_PORT=8081 bash bitnet/start_local.sh"
    exit 1
fi

# ── Auto-detect performance cores ───────────────────────────────────────────

PERF_CORES=$(sysctl -n hw.perflevel0.logicalcpu 2>/dev/null || echo 4)
THREADS="${BITNET_THREADS:-${PERF_CORES}}"
HOST="${BITNET_HOST_ADDR:-127.0.0.1}"
CONTEXT="${BITNET_CONTEXT:-2048}"

# ── Launch ──────────────────────────────────────────────────────────────────

echo "Starting BitNet inference server (local dev)..."
echo "  Host:    ${HOST}:${PORT}"
echo "  Model:   BitNet b1.58 2B4T"
echo "  Context: ${CONTEXT} tokens"
echo "  Threads: ${THREADS} (performance cores)"
echo ""
echo "  API endpoint: http://${HOST}:${PORT}/completion"
echo "  Health check: http://${HOST}:${PORT}/health"
echo ""
echo "  Press Ctrl+C to stop"
echo ""

exec "${SERVER_BIN}" \
    -m "${MODEL_PATH}" \
    --host "${HOST}" \
    --port "${PORT}" \
    -c "${CONTEXT}" \
    -t "${THREADS}" \
    --log-disable
