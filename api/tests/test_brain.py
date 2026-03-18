"""
Tests for GROOT Brain end-to-end flow.
Upload → Parse → Publish → GROOT context includes SDK → MCP lists tools.
"""

import json
import uuid
import pytest

from api.services.abi_parser import parse_abi
from api.services.sdk_generator import generate_sdk, sdk_to_json, compute_sdk_hash
from api.services.crypto_utils import compute_selector, compute_topic_hash, sha256_hex


# ── Crypto Utils Tests ──────────────────────────────────────────────

class TestCryptoUtils:
    def test_compute_selector(self):
        selector = compute_selector("transfer(address,uint256)")
        assert selector.startswith("0x")
        assert len(selector) == 10

    def test_compute_topic_hash(self):
        topic = compute_topic_hash("Transfer(address,address,uint256)")
        assert topic.startswith("0x")
        assert len(topic) == 66

    def test_sha256_hex(self):
        h = sha256_hex("hello")
        assert len(h) == 64
        # Deterministic
        assert h == sha256_hex("hello")
        assert h != sha256_hex("world")


# ── End-to-End Flow Test ────────────────────────────────────────────

STAKING_ABI = json.dumps([
    {
        "type": "function", "name": "stake",
        "inputs": [{"name": "amount", "type": "uint256"}],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "type": "function", "name": "unstake",
        "inputs": [{"name": "amount", "type": "uint256"}],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "type": "function", "name": "balanceOf",
        "inputs": [{"name": "account", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
    },
    {
        "type": "function", "name": "setRewardRate",
        "inputs": [{"name": "rate", "type": "uint256"}],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "type": "function", "name": "emergencyWithdraw",
        "inputs": [],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "type": "event", "name": "Staked",
        "inputs": [
            {"name": "user", "type": "address", "indexed": True},
            {"name": "amount", "type": "uint256", "indexed": False},
        ],
    },
    {
        "type": "event", "name": "Unstaked",
        "inputs": [
            {"name": "user", "type": "address", "indexed": True},
            {"name": "amount", "type": "uint256", "indexed": False},
        ],
    },
])

STAKING_SOURCE = """
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "@openzeppelin/contracts/access/Ownable.sol";

contract StakingPool is Ownable {
    mapping(address => uint256) public balances;
    uint256 public rewardRate;

    function stake(uint256 amount) external {
        balances[msg.sender] += amount;
    }

    function unstake(uint256 amount) external {
        require(balances[msg.sender] >= amount);
        balances[msg.sender] -= amount;
    }

    function balanceOf(address account) external view returns (uint256) {
        return balances[account];
    }

    function setRewardRate(uint256 rate) external onlyOwner {
        rewardRate = rate;
    }

    function emergencyWithdraw() external onlyOwner {
        payable(owner()).transfer(address(this).balance);
    }
}
"""


class TestEndToEndFlow:
    """Simulates the full upload → parse → SDK generation flow."""

    def test_full_flow(self):
        # Step 1: Parse ABI with source code
        parsed = parse_abi(STAKING_ABI, STAKING_SOURCE)
        assert len(parsed.errors) == 0
        assert len(parsed.functions) == 5
        assert len(parsed.events) == 2

        # Step 2: Verify access control classification
        stake = next(f for f in parsed.functions if f.name == "stake")
        assert stake.access_level == "public"
        assert stake.state_mutability == "nonpayable"

        balance_of = next(f for f in parsed.functions if f.name == "balanceOf")
        assert balance_of.access_level == "public"
        assert balance_of.state_mutability == "view"

        set_rate = next(f for f in parsed.functions if f.name == "setRewardRate")
        assert set_rate.access_level == "owner"
        assert set_rate.access_modifier == "onlyOwner"

        emergency = next(f for f in parsed.functions if f.name == "emergencyWithdraw")
        assert emergency.access_level == "owner"

        # Step 3: Verify security summary
        assert parsed.security.total_functions == 5
        assert parsed.security.public_functions >= 3  # stake, unstake, balanceOf
        assert parsed.security.owner_functions >= 2  # setRewardRate, emergencyWithdraw
        assert parsed.security.access_control_pattern == "Ownable"

        # Step 4: Generate SDK
        sdk = generate_sdk(
            contract_name="StakingPool",
            chain="ethereum",
            contract_address="0x1234567890abcdef1234567890abcdef12345678",
            owner_namespace="refinetdev",
            language="solidity",
            version="1.0.0",
            description="Staking contract for REFINET token holders",
            tags=["defi", "staking"],
            parsed=parsed,
            sdk_version="1.0.0",
        )

        # Step 5: Verify SDK structure
        assert sdk["sdk_version"] == "1.0.0"
        assert sdk["contract"]["name"] == "StakingPool"
        assert sdk["contract"]["chain"] == "ethereum"
        assert sdk["contract"]["address"] == "0x1234567890abcdef1234567890abcdef12345678"
        assert sdk["contract"]["owner"] == "@refinetdev"

        # Public functions
        public_names = [f["name"] for f in sdk["functions"]["public"]]
        assert "stake" in public_names
        assert "balanceOf" in public_names

        # Admin functions
        admin_names = [f["name"] for f in sdk["functions"]["owner_admin"]]
        assert "setRewardRate" in admin_names
        assert "emergencyWithdraw" in admin_names

        # Admin functions have warnings
        for admin_fn in sdk["functions"]["owner_admin"]:
            assert "warning" in admin_fn
            assert "RESTRICTED" in admin_fn["warning"]

        # Events
        event_names = [e["name"] for e in sdk["events"]]
        assert "Staked" in event_names
        assert "Unstaked" in event_names

        # Security summary
        assert sdk["security_summary"]["public_functions"] >= 3
        assert sdk["security_summary"]["admin_functions"] >= 2
        assert sdk["security_summary"]["access_control_pattern"] == "Ownable"

        # Step 6: Verify SDK serialization
        sdk_json = sdk_to_json(sdk)
        assert isinstance(sdk_json, str)
        reparsed = json.loads(sdk_json)
        assert reparsed["contract"]["name"] == "StakingPool"

        # Step 7: Verify SDK hash integrity
        sdk_hash = compute_sdk_hash(sdk_json)
        assert sdk_hash == compute_sdk_hash(sdk_json)  # deterministic

        # Step 8: Cardinal rule — SDK never contains source code
        assert "pragma solidity" not in sdk_json
        assert "mapping(address" not in sdk_json
        assert "source_code" not in sdk_json
        assert "import " not in sdk_json

    def test_function_toggle(self):
        """Test that disabling functions removes them from SDK."""
        parsed = parse_abi(STAKING_ABI, STAKING_SOURCE)

        # Generate with only stake and balanceOf enabled
        sdk = generate_sdk(
            contract_name="StakingPool",
            chain="ethereum",
            contract_address=None,
            owner_namespace="testuser",
            language="solidity",
            version="1.0.0",
            description=None,
            tags=None,
            parsed=parsed,
            enabled_function_ids={"stake", "balanceOf"},
        )

        all_names = (
            [f["name"] for f in sdk["functions"]["public"]]
            + [f["name"] for f in sdk["functions"]["owner_admin"]]
        )
        assert "stake" in all_names
        assert "balanceOf" in all_names
        assert "unstake" not in all_names
        assert "setRewardRate" not in all_names

    def test_sdk_with_no_source_code(self):
        """Test parsing ABI without source code — access levels should be unknown."""
        parsed = parse_abi(STAKING_ABI)  # No source code

        # View functions should still be classified as public
        balance_of = next(f for f in parsed.functions if f.name == "balanceOf")
        assert balance_of.access_level == "public"

        # State-changing functions without source code should be unknown
        stake = next(f for f in parsed.functions if f.name == "stake")
        assert stake.access_level == "unknown"

        # Security summary should reflect unknowns
        assert parsed.security.unknown_functions >= 1


class TestContractBrainContext:
    """Test that the contract brain service formats context correctly."""

    def test_sdk_context_format(self):
        """Verify the context string format for GROOT."""
        # This tests the pure formatting logic, not DB queries
        from api.services.sdk_generator import generate_sdk, sdk_to_json

        parsed = parse_abi(STAKING_ABI, STAKING_SOURCE)
        sdk = generate_sdk(
            contract_name="StakingPool",
            chain="ethereum",
            contract_address="0xabc123",
            owner_namespace="refinetdev",
            language="solidity",
            version="1.0.0",
            description="Staking contract",
            tags=["defi"],
            parsed=parsed,
        )

        sdk_json = sdk_to_json(sdk)
        sdk_data = json.loads(sdk_json)

        # Simulate what contract_brain.get_sdk_context_for_groot would produce
        public_fns = [f["name"] for f in sdk_data["functions"]["public"]]
        admin_fns = [f["name"] for f in sdk_data["functions"]["owner_admin"]]

        assert "stake" in public_fns
        assert "setRewardRate" in admin_fns

        # Verify the SDK data has the right structure for context injection
        assert "security_summary" in sdk_data
        assert "functions" in sdk_data
        assert "events" in sdk_data
