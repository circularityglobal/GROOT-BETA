#!/bin/bash
# =============================================================================
# REFINET Cloud — BitNet Local Setup (macOS ARM)
# Builds BitNet b1.58 2B4T for local development on Apple Silicon.
# Existing setup.sh (Linux production) is untouched.
# =============================================================================

set -euo pipefail

# ── Paths (relative to this script) ──────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_DIR="${SCRIPT_DIR}/local"
BIN_DIR="${SCRIPT_DIR}/bin"
MODEL_DIR="${SCRIPT_DIR}/models"
VENV_DIR="${LOCAL_DIR}/venv"
MODEL_GGUF="${MODEL_DIR}/BitNet-b1.58-2B-4T/ggml-model-i2_s.gguf"

# ── Platform guard ───────────────────────────────────────────────────────────

if [ "$(uname -s)" != "Darwin" ] || [ "$(uname -m)" != "arm64" ]; then
    echo "ERROR: This script is for macOS ARM (Apple Silicon) only."
    echo "For Linux ARM64, use setup.sh instead."
    exit 1
fi

# ── Prerequisites ────────────────────────────────────────────────────────────

echo "Checking prerequisites..."

for cmd in cmake git clang++; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "ERROR: $cmd not found. Install Xcode Command Line Tools and Homebrew cmake:"
        echo "  xcode-select --install"
        echo "  brew install cmake"
        exit 1
    fi
done

# Find a suitable Python (prefer Homebrew 3.12/3.11, fall back to system)
PYTHON_BIN=""
for candidate in /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3.11 /opt/homebrew/bin/python3 python3; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON_BIN="$candidate"
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "ERROR: Python 3.9+ not found."
    exit 1
fi

PY_VERSION=$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "  Python: $PYTHON_BIN ($PY_VERSION)"
echo "  cmake:  $(cmake --version | head -1)"
echo "  clang:  $(clang++ --version | head -1)"

# ── Idempotent — skip if already built ───────────────────────────────────────

if [ -f "${BIN_DIR}/llama-server" ] && [ -f "${MODEL_GGUF}" ]; then
    echo ""
    echo "BitNet already built."
    echo "  Binary: ${BIN_DIR}/llama-server"
    echo "  Model:  ${MODEL_GGUF}"
    echo ""
    echo "To rebuild, delete bitnet/local/ and bitnet/bin/ then re-run."
    exit 0
fi

# ── Prefer Homebrew LLVM 18 if available ─────────────────────────────────────

LLVM_PREFIX="/opt/homebrew/opt/llvm@18"
if [ -x "${LLVM_PREFIX}/bin/clang" ]; then
    echo ""
    echo "Found LLVM 18 — using it for build (recommended for BitNet kernels)."
    export PATH="${LLVM_PREFIX}/bin:${PATH}"
    export CC="${LLVM_PREFIX}/bin/clang"
    export CXX="${LLVM_PREFIX}/bin/clang++"
else
    echo ""
    echo "LLVM 18 not found — using Apple Clang (should work for i2_s quantization)."
    echo "If the build hangs, install LLVM 18: brew install llvm@18"
fi

# ── Create directories ──────────────────────────────────────────────────────

mkdir -p "${LOCAL_DIR}" "${BIN_DIR}" "${MODEL_DIR}"

# ── Python venv (isolated from system) ──────────────────────────────────────

echo ""
echo "Setting up Python build environment..."

if [ ! -d "${VENV_DIR}" ]; then
    "$PYTHON_BIN" -m venv "${VENV_DIR}"
fi
source "${VENV_DIR}/bin/activate"
pip install --upgrade pip --quiet

# ── Clone BitNet ─────────────────────────────────────────────────────────────

echo ""
echo "Cloning Microsoft/BitNet..."

cd "${LOCAL_DIR}"
if [ ! -d "BitNet" ]; then
    git clone --depth 1 https://github.com/microsoft/BitNet.git
    cd BitNet
    git submodule update --init --recursive
else
    cd BitNet
fi

# ── Patch: fix compatibility with BitNet-b1.58-2B-4T model ──────────────────
# The HuggingFace model has three incompatibilities with the repo's converter:
# 1. Architecture name casing: "BitNetForCausalLM" vs "BitnetForCausalLM"
# 2. Tokenizer format: PreTrainedTokenizerFast (no tokenizer.model file)
# 3. Weight format: packed uint8 with weight_scale tensors (not raw floats)
# We apply all patches via a single Python script for reliability.

