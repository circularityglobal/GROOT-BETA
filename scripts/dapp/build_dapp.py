#!/usr/bin/env python3
"""
CLI tool to assemble a DApp from a template and contract configuration.
Generates a downloadable zip file.

Usage:
    python scripts/dapp/build_dapp.py

Environment:
    SCRIPT_ARGS: JSON {
        "template": "simple-dashboard",
        "contract_name": "MyToken",
        "contract_address": "0x...",
        "chain": "ethereum",
        "output_dir": "./output"  (optional, defaults to current dir)
    }
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "build_dapp",
    "description": "Assemble a DApp project from a template + contract config, outputs a zip file",
    "category": "dapp",
    "requires_admin": False,
}


def main():
    args = json.loads(os.environ.get("SCRIPT_ARGS", "{}"))

    template = args.get("template", "")
    contract_name = args.get("contract_name", "")
    contract_address = args.get("contract_address", "")
    chain = args.get("chain", "ethereum")
    abi_json = args.get("abi_json")
    output_dir = args.get("output_dir", ".")

    if not template or not contract_name or not contract_address:
        print("ERROR: Required fields: template, contract_name, contract_address")
        print()
        print("Example:")
        print('  SCRIPT_ARGS=\'{"template":"simple-dashboard","contract_name":"MyToken",')
        print('    "contract_address":"0xdAC17F958D2ee523a2206206994597C13D831ec7","chain":"ethereum"}\'')
        print()

        # Show available templates
        from api.services.dapp_factory import TEMPLATES
        print("Available templates:")
        for tid, t in TEMPLATES.items():
            print(f"  {tid:<25} {t['description']}")

        sys.exit(1)

    from api.services.dapp_factory import generate_dapp_zip, TEMPLATES

    if template not in TEMPLATES:
        print(f"ERROR: Unknown template '{template}'")
        print(f"Available: {', '.join(TEMPLATES.keys())}")
        sys.exit(1)

    print(f"=== DApp Builder ===")
    print(f"  Template: {template} ({TEMPLATES[template]['name']})")
    print(f"  Contract: {contract_name}")
    print(f"  Address:  {contract_address}")
    print(f"  Chain:    {chain}")
    print()

    # Generate the zip
    zip_bytes = generate_dapp_zip(
        template_name=template,
        contract_name=contract_name,
        contract_address=contract_address,
        chain=chain,
        abi_json=abi_json,
    )

    # Save to file
    filename = f"dapp-{contract_name.lower().replace(' ', '-')}.zip"
    output_path = os.path.join(output_dir, filename)

    os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(zip_bytes)

    size_kb = len(zip_bytes) / 1024
    print(f"DApp generated successfully!")
    print(f"  File: {output_path}")
    print(f"  Size: {size_kb:.1f} KB")
    print()
    print("To use:")
    print(f"  cd {os.path.splitext(filename)[0]}")
    print("  npm install")
    print("  npm run dev")


if __name__ == "__main__":
    main()
