#!/bin/bash
# =============================================================================
# REFINET Cloud — BitNet Start
# Launches the BitNet inference server (llama-server)
# =============================================================================

BITNET_DIR="/opt/refinet/bitnet"
MODEL_PATH="${BITNET_DIR}/models/BitNet-b1.58-2B-4T/ggml-model-i2_s.gguf"

if [ ! -f "${BITNET_DIR}/llama-server" ]; then
    echo "ERROR: llama-server not found. Run setup.sh first."
    exit 1
fi

if [ ! -f "${MODEL_PATH}" ]; then
    echo "ERROR: Model not found at ${MODEL_PATH}. Run setup.sh first."
    exit 1
fi

echo "Starting BitNet inference server..."
echo "  Host: 127.0.0.1:8080"
echo "  Model: BitNet b1.58 2B4T"
echo "  Context: 2048 tokens"
echo "  Threads: 4"

exec "${BITNET_DIR}/llama-server" \
    -m "${MODEL_PATH}" \
    --host 127.0.0.1 \
    --port 8080 \
    -c 2048 \
    -t 4 \
    --log-disable