CONVERTER="utils/convert-hf-to-gguf-bitnet.py"
if [ -f "${CONVERTER}" ]; then
    echo "Checking converter compatibility..."
    python3 << 'PATCH_EOF'
import sys

converter_path = "utils/convert-hf-to-gguf-bitnet.py"
with open(converter_path, "r") as f:
    content = f.read()

patched = False

# Patch 1: architecture name — add "BitNetForCausalLM" registration
if "BitNetForCausalLM" not in content:
    content = content.replace(
        '@Model.register("BitnetForCausalLM")',
        '@Model.register("BitnetForCausalLM", "BitNetForCausalLM")'
    )
    print("  Patched: architecture name casing")
    patched = True

# Patch 2: tokenizer fallback (sentencepiece -> llama_hf -> gpt2)
old_vocab = """    def set_vocab(self):
        self._set_vocab_sentencepiece()"""
new_vocab = """    def set_vocab(self):
        try:
            self._set_vocab_sentencepiece()
        except FileNotFoundError:
            try:
                self._set_vocab_llama_hf()
            except (FileNotFoundError, TypeError):
                self._set_vocab_gpt2()"""
if old_vocab in content:
    content = content.replace(old_vocab, new_vocab)
    print("  Patched: tokenizer fallback")
    patched = True

# Patch 3: weight_scale handling in BitnetModel
# The 2B-4T model stores ternary weights packed as uint8 with separate
# weight_scale tensors. BitnetModel.modify_tensors must skip them, and
# write_tensors must unpack them (same approach as LlamaModel).
if "class BitnetModel" in content and "scale_map" not in content.split("class BitnetModel")[1].split("class ")[0]:
    # Add weight_scale skip to modify_tensors
    old_modify = '''    def modify_tensors(self, data_torch: Tensor, name: str, bid: int | None) -> Iterable[tuple[str, Tensor]]:
        # quant weight to i2 (in fp16)
        if name.endswith(("q_proj.weight", "k_proj.weight", "v_proj.weight",
                          "down_proj.weight", "up_proj.weight", "gate_proj.weight",
                          "o_proj.weight")):
            data_torch = self.weight_quant(data_torch)

        return [(self.map_tensor_name(name), data_torch)]

    def write_tensors(self):
        max_name_len = max(len(s) for _, s in self.tensor_map.mapping.values()) + len(".weight,")

        for name, data_torch in self.get_tensors():
            # we don't need these
            if name.endswith((".attention.masked_bias", ".attention.bias", ".rotary_emb.inv_freq")):
                continue

            old_dtype = data_torch.dtype

            # convert any unsupported data types to float32
            if data_torch.dtype not in (torch.float16, torch.float32):
                data_torch = data_torch.to(torch.float32)'''
    new_modify = '''    def modify_tensors(self, data_torch: Tensor, name: str, bid: int | None) -> Iterable[tuple[str, Tensor]]:
        # skip weight_scale tensors -- handled in write_tensors
        if name.endswith("weight_scale"):
            return []

        # quant weight to i2 (in fp16)
        if name.endswith(("q_proj.weight", "k_proj.weight", "v_proj.weight",
                          "down_proj.weight", "up_proj.weight", "gate_proj.weight",
                          "o_proj.weight")):
            data_torch = self.weight_quant(data_torch)

        return [(self.map_tensor_name(name), data_torch)]

    def write_tensors(self):
        max_name_len = max(len(s) for _, s in self.tensor_map.mapping.values()) + len(".weight,")

        # First pass: collect weight_scale tensors for packed uint8 weights
        scale_map = dict()
        for name, data_torch in self.get_tensors():
            if name.endswith("weight_scale"):
                data_torch = data_torch.to(torch.float32)
                name = name.replace(".weight_scale", "")
                scale_map[name] = data_torch

        for name, data_torch in self.get_tensors():
            # skip weight_scale tensors (already collected above)
            if name.endswith("weight_scale"):
                continue
            # we don't need these
            if name.endswith((".attention.masked_bias", ".attention.bias", ".rotary_emb.inv_freq")):
                continue

            old_dtype = data_torch.dtype

            # unpack uint8-packed ternary weights using scale map
            if name.replace(".weight", "") in scale_map:
                data_torch = data_torch.to(torch.uint8)
                origin_shape = data_torch.shape
                shift = torch.tensor([0, 2, 4, 6], dtype=torch.uint8).reshape((4, *(1 for _ in range(len(origin_shape)))))
                data_torch = data_torch.unsqueeze(0).expand((4, *origin_shape)) >> shift
                data_torch = data_torch & 3
                data_torch = (data_torch.float() - 1).reshape((origin_shape[0] * 4, *origin_shape[1:]))
                data_torch = data_torch / scale_map[name.replace(".weight", "")].float()

            # convert any unsupported data types to float32
            if data_torch.dtype not in (torch.float16, torch.float32):
                data_torch = data_torch.to(torch.float32)'''
    if old_modify in content:
        content = content.replace(old_modify, new_modify)
        print("  Patched: weight_scale unpacking in BitnetModel")
        patched = True
    else:
        print("  Note: weight_scale patch pattern not found (may already be patched)")

