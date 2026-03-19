"""
REFINET Cloud — Tag Taxonomy
Hierarchical tag ontology for contract discovery and classification.
Deterministic keyword matching — no LLM dependency.
"""

import json
import logging
import re
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger("refinet.tag_taxonomy")


# ── Tag Ontology ──────────────────────────────────────────────────
# Hierarchical taxonomy: category → subcategories
# All tags are lowercase, no spaces (use hyphens)

TAXONOMY = {
    "defi": [
        "lending", "borrowing", "dex", "amm", "yield", "staking",
        "vault", "liquidity-pool", "flash-loan", "aggregator",
        "perpetual", "options", "insurance", "bridge",
    ],
    "token": [
        "erc20", "erc721", "erc1155", "erc4626", "soulbound",
        "wrapped", "rebasing", "deflationary", "mintable", "burnable",
        "governance-token", "utility-token", "reward-token",
    ],
    "governance": [
        "dao", "voting", "multisig", "timelock", "governor",
        "proposal", "delegation", "quorum", "snapshot",
    ],
    "nft": [
        "collection", "marketplace", "auction", "royalty",
        "metadata", "on-chain-art", "dynamic-nft", "soulbound-nft",
    ],
    "security": [
        "access-control", "ownable", "pausable", "reentrancy-guard",
        "rate-limiter", "allowlist", "blocklist", "upgrade-proxy",
    ],
    "oracle": [
        "price-feed", "chainlink", "randomness", "vrf",
        "data-provider", "off-chain", "keeper",
    ],
    "identity": [
        "ens", "did", "attestation", "credential", "reputation",
        "profile", "registry", "resolver",
    ],
    "payment": [
        "escrow", "streaming", "subscription", "invoice",
        "split", "vesting", "payroll", "tip",
    ],
    "infrastructure": [
        "proxy", "factory", "registry", "library",
        "storage", "relay", "cross-chain", "layer2",
    ],
    "gaming": [
        "in-game-asset", "loot-box", "achievement",
        "crafting", "marketplace", "tournament",
    ],
    "refi": [
        "carbon-credit", "regenerative", "impact",
        "circular-economy", "sustainability", "green-bond",
    ],
}

# Flattened set of all valid tags (category + subcategory)
ALL_TAGS = set()
for category, subcats in TAXONOMY.items():
    ALL_TAGS.add(category)
    ALL_TAGS.update(subcats)

# Keyword → tag mapping for natural language → tag resolution
KEYWORD_MAP = {
    "swap": "dex", "uniswap": "dex", "sushiswap": "dex",
    "lend": "lending", "borrow": "borrowing", "aave": "lending", "compound": "lending",
    "stake": "staking", "unstake": "staking", "validator": "staking",
    "nft": "nft", "collectible": "collection", "art": "on-chain-art",
    "erc-20": "erc20", "erc-721": "erc721", "erc-1155": "erc1155",
    "vote": "voting", "govern": "governance", "proposal": "proposal",
    "multisig": "multisig", "gnosis": "multisig", "safe": "multisig",
    "oracle": "oracle", "chainlink": "chainlink", "price": "price-feed",
    "proxy": "proxy", "upgradeable": "upgrade-proxy", "uups": "upgrade-proxy",
    "ownable": "ownable", "access": "access-control", "role": "access-control",
    "pausable": "pausable", "pause": "pausable",
    "escrow": "escrow", "payment": "payment", "streaming": "streaming",
    "bridge": "bridge", "cross-chain": "cross-chain",
    "vault": "vault", "yield": "yield", "farm": "yield",
    "carbon": "carbon-credit", "regen": "regenerative", "refi": "refi",
    "ens": "ens", "did": "did", "identity": "identity",
    "factory": "factory", "deploy": "factory",
    "marketplace": "marketplace", "auction": "auction",
    "royalty": "royalty", "eip-2981": "royalty",
    "timelock": "timelock", "governor": "governor",
    "vrf": "vrf", "random": "randomness",
    "flash": "flash-loan",
    "mint": "mintable", "burn": "burnable",
    "wrap": "wrapped", "unwrap": "wrapped",
}


