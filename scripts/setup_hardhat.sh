#!/usr/bin/env bash
# Setup Hardhat base environment for GROOT Wizard compilation worker.
# Run once during deployment or Docker build.
# Workers copy this base into temp directories for each compilation.

set -euo pipefail

HARDHAT_BASE="${HARDHAT_BASE_DIR:-/opt/refinet/hardhat-base}"

echo "=== Setting up Hardhat base at ${HARDHAT_BASE} ==="

mkdir -p "${HARDHAT_BASE}"
cd "${HARDHAT_BASE}"

# Initialize package.json if not exists
if [ ! -f package.json ]; then
    npm init -y --silent
fi

# Install Hardhat and toolbox
npm install --save-dev \
    hardhat \
    @nomicfoundation/hardhat-toolbox \
    @nomicfoundation/hardhat-ethers \
    ethers \
    chai \
    @types/chai \
    2>/dev/null

# Create default hardhat config (workers will override this)
cat > hardhat.config.js << 'EOF'
require("@nomicfoundation/hardhat-toolbox");
module.exports = {
  solidity: {
    version: "0.8.20",
    settings: { optimizer: { enabled: true, runs: 200 } }
  },
};
EOF

# Create directory structure
mkdir -p contracts test artifacts

echo "=== Hardhat base ready at ${HARDHAT_BASE} ==="
echo "  node_modules: $(du -sh node_modules | cut -f1)"
echo "  hardhat version: $(npx hardhat --version 2>/dev/null || echo 'check manually')"
