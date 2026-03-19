"""
REFINET Cloud — DApp Factory Service
Assembles downloadable DApp projects from registry contracts + templates.
"""

import json
import io
import logging
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from api.models.public import DAppBuild

logger = logging.getLogger("refinet.dapp")


# ── Template Definitions ─────────────────────────────────────────

TEMPLATES = {
    "simple-dashboard": {
        "name": "Simple Dashboard",
        "description": "A minimal React dashboard that connects to your contract and displays key metrics.",
        "framework": "next.js",
        "files": ["package.json", "pages/index.tsx", "lib/contract.ts", "styles/globals.css"],
    },
    "token-manager": {
        "name": "Token Manager",
        "description": "ERC20 token management interface with transfer, approve, and balance checking.",
        "framework": "next.js",
        "files": ["package.json", "pages/index.tsx", "components/TokenInfo.tsx", "components/TransferForm.tsx", "lib/contract.ts"],
    },
    "staking-ui": {
        "name": "Staking Interface",
        "description": "Staking pool interface with stake, unstake, and reward claiming.",
        "framework": "next.js",
        "files": ["package.json", "pages/index.tsx", "components/StakeForm.tsx", "components/RewardDisplay.tsx", "lib/contract.ts"],
    },
    "governance-voting": {
        "name": "Governance Voting",
        "description": "DAO governance interface with proposal listing, voting, and delegation.",
        "framework": "next.js",
        "files": ["package.json", "pages/index.tsx", "components/ProposalList.tsx", "components/VoteModal.tsx", "lib/contract.ts"],
    },
}


def list_templates() -> list[dict]:
    """List all available DApp templates."""
    return [
        {
            "id": key,
            "name": t["name"],
            "description": t["description"],
            "framework": t["framework"],
        }
        for key, t in TEMPLATES.items()
    ]


# ── DApp Assembly ────────────────────────────────────────────────

def assemble_dapp(
    db: Session,
    user_id: str,
    template_name: str,
    contract_name: str,
    contract_address: str,
    chain: str,
    abi_json: Optional[str] = None,
    project_id: Optional[str] = None,
) -> DAppBuild:
    """
    Assemble a DApp from a template and contract configuration.
    Returns a DAppBuild record with the generated zip filename.
    """
    if template_name not in TEMPLATES:
        build = DAppBuild(
            user_id=user_id,
            template_name=template_name,
            status="failed",
            error_message=f"Unknown template: {template_name}",
        )
        db.add(build)
        db.flush()
        return build

    template = TEMPLATES[template_name]
    build_id = str(uuid.uuid4())

    build = DAppBuild(
        id=build_id,
        user_id=user_id,
        project_id=project_id,
        template_name=template_name,
        config_json=json.dumps({
            "contract_name": contract_name,
            "contract_address": contract_address,
            "chain": chain,
        }),
        status="ready",
        output_filename=f"dapp-{contract_name.lower()}-{build_id[:8]}.zip",
        completed_at=datetime.now(timezone.utc),
    )
    db.add(build)
    db.flush()
    return build


def generate_dapp_zip(
    template_name: str,
    contract_name: str,
    contract_address: str,
    chain: str,
    abi_json: Optional[str] = None,
) -> bytes:
    """
    Generate a downloadable zip file containing the DApp project.
    Returns the zip file as bytes.
    """
    if template_name not in TEMPLATES:
        raise ValueError(f"Unknown template: {template_name}")

    chain_config = _get_chain_config(chain)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        project_name = f"dapp-{contract_name.lower()}"

        # package.json
        zf.writestr(f"{project_name}/package.json", _gen_package_json(project_name, contract_name))

        # Contract config
        zf.writestr(f"{project_name}/lib/contract.ts", _gen_contract_ts(
            contract_name, contract_address, chain_config, abi_json,
        ))

        # Main page
        zf.writestr(f"{project_name}/pages/index.tsx", _gen_index_page(
            template_name, contract_name, contract_address, chain,
        ))

        # Global styles
        zf.writestr(f"{project_name}/styles/globals.css", _gen_styles())

        # README
        zf.writestr(f"{project_name}/README.md", _gen_readme(
            project_name, contract_name, contract_address, chain, template_name,
        ))

        # ABI file if provided
        if abi_json:
            zf.writestr(f"{project_name}/lib/abi.json", abi_json)

        # tsconfig
        zf.writestr(f"{project_name}/tsconfig.json", json.dumps({
            "compilerOptions": {
                "target": "es5",
                "lib": ["dom", "dom.iterable", "esnext"],
                "strict": True,
                "module": "esnext",
                "moduleResolution": "node",
                "jsx": "preserve",
            },
            "include": ["**/*.ts", "**/*.tsx"],
        }, indent=2))

    return buf.getvalue()


# ── File Generators ──────────────────────────────────────────────

