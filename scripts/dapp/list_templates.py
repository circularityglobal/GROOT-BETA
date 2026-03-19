#!/usr/bin/env python3
"""
List available DApp Factory templates with descriptions.

Usage:
    python scripts/dapp/list_templates.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "list_templates",
    "description": "List available DApp Factory templates with descriptions and framework info",
    "category": "dapp",
    "requires_admin": False,
}


def main():
    from api.services.dapp_factory import TEMPLATES

    print("=== DApp Factory Templates ===\n")
    print(f"{'ID':<25} {'Name':<25} {'Framework':<12} Description")
    print("-" * 90)

    for template_id, template in TEMPLATES.items():
        print(f"{template_id:<25} {template['name']:<25} {template['framework']:<12} {template['description']}")

    print(f"\n{len(TEMPLATES)} template(s) available")
    print(f"\nUsage: POST /dapp/build with {'{'}\"template_name\": \"<id>\", \"contract_name\": \"...\", \"contract_address\": \"0x...\", \"chain\": \"ethereum\"{'}'}")


if __name__ == "__main__":
    main()