if patched:
    with open(converter_path, "w") as f:
        f.write(content)
    print("  All patches applied.")
else:
    print("  No patches needed.")
PATCH_EOF
fi

# ── Install dependencies ────────────────────────────────────────────────────

echo ""
echo "Installing Python dependencies..."

pip install -r requirements.txt --quiet
pip install 'huggingface_hub[cli]' --quiet

# ── Build + download + quantize ─────────────────────────────────────────────

echo ""
echo "Building BitNet (this will take 10-20 minutes)..."
echo "  - Compiling llama.cpp with BitNet kernel support"
echo "  - Downloading model from HuggingFace (~1-2 GB)"
echo "  - Quantizing to i2_s format"
echo ""

python setup_env.py \
    --hf-repo microsoft/BitNet-b1.58-2B-4T \
    -q i2_s

BUILD_STATUS=$?
if [ $BUILD_STATUS -ne 0 ]; then
    echo ""
    echo "ERROR: Build failed (exit code $BUILD_STATUS)."
    echo ""
    echo "If the build hung or crashed, try installing LLVM 18:"
    echo "  brew install llvm@18"
    echo "Then re-run this script."
    exit 1
fi

# ── Copy binaries ───────────────────────────────────────────────────────────

echo ""
echo "Copying build artifacts..."

for bin_name in llama-server llama-cli llama-quantize; do
    if [ -f "build/bin/${bin_name}" ]; then
        cp "build/bin/${bin_name}" "${BIN_DIR}/"
        echo "  ${BIN_DIR}/${bin_name}"
    fi
done

# ── Copy model ──────────────────────────────────────────────────────────────

if [ -d "models/BitNet-b1.58-2B-4T" ]; then
    mkdir -p "${MODEL_DIR}/BitNet-b1.58-2B-4T"
    cp -r models/BitNet-b1.58-2B-4T/* "${MODEL_DIR}/BitNet-b1.58-2B-4T/"
    echo "  ${MODEL_DIR}/BitNet-b1.58-2B-4T/"
fi

# ── Verify ──────────────────────────────────────────────────────────────────

echo ""

if [ -f "${BIN_DIR}/llama-server" ] && [ -f "${MODEL_GGUF}" ]; then
    echo "============================================"
    echo "  BitNet setup complete!"
    echo "============================================"
    echo ""
    echo "  Binary: ${BIN_DIR}/llama-server"
    echo "  Model:  ${MODEL_GGUF}"
    echo ""
    echo "  Start the server:"
    echo "    bash bitnet/start_local.sh"
    echo ""
    echo "  Or test directly:"
    echo "    ${BIN_DIR}/llama-server -m ${MODEL_GGUF} --host 127.0.0.1 --port 8080 -c 2048 -t 4"
    echo ""
else
    echo "ERROR: Build completed but artifacts are missing."
    [ ! -f "${BIN_DIR}/llama-server" ] && echo "  Missing: ${BIN_DIR}/llama-server"
    [ ! -f "${MODEL_GGUF}" ] && echo "  Missing: ${MODEL_GGUF}"
    echo ""
    echo "Check the build output above for errors."
    exit 1
fi
