#!/usr/bin/env python3
"""
REFINET Cloud — Contract Definitions Seed Script
Seeds Groot's CAG (Contract-Augmented Generation) knowledge with foundational
smart contract definitions across Ethereum, Base, Arbitrum, and Polygon.

Usage:
  python3 scripts/seed_contracts.py --local
"""

SCRIPT_META = {
    "name": "seed_contracts",
    "description": "Seed 10 foundational smart contract definitions for CAG (idempotent)",
    "category": "seed",
    "requires_admin": True,
}

import argparse
import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Contract Definitions ────────────────────────────────────────────

CONTRACTS = [
    # ── Ethereum ────────────────────────────────────────────────
    {
        "name": "Wrapped Ether (WETH)",
        "chain": "ethereum",
        "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "category": "defi",
        "description": "WETH is the ERC-20 wrapped version of native ETH. Since ETH itself does not conform to the ERC-20 standard, WETH allows ETH to be traded directly with other ERC-20 tokens on decentralized exchanges. Users deposit ETH and receive an equal amount of WETH; withdrawing burns WETH and returns ETH.",
        "logic_summary": "deposit() — payable, wraps msg.value ETH into WETH tokens 1:1. withdraw(uint256 wad) — burns wad WETH and sends wad ETH back to caller. transfer(address dst, uint256 wad) — standard ERC-20 transfer. approve(address guy, uint256 wad) — ERC-20 approval for delegated spending. totalSupply() — returns total WETH in circulation (equals ETH held by contract). balanceOf(address) — returns WETH balance of an address.",
    },
    {
        "name": "Uniswap V3 SwapRouter",
        "chain": "ethereum",
        "address": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        "category": "defi",
        "description": "The Uniswap V3 SwapRouter is the primary entry point for token swaps on Uniswap V3. It routes swaps through concentrated liquidity pools, supporting exact-input and exact-output swaps across single pools or multi-hop paths. It handles deadline enforcement, slippage protection, and fee tier selection.",
        "logic_summary": "exactInputSingle(ExactInputSingleParams) — swap exact amount of tokenIn for maximum tokenOut through a single pool. exactInput(ExactInputParams) — multi-hop swap with exact input amount along an encoded path. exactOutputSingle(ExactOutputSingleParams) — swap minimum tokenIn for exact amount of tokenOut. exactOutput(ExactOutputParams) — multi-hop swap for exact output. Parameters include: tokenIn, tokenOut, fee (500/3000/10000 bps), recipient, deadline, amountIn/amountOut, sqrtPriceLimitX96.",
    },
    {
        "name": "ENS Registry",
        "chain": "ethereum",
        "address": "0x00000000000C2E074eC69A0dFb2997BA6C7d2e1e",
        "category": "utility",
        "description": "The Ethereum Name Service (ENS) Registry is the core contract that stores all ENS domain ownership and resolver information. It maps domain name hashes (namehash) to owner addresses, resolver contracts, and TTL values. ENS enables human-readable names like 'alice.eth' to resolve to Ethereum addresses, content hashes, and other records.",
        "logic_summary": "owner(bytes32 node) — returns the owner of a domain. resolver(bytes32 node) — returns the resolver contract address for a domain. setOwner(bytes32 node, address owner) — transfer domain ownership. setResolver(bytes32 node, address resolver) — set the resolver for a domain. setSubnodeOwner(bytes32 node, bytes32 label, address owner) — create or transfer a subdomain. setTTL(bytes32 node, uint64 ttl) — set the caching TTL. recordExists(bytes32 node) — check if a record exists.",
    },
    {
        "name": "ERC-20 Token Standard",
        "chain": "ethereum",
        "address": None,
        "category": "token",
        "description": "ERC-20 is the standard interface for fungible tokens on Ethereum and all EVM-compatible chains. It defines the minimum set of functions that every token contract must implement to be interoperable with wallets, exchanges, and DeFi protocols. Most DeFi protocols, including Uniswap, Aave, and Compound, interact with tokens through this interface.",
        "logic_summary": "totalSupply() — returns total token supply. balanceOf(address account) — returns token balance of account. transfer(address to, uint256 amount) — sends tokens from caller to recipient. approve(address spender, uint256 amount) — authorizes spender to transfer up to amount tokens. transferFrom(address from, address to, uint256 amount) — transfers tokens on behalf of from (requires prior approval). allowance(address owner, address spender) — returns remaining approved amount. Events: Transfer(from, to, value), Approval(owner, spender, value).",
    },

    # ── Base ────────────────────────────────────────────────────
    {
        "name": "USDC on Base",
        "chain": "base",
        "address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "category": "token",
        "description": "USDC on Base is Circle's native USD Coin deployment on the Base L2 network. It is a fully-backed, regulated stablecoin pegged 1:1 to the US dollar. Unlike bridged USDC, this is the native issuance on Base with direct Circle support, making it the canonical dollar-denominated token on the Base ecosystem.",
        "logic_summary": "Standard ERC-20 interface: transfer(), approve(), transferFrom(), balanceOf(), totalSupply(), allowance(). Additional: mint(address to, uint256 amount) — Circle minter creates new USDC. burn(uint256 amount) — destroys USDC (redeem for USD). configureMinter(address minter, uint256 allowance) — admin configures minting rights. Decimals: 6 (not 18). Upgradeable proxy pattern (UUPS).",
    },
    {
        "name": "Base Bridge (L1StandardBridge)",
        "chain": "base",
        "address": "0x3154Cf16ccdb4C6d922629664174b904d80F2C35",
        "category": "bridge",
        "description": "The Base Bridge enables asset transfers between Ethereum L1 and Base L2. It locks tokens on L1 and mints equivalent representations on L2 (and vice versa for withdrawals). Deposits are confirmed in minutes; withdrawals require a 7-day challenge period for security under the Optimistic Rollup model.",
        "logic_summary": "depositETH(uint32 minGasLimit, bytes extraData) — bridges ETH from L1 to L2. depositERC20(address l1Token, address l2Token, uint256 amount, uint32 minGasLimit, bytes extraData) — bridges ERC-20 from L1 to L2. withdrawals require proving and finalizing after the challenge period. bridgeETH(uint32 minGasLimit, bytes extraData) — L2 side ETH bridge. bridgeERC20(address localToken, address remoteToken, uint256 amount, uint32 minGasLimit, bytes extraData) — L2 side token bridge.",
    },

    # ── Arbitrum ────────────────────────────────────────────────
    {
        "name": "GMX V2 Router",
        "chain": "arbitrum",
        "address": "0x7C68C7866A64FA2160F78EEaE12217FFbf871fa8",
        "category": "defi",
        "description": "GMX is a decentralized perpetual exchange on Arbitrum allowing leveraged trading of BTC, ETH, and other assets up to 50x. The V2 Router handles swap and leverage order creation, execution, and cancellation. Liquidity is provided through GM tokens (market-specific liquidity pools) rather than a single GLP pool.",
        "logic_summary": "createOrder(CreateOrderParams) — submits a new market/limit/stop order. cancelOrder(bytes32 key) — cancels a pending order. createDeposit(CreateDepositParams) — deposits assets into a GM liquidity pool. createWithdrawal(CreateWithdrawalParams) — withdraws from a GM pool. Key parameters: market (trading pair), initialCollateralToken, sizeDeltaUsd, isLong, triggerPrice, acceptablePrice, executionFee. Orders are executed by keeper network after submission.",
    },
    {
        "name": "Arbitrum Gateway Router",
        "chain": "arbitrum",
        "address": "0x5288c571Fd7aD117beA99bF60FE0846C4E84F933",
        "category": "bridge",
        "description": "The Arbitrum Gateway Router directs token deposits from Ethereum L1 to the appropriate gateway contract on Arbitrum L2. Different token types (standard ERC-20, custom, WETH) use different gateway contracts, and the router maintains the mapping. This is the standard entry point for bridging tokens to Arbitrum.",
        "logic_summary": "outboundTransfer(address token, address to, uint256 amount, uint256 maxGas, uint256 gasPriceBid, bytes data) — initiates an L1→L2 token transfer through the correct gateway. getGateway(address token) — returns the gateway contract for a specific token. calculateL2TokenAddress(address l1Token) — computes the L2 token address for a given L1 token. counterpartGateway() — returns the L2 gateway router address.",
    },

    # ── Polygon ─────────────────────────────────────────────────
    {
        "name": "Aave V3 Pool (Polygon)",
        "chain": "polygon",
        "address": "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
        "category": "defi",
        "description": "Aave V3 is the leading decentralized lending protocol on Polygon. Users supply assets to earn interest and borrow against their collateral. V3 introduces efficiency mode (eMode) for correlated assets, isolation mode for new listings, and cross-chain portals. The Pool contract is the main user-facing entry point for all lending operations.",
        "logic_summary": "supply(address asset, uint256 amount, address onBehalfOf, uint16 referralCode) — deposits asset as collateral/earning. withdraw(address asset, uint256 amount, address to) — withdraws supplied asset. borrow(address asset, uint256 amount, uint256 interestRateMode, uint16 referralCode, address onBehalfOf) — borrows asset (1=stable, 2=variable rate). repay(address asset, uint256 amount, uint256 interestRateMode, address onBehalfOf) — repays borrowed asset. liquidationCall(address collateralAsset, address debtAsset, address user, uint256 debtToCover, bool receiveAToken) — liquidates undercollateralized position. getUserAccountData(address user) — returns health factor, collateral, debt.",
    },
    {
        "name": "Polygon PoS Bridge (RootChainManager)",
        "chain": "polygon",
        "address": "0xA0c68C638235ee32657e8f720a23ceC1bFc77C77",
        "category": "bridge",
        "description": "The Polygon PoS Bridge RootChainManager is the Ethereum-side contract that manages token deposits into the Polygon PoS chain. It handles deposit and exit (withdrawal) flows for ETH, ERC-20, ERC-721, and ERC-1155 tokens. Deposits are confirmed within ~7 minutes; exits require a checkpoint inclusion proof.",
        "logic_summary": "depositEtherFor(address user) — payable, deposits ETH to Polygon for user. depositFor(address user, address rootToken, bytes depositData) — deposits ERC-20/721/1155 tokens to Polygon. exit(bytes inputData) — processes an exit/withdrawal proof from Polygon. tokenToType(address token) — returns the token type mapping. typeToPredicate(bytes32 tokenType) — returns the predicate contract for a token type.",
    },
]


