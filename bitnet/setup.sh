#!/bin/bash
# =============================================================================
# REFINET Cloud — BitNet Setup
# Downloads and builds BitNet b1.58 2B4T for ARM inference
# =============================================================================

set -euo pipefail

BITNET_DIR="/opt/refinet/bitnet"
MODEL_DIR="${BITNET_DIR}/models"

echo "Setting up BitNet b1.58 2B4T..."

# Check if already set up
if [ -f "${BITNET_DIR}/llama-server" ]; then
    echo "BitNet already built. To rebuild, delete ${BITNET_DIR} first."
    exit 0
fi

mkdir -p "${BITNET_DIR}" "${MODEL_DIR}"

# Clone BitNet repository
cd /tmp
if [ ! -d "BitNet" ]; then
    git clone --depth 1 https://github.com/microsoft/BitNet.git
fi

cd BitNet

# Install Python dependencies
pip install -r requirements.txt

# Build with BitNet optimizations for ARM
# This uses the setup_env.py script which handles:
# - Building llama.cpp with BitNet kernel support
# - Downloading the model from HuggingFace
# - Quantizing to i2_s format (optimal for 1-bit inference)
python setup_env.py \
    --hf-repo microsoft/BitNet-b1.58-2B-4T \
    -q i2_s

# Copy built binaries
cp -r build/bin/* "${BITNET_DIR}/" 2>/dev/null || true

# Copy model files
cp -r models/* "${MODEL_DIR}/" 2>/dev/null || true

# Verify
if [ -f "${BITNET_DIR}/llama-server" ]; then
    echo ""
    echo "BitNet setup complete!"
    echo "Binary: ${BITNET_DIR}/llama-server"
    echo "Model:  ${MODEL_DIR}/"
    echo ""
    echo "Test with:"
    echo "  ${BITNET_DIR}/llama-server -m ${MODEL_DIR}/BitNet-b1.58-2B-4T/ggml-model-i2_s.gguf --host 127.0.0.1 --port 8080 -c 2048 -t 4"
else
    echo "ERROR: llama-server binary not found after build."
    echo "Check build output above for errors."
    exit 1
fi
