"""
Tests for GROOT Brain ABI Parser Service.
Tests parsing, access control detection, dangerous pattern flagging,
and security summary generation.
"""

import json
import pytest
from api.services.abi_parser import (
    parse_abi, ParsedABI, ParsedFunction, ParsedEvent,
    _detect_access_control, _detect_dangerous_function,
)


# ── Sample ABIs ─────────────────────────────────────────────────────

ERC20_ABI = json.dumps([
    {
        "type": "function", "name": "transfer",
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
    },
    {
        "type": "function", "name": "approve",
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
    },
    {
        "type": "function", "name": "balanceOf",
        "inputs": [{"name": "account", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
    },
    {
        "type": "function", "name": "totalSupply",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
    },
    {
        "type": "event", "name": "Transfer",
        "inputs": [
            {"name": "from", "type": "address", "indexed": True},
            {"name": "to", "type": "address", "indexed": True},
            {"name": "value", "type": "uint256", "indexed": False},
        ],
    },
    {
        "type": "event", "name": "Approval",
        "inputs": [
            {"name": "owner", "type": "address", "indexed": True},
            {"name": "spender", "type": "address", "indexed": True},
            {"name": "value", "type": "uint256", "indexed": False},
        ],
    },
    {
        "type": "constructor",
        "inputs": [
            {"name": "name_", "type": "string"},
            {"name": "symbol_", "type": "string"},
        ],
        "stateMutability": "nonpayable",
    },
])

OWNABLE_SOURCE = """
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract MyToken is ERC20, Ownable {
    uint256 public rewardRate;

    constructor() ERC20("MyToken", "MTK") {
        _mint(msg.sender, 1000000 * 10**18);
    }

    function transfer(address to, uint256 amount) public override returns (bool) {
        return super.transfer(to, amount);
    }

    function approve(address spender, uint256 amount) public override returns (bool) {
        return super.approve(spender, amount);
    }

    function balanceOf(address account) public view override returns (uint256) {
        return super.balanceOf(account);
    }

    function totalSupply() public view override returns (uint256) {
        return super.totalSupply();
    }

    function setRewardRate(uint256 rate) external onlyOwner {
        rewardRate = rate;
    }

    function pause() external onlyOwner {
        // pause logic
    }

    function mint(address to, uint256 amount) external onlyOwner {
        _mint(to, amount);
    }
}
"""

OWNABLE_ABI = json.dumps([
    {
        "type": "function", "name": "transfer",
        "inputs": [{"name": "to", "type": "address"}, {"name": "amount", "type": "uint256"}],
        "outputs": [{"name": "", "type": "bool"}],
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
        "type": "function", "name": "pause",
        "inputs": [],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "type": "function", "name": "mint",
        "inputs": [{"name": "to", "type": "address"}, {"name": "amount", "type": "uint256"}],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
])

ACCESS_CONTROL_SOURCE = """
pragma solidity ^0.8.0;
import "@openzeppelin/contracts/access/AccessControl.sol";

contract MyDAO is AccessControl {
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
    bytes32 public constant MINTER_ROLE = keccak256("MINTER_ROLE");

    function propose(string memory description) external {
        // anyone can propose
    }

    function execute(uint256 proposalId) external onlyRole(ADMIN_ROLE) {
        // admin only
    }

    function mint(address to, uint256 amount) external onlyRole(MINTER_ROLE) {
        // minter only
    }
}
"""

DANGEROUS_SOURCE = """
pragma solidity ^0.8.0;

contract Destroyable {
    address public owner;

    function destroy() external {
        require(msg.sender == owner);
        selfdestruct(payable(owner));
    }

    function upgrade(address newImpl) external {
        require(msg.sender == owner);
        (bool ok, ) = newImpl.delegatecall(abi.encodeWithSignature("init()"));
        require(ok);
    }
}
"""


# ── Tests ───────────────────────────────────────────────────────────

class TestParseABI:
    def test_parse_erc20_abi(self):
        result = parse_abi(ERC20_ABI)
        assert isinstance(result, ParsedABI)
        assert len(result.errors) == 0

        # Should have 4 functions + 1 constructor = 5
        assert len(result.functions) == 5
        # Should have 2 events
        assert len(result.events) == 2

    def test_function_signatures(self):
        result = parse_abi(ERC20_ABI)
        fn_names = [f.name for f in result.functions]
        assert "transfer" in fn_names
        assert "approve" in fn_names
        assert "balanceOf" in fn_names
        assert "totalSupply" in fn_names
        assert "constructor" in fn_names

    def test_function_selectors(self):
        result = parse_abi(ERC20_ABI)
        transfer = next(f for f in result.functions if f.name == "transfer")
        assert transfer.selector.startswith("0x")
        assert len(transfer.selector) == 10  # 0x + 8 hex chars
        # transfer(address,uint256) selector = 0xa9059cbb
        assert transfer.signature == "transfer(address,uint256)"

    def test_view_functions_classified_as_public(self):
        result = parse_abi(ERC20_ABI)
        balance_of = next(f for f in result.functions if f.name == "balanceOf")
        assert balance_of.state_mutability == "view"
        assert balance_of.access_level == "public"

    def test_event_parsing(self):
        result = parse_abi(ERC20_ABI)
        transfer_evt = next(e for e in result.events if e.name == "Transfer")
        assert transfer_evt.signature == "Transfer(address,address,uint256)"
        assert transfer_evt.topic_hash.startswith("0x")
        assert len(transfer_evt.topic_hash) == 66  # 0x + 64 hex chars
        assert len(transfer_evt.inputs) == 3
        assert transfer_evt.inputs[0]["indexed"] is True

    def test_invalid_json(self):
        result = parse_abi("not json")
        assert len(result.errors) > 0
        assert "Invalid ABI JSON" in result.errors[0]

    def test_non_array_json(self):
        result = parse_abi('{"type": "function"}')
        assert len(result.errors) > 0
        assert "JSON array" in result.errors[0]

    def test_empty_abi(self):
        result = parse_abi("[]")
        assert len(result.functions) == 0
        assert len(result.events) == 0
        assert len(result.errors) == 0


class TestAccessControlDetection:
    def test_ownable_detection(self):
        result = parse_abi(OWNABLE_ABI, OWNABLE_SOURCE)

        # transfer should be public
        transfer = next(f for f in result.functions if f.name == "transfer")
        assert transfer.access_level == "public"

        # setRewardRate should be owner
        set_rate = next(f for f in result.functions if f.name == "setRewardRate")
        assert set_rate.access_level == "owner"
        assert set_rate.access_modifier == "onlyOwner"

        # pause should be owner
        pause = next(f for f in result.functions if f.name == "pause")
        assert pause.access_level == "owner"

        # mint should be owner
        mint = next(f for f in result.functions if f.name == "mint")
        assert mint.access_level == "owner"

    def test_access_control_pattern_detected(self):
        result = parse_abi(OWNABLE_ABI, OWNABLE_SOURCE)
        assert result.security.access_control_pattern == "Ownable"

    def test_security_summary_counts(self):
        result = parse_abi(OWNABLE_ABI, OWNABLE_SOURCE)
        assert result.security.total_functions == 5
        assert result.security.public_functions >= 2  # transfer, balanceOf
        assert result.security.owner_functions >= 2  # setRewardRate, pause, mint


class TestAccessControlWithRoles:
    def test_role_based_detection(self):
        abi = json.dumps([
            {"type": "function", "name": "propose", "inputs": [{"name": "description", "type": "string"}], "outputs": [], "stateMutability": "nonpayable"},
            {"type": "function", "name": "execute", "inputs": [{"name": "proposalId", "type": "uint256"}], "outputs": [], "stateMutability": "nonpayable"},
            {"type": "function", "name": "mint", "inputs": [{"name": "to", "type": "address"}, {"name": "amount", "type": "uint256"}], "outputs": [], "stateMutability": "nonpayable"},
        ])
        result = parse_abi(abi, ACCESS_CONTROL_SOURCE)

        # propose should be public
        propose = next(f for f in result.functions if f.name == "propose")
        assert propose.access_level == "public"

        # execute has onlyRole(ADMIN_ROLE) — detected as admin (ADMIN pattern matches first)
        execute = next(f for f in result.functions if f.name == "execute")
        assert execute.access_level in ("admin", "role_based")

        # mint has onlyRole(MINTER_ROLE) — detected as role_based
        mint_fn = next(f for f in result.functions if f.name == "mint")
        assert mint_fn.access_level == "role_based"
        assert "MINTER_ROLE" in mint_fn.access_roles


class TestDangerousPatterns:
    def test_selfdestruct_detection(self):
        abi = json.dumps([
            {"type": "function", "name": "destroy", "inputs": [], "outputs": [], "stateMutability": "nonpayable"},
            {"type": "function", "name": "upgrade", "inputs": [{"name": "newImpl", "type": "address"}], "outputs": [], "stateMutability": "nonpayable"},
        ])
        result = parse_abi(abi, DANGEROUS_SOURCE)

        destroy = next(f for f in result.functions if f.name == "destroy")
        assert destroy.is_dangerous is True
        assert "selfdestruct" in (destroy.danger_reason or "").lower()

    def test_delegatecall_detection(self):
        abi = json.dumps([
            {"type": "function", "name": "upgrade", "inputs": [{"name": "newImpl", "type": "address"}], "outputs": [], "stateMutability": "nonpayable"},
        ])
        result = parse_abi(abi, DANGEROUS_SOURCE)

        upgrade = next(f for f in result.functions if f.name == "upgrade")
        assert upgrade.is_dangerous is True
        assert "delegatecall" in (upgrade.danger_reason or "").lower()

    def test_dangerous_function_names(self):
        abi = json.dumps([
            {"type": "function", "name": "selfdestruct", "inputs": [], "outputs": [], "stateMutability": "nonpayable"},
            {"type": "function", "name": "upgradeTo", "inputs": [{"name": "impl", "type": "address"}], "outputs": [], "stateMutability": "nonpayable"},
        ])
        result = parse_abi(abi)

        # selfdestruct by name
        sd = next(f for f in result.functions if f.name == "selfdestruct")
        assert sd.is_dangerous is True

        # upgradeTo by name
        ut = next(f for f in result.functions if f.name == "upgradeTo")
        assert ut.is_dangerous is True

    def test_security_summary_flags(self):
        abi = json.dumps([
            {"type": "function", "name": "destroy", "inputs": [], "outputs": [], "stateMutability": "nonpayable"},
            {"type": "function", "name": "upgrade", "inputs": [{"name": "newImpl", "type": "address"}], "outputs": [], "stateMutability": "nonpayable"},
        ])
        result = parse_abi(abi, DANGEROUS_SOURCE)

        assert result.security.has_selfdestruct is True
        assert result.security.has_delegatecall is True
        assert result.security.dangerous_count >= 1


class TestProxyDetection:
    def test_uups_proxy_detected(self):
        source = """
        import "@openzeppelin/contracts/proxy/utils/UUPSUpgradeable.sol";
        contract MyProxy is UUPSUpgradeable {
            function _authorizeUpgrade(address) internal override onlyOwner {}
        }
        """
        abi = json.dumps([
            {"type": "function", "name": "upgradeTo", "inputs": [{"name": "impl", "type": "address"}], "outputs": [], "stateMutability": "nonpayable"},
        ])
        result = parse_abi(abi, source)
        assert result.security.is_proxy is True


class TestSDKGeneration:
    def test_sdk_generator_integration(self):
        """Test that parsed ABI can be fed to SDK generator."""
        from api.services.sdk_generator import generate_sdk, sdk_to_json, compute_sdk_hash

        parsed = parse_abi(ERC20_ABI)
        sdk = generate_sdk(
            contract_name="TestToken",
            chain="ethereum",
            contract_address="0x1234567890abcdef1234567890abcdef12345678",
            owner_namespace="testuser",
            language="solidity",
            version="1.0.0",
            description="A test ERC20 token",
            tags=["token", "erc20"],
            parsed=parsed,
        )

        assert sdk["sdk_version"] == "1.0.0"
        assert sdk["contract"]["name"] == "TestToken"
        assert sdk["contract"]["chain"] == "ethereum"
        assert sdk["contract"]["owner"] == "@testuser"
        assert len(sdk["functions"]["public"]) > 0
        assert len(sdk["events"]) == 2

        # Verify JSON serialization
        sdk_json = sdk_to_json(sdk)
        assert isinstance(sdk_json, str)

        # Verify hash
        sdk_hash = compute_sdk_hash(sdk_json)
        assert len(sdk_hash) == 64  # SHA-256 hex

    def test_sdk_excludes_disabled_functions(self):
        from api.services.sdk_generator import generate_sdk

        parsed = parse_abi(ERC20_ABI)
        # Only enable transfer and balanceOf
        sdk = generate_sdk(
            contract_name="TestToken",
            chain="ethereum",
            contract_address=None,
            owner_namespace="testuser",
            language="solidity",
            version="1.0.0",
            description=None,
            tags=None,
            parsed=parsed,
            enabled_function_ids={"transfer", "balanceOf"},
        )

        all_fn_names = [f["name"] for f in sdk["functions"]["public"]]
        assert "transfer" in all_fn_names
        assert "balanceOf" in all_fn_names
        assert "approve" not in all_fn_names

    def test_sdk_never_contains_source_code(self):
        from api.services.sdk_generator import generate_sdk, sdk_to_json

        parsed = parse_abi(OWNABLE_ABI, OWNABLE_SOURCE)
        sdk = generate_sdk(
            contract_name="MyToken",
            chain="ethereum",
            contract_address=None,
            owner_namespace="testuser",
            language="solidity",
            version="1.0.0",
            description=None,
            tags=None,
            parsed=parsed,
        )

        sdk_json = sdk_to_json(sdk)

        # The cardinal rule: SDK never contains source code
        assert "pragma solidity" not in sdk_json
        assert "import" not in sdk_json
        assert "contract MyToken" not in sdk_json
        assert "source_code" not in sdk_json