def seed_local():
    """Seed contracts directly via DB access (no HTTP needed)."""
    from dotenv import load_dotenv
    load_dotenv()

    from api.database import create_public_session
    from api.models.knowledge import ContractDefinition

    db = create_public_session()
    try:
        inserted = 0
        skipped = 0
        for c in CONTRACTS:
            # Dedup by chain + name
            existing = db.query(ContractDefinition).filter(
                ContractDefinition.chain == c["chain"],
                ContractDefinition.name == c["name"],
            ).first()
            if existing:
                skipped += 1
                continue

            definition = ContractDefinition(
                id=str(uuid.uuid4()),
                name=c["name"],
                chain=c["chain"],
                address=c.get("address"),
                description=c["description"],
                logic_summary=c["logic_summary"],
                category=c.get("category", "defi"),
            )
            db.add(definition)
            inserted += 1

        db.commit()
        print(f"Done. Inserted: {inserted}, Skipped (already exist): {skipped}")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Seed CAG contract definitions")
    parser.add_argument("--local", action="store_true", help="Seed via direct DB access")
    args = parser.parse_args()

    if args.local:
        seed_local()
    else:
        print("Use --local flag for direct DB seeding.")
        print("Example: python3 scripts/seed_contracts.py --local")
        sys.exit(1)


if __name__ == "__main__":
    main()