def _gen_package_json(project_name: str, contract_name: str) -> str:
    return json.dumps({
        "name": project_name,
        "version": "1.0.0",
        "description": f"DApp for {contract_name} — generated by REFINET Cloud DApp Factory",
        "scripts": {
            "dev": "next dev",
            "build": "next build",
            "start": "next start",
        },
        "dependencies": {
            "next": "^14.0.0",
            "react": "^18.2.0",
            "react-dom": "^18.2.0",
            "ethers": "^6.9.0",
        },
        "devDependencies": {
            "typescript": "^5.3.0",
            "@types/react": "^18.2.0",
            "@types/node": "^20.10.0",
        },
    }, indent=2)


def _gen_contract_ts(name: str, address: str, chain_config: dict, abi_json: Optional[str]) -> str:
    abi_import = 'import abi from "./abi.json";\n' if abi_json else 'const abi: any[] = [];\n'
    return f'''// Contract configuration — generated by REFINET Cloud DApp Factory
import {{ ethers }} from "ethers";

{abi_import}
export const CONTRACT_NAME = "{name}";
export const CONTRACT_ADDRESS = "{address}";
export const CHAIN_ID = {chain_config.get("chain_id", 1)};
export const CHAIN_NAME = "{chain_config.get("name", "Ethereum")}";
export const RPC_URL = "{chain_config.get("rpc_url", "")}";

export function getProvider() {{
  if (typeof window !== "undefined" && (window as any).ethereum) {{
    return new ethers.BrowserProvider((window as any).ethereum);
  }}
  return new ethers.JsonRpcProvider(RPC_URL);
}}

export async function getContract(signer?: ethers.Signer) {{
  const provider = getProvider();
  if (signer) {{
    return new ethers.Contract(CONTRACT_ADDRESS, abi, signer);
  }}
  return new ethers.Contract(CONTRACT_ADDRESS, abi, provider);
}}
'''


def _gen_index_page(template: str, name: str, address: str, chain: str) -> str:
    return f'''// Main page — generated by REFINET Cloud DApp Factory
import {{ useState, useEffect }} from "react";
import {{ CONTRACT_NAME, CONTRACT_ADDRESS, CHAIN_NAME, getProvider, getContract }} from "../lib/contract";

export default function Home() {{
  const [connected, setConnected] = useState(false);
  const [account, setAccount] = useState("");

  async function connectWallet() {{
    const provider = getProvider();
    if (provider && "send" in provider) {{
      const accounts = await (provider as any).send("eth_requestAccounts", []);
      setAccount(accounts[0]);
      setConnected(true);
    }}
  }}

  return (
    <div style={{{{ padding: "2rem", fontFamily: "monospace", maxWidth: "800px", margin: "0 auto" }}}}>
      <h1>{{CONTRACT_NAME}}</h1>
      <p>Contract: {{CONTRACT_ADDRESS}}</p>
      <p>Chain: {{CHAIN_NAME}}</p>

      {{!connected ? (
        <button onClick={{connectWallet}} style={{{{ padding: "0.5rem 1rem", cursor: "pointer" }}}}>
          Connect Wallet
        </button>
      ) : (
        <div>
          <p>Connected: {{account}}</p>
          <p>Template: {template}</p>
          <p style={{{{ color: "#888" }}}}>
            Customize this page to interact with your contract functions.
          </p>
        </div>
      )}}

      <footer style={{{{ marginTop: "3rem", color: "#666", fontSize: "0.85rem" }}}}>
        Built with REFINET Cloud DApp Factory
      </footer>
    </div>
  );
}}
'''


def _gen_styles() -> str:
    return '''/* Global styles — REFINET DApp Factory */
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #0a0a0a; color: #e0e0e0; }
button { background: #00bfa5; color: #000; border: none; border-radius: 4px; font-weight: bold; }
button:hover { background: #00e5c4; }
'''


def _gen_readme(project: str, name: str, address: str, chain: str, template: str) -> str:
    return f'''# {project}

DApp for **{name}** on **{chain}**.

Generated by REFINET Cloud DApp Factory using the `{template}` template.

## Setup

```bash
npm install
npm run dev
```

## Contract

- **Address:** `{address}`
- **Chain:** {chain}

## Built With

- Next.js 14
- ethers.js v6
- REFINET Cloud
'''


def _get_chain_config(chain: str) -> dict:
    configs = {
        "ethereum": {"chain_id": 1, "name": "Ethereum Mainnet", "rpc_url": "https://eth.llamarpc.com"},
        "base": {"chain_id": 8453, "name": "Base", "rpc_url": "https://mainnet.base.org"},
        "arbitrum": {"chain_id": 42161, "name": "Arbitrum One", "rpc_url": "https://arb1.arbitrum.io/rpc"},
        "polygon": {"chain_id": 137, "name": "Polygon", "rpc_url": "https://polygon-rpc.com"},
        "sepolia": {"chain_id": 11155111, "name": "Sepolia Testnet", "rpc_url": "https://rpc.sepolia.org"},
    }
    return configs.get(chain, {"chain_id": 1, "name": chain, "rpc_url": ""})