def normalize_tags(raw_tags: list[str]) -> list[str]:
    """
    Map free-text tags to canonical taxonomy terms.
    Returns deduplicated, sorted list of valid tags.
    """
    normalized = set()
    for tag in raw_tags:
        tag_lower = tag.lower().strip().replace(" ", "-")

        # Direct match
        if tag_lower in ALL_TAGS:
            normalized.add(tag_lower)
            # Also add parent category
            for cat, subcats in TAXONOMY.items():
                if tag_lower in subcats:
                    normalized.add(cat)
            continue

        # Keyword match
        mapped = KEYWORD_MAP.get(tag_lower)
        if mapped:
            normalized.add(mapped)
            for cat, subcats in TAXONOMY.items():
                if mapped in subcats:
                    normalized.add(cat)
            continue

        # Partial match (substring)
        for keyword, mapped_tag in KEYWORD_MAP.items():
            if keyword in tag_lower:
                normalized.add(mapped_tag)
                break

    return sorted(normalized)


def suggest_tags(description: str, abi_json: Optional[list] = None) -> list[str]:
    """
    Deterministic tag suggestion from contract description + ABI function signatures.
    No LLM needed — pure keyword matching against taxonomy.
    """
    tags = set()
    text = description.lower()

    # Match keywords in description
    for keyword, tag in KEYWORD_MAP.items():
        if keyword in text:
            tags.add(tag)

    # Match category names in description
    for category in TAXONOMY:
        if category in text:
            tags.add(category)

    # Analyze ABI if provided
    if abi_json and isinstance(abi_json, list):
        function_names = []
        for item in abi_json:
            name = (item.get("name") or "").lower()
            if name:
                function_names.append(name)

        all_names = " ".join(function_names)

        # ERC detection from function signatures
        erc_patterns = {
            "erc20": {"transfer", "approve", "allowance", "totalsupply", "balanceof"},
            "erc721": {"safetransferfrom", "ownerof", "tokenuri", "getapproved"},
            "erc1155": {"safebatchtransferfrom", "balanceofbatch", "uri"},
        }
        for erc, required_fns in erc_patterns.items():
            if len(required_fns & set(function_names)) >= 2:
                tags.add(erc)
                tags.add("token")

        # Feature detection from function names
        feature_keywords = {
            "stake": "staking", "unstake": "staking",
            "swap": "dex", "addliquidity": "liquidity-pool",
            "vote": "voting", "propose": "proposal",
            "mint": "mintable", "burn": "burnable",
            "pause": "pausable", "unpause": "pausable",
            "transferownership": "ownable",
            "grantrole": "access-control", "hasrole": "access-control",
            "upgrade": "upgrade-proxy",
            "deposit": "vault", "withdraw": "vault",
            "setprice": "price-feed",
            "claim": "reward-token",
        }
        for fn_name in function_names:
            for keyword, tag in feature_keywords.items():
                if keyword in fn_name:
                    tags.add(tag)

    # Add parent categories for any matched subcategories
    for tag in list(tags):
        for cat, subcats in TAXONOMY.items():
            if tag in subcats:
                tags.add(cat)

    return sorted(tags)


def search_by_tags(
    db: Session,
    tags: list[str],
    chain: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """
    Search registry projects by tags.
    Returns projects that match ANY of the provided tags.
    """
    from api.models.registry import RegistryProject

    # Normalize input tags
    search_tags = normalize_tags(tags)
    if not search_tags:
        return []

    # Query projects — tags stored as comma-separated in categories or as JSON
    query = db.query(RegistryProject).filter(RegistryProject.is_public == True)  # noqa: E712

    if chain:
        query = query.filter(RegistryProject.chain == chain)

    projects = query.order_by(RegistryProject.stars_count.desc()).all()

    # Filter by tags (match against category + any tag fields)
    results = []
    for p in projects:
        project_tags = set()
        if p.category:
            project_tags.add(p.category.lower())

        # Check if any search tag matches
        if project_tags & set(search_tags):
            results.append({
                "id": p.id,
                "name": p.name,
                "slug": p.slug,
                "description": p.description,
                "category": p.category,
                "chain": p.chain,
                "stars_count": p.stars_count,
                "matched_tags": sorted(project_tags & set(search_tags)),
            })

        if len(results) >= limit:
            break

    return results[offset:offset + limit]


def get_taxonomy() -> dict:
    """Return the full tag taxonomy for clients."""
    return {
        "categories": {
            cat: {"subcategories": subcats, "count": len(subcats)}
            for cat, subcats in TAXONOMY.items()
        },
        "total_tags": len(ALL_TAGS),
    }
