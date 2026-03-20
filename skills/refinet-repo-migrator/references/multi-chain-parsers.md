# Multi-Chain Contract Parser Reference

## Ecosystem-Specific Parsing Strategies

### Solidity (EVM) — Primary Path

**Tool**: `solc-js` (npm package, MIT license, free)
**Install**: `npm install -g solc` or use via `npx solcjs`

**Compilation flow**:
1. Read `.sol` source file
2. Detect pragma version (`pragma solidity ^0.8.20;`)
3. Load matching compiler version via `solc.loadRemoteVersion()`
4. Compile with standard JSON input
5. Extract ABI from output JSON

**Import resolution**: Solidity files often import OpenZeppelin or other libraries. Strategy:
- Check if repo contains `node_modules/@openzeppelin/` — use those
- If not, fetch common imports from npm registry
- As last resort, compile with `--allow-paths` and resolve manually

**Known issues**:
- Files with `import "@openzeppelin/..."` fail without the dependency
- Solution: detect imports, fetch from npm, provide as additional sources
- ARM compilation: solc-js works on ARM64 (uses WebAssembly)

### Vyper (EVM)

**Tool**: `vyper` (pip package, Apache 2.0, free)
**Install**: `pip install vyper`

**Compilation flow**:
1. Read `.vy` source file
2. Detect version from `# @version` pragma
3. Run: `vyper -f abi contract.vy`
4. Parse JSON output as ABI

### Anchor (Solana)

**Tool**: No compilation needed — parse IDL JSON directly
**IDL location**: `target/idl/{program_name}.json` in Anchor projects

**Parsing flow**:
1. Find `Anchor.toml` in repo root
2. Locate IDL files in `target/idl/` or `idl/` directory
3. If no IDL found, look for `.json` files matching program names
4. Parse IDL JSON structure (instructions, accounts, types, events, errors)

**Access control patterns in Anchor**:
- `has_one = authority` — owner check on account
- `constraint = signer.key() == authority.key()` — explicit signer check
- `#[access_control(ctx.accounts.admin.is_signer)]` — decorator pattern
- Account named `authority`, `owner`, `admin` with `isSigner: true`

### Move (Sui / Aptos)

**Tool**: LLM-assisted parsing (no local compiler on ARM)

**Parsing flow**:
1. Read `.move` source files
2. Extract `public fun`, `public entry fun`, `fun` declarations
3. Parse parameter types from Move type system
4. Identify `friend` visibility and `signer` parameters for access control

**Access control in Move**:
- `public fun` — callable by anyone
- `public(friend) fun` — restricted to friend modules
- First parameter `signer` / `&signer` — requires transaction signing authority
- `assert!(signer::address_of(account) == @admin)` — owner check

### Clarity (Bitcoin / Stacks)

**Tool**: LLM-assisted parsing

**Parsing flow**:
1. Read `.clar` source files
2. Extract `(define-public ...)` and `(define-read-only ...)` functions
3. Parse Clarity types (uint, int, principal, buff, string, tuple, list)
4. Identify `tx-sender` checks for access control

**Access control in Clarity**:
- `(asserts! (is-eq tx-sender contract-owner) (err u403))` — owner check
- `(define-constant contract-owner tx-sender)` — deployer as owner

### TEAL / PyTEAL (Algorand)

**Tool**: ARC-4 annotation parsing or LLM-assisted

**Parsing flow**:
1. Check for ARC-4 JSON spec file (modern Algorand contracts)
2. If PyTEAL: parse `@app.external`, `@app.create`, `@app.opt_in` decorators
3. If raw TEAL: LLM-assisted parsing of opcodes

**ARC-4 spec format** (if available):
```json
{
  "name": "MyApp",
  "methods": [
    {
      "name": "transfer",
      "args": [{"type": "address", "name": "receiver"}, {"type": "uint64", "name": "amount"}],
      "returns": {"type": "void"}
    }
  ]
}
```

### XRPL Hooks

**Tool**: LLM-assisted parsing

**Parsing flow**:
1. Read hook source files (C or JavaScript)
2. Extract `hook()` entry point parameters
3. Identify `emit()`, `slot_set()`, and other hook API calls
4. Map to XRPL transaction types affected

### Hedera (HTS + Solidity)

**Tool**: `solc-js` (same as Solidity) + HTS pattern detection

**Additional parsing**:
1. Compile as standard Solidity
2. Detect Hedera Token Service (HTS) precompile calls:
   - `0x167` — HTS precompile address
   - `createFungibleToken`, `mintToken`, `associateToken`
3. Flag HTS-specific functions in SDK

### Soroban (Stellar / XLM)

**Tool**: Parse contract spec from build artifacts or LLM-assisted

**Parsing flow**:
1. Check `Cargo.toml` for `soroban-sdk` dependency
2. Look for `target/` directory with `.wasm` and spec files
3. If spec available: parse JSON contract specification
4. If not: LLM-parse the `#[contractimpl]` block from Rust source

**Access control in Soroban**:
- `env.require_auth(&admin)` — explicit auth check
- `Address` type parameters with auth requirements

## Fallback: LLM-Assisted Parsing

For any ecosystem where local compilation is unavailable or fails, the repo-migrator falls back to the LLM chain (Claude Code CLI → Ollama → BitNet → Gemini). The LLM receives the source code and a structured prompt requesting JSON-formatted function/event/error extraction.

This works well for:
- Small contracts (< 500 lines)
- Well-documented contracts with clear function signatures
- Standard patterns (ERC-20, ERC-721, etc.)

It may struggle with:
- Complex inheritance chains
- Heavily obfuscated code
- Custom macro-heavy frameworks

When LLM parsing produces uncertain results, the contract is flagged for manual review.

## Zero-Cost Tool Summary

| Tool | License | Install | ARM64 | Purpose |
|---|---|---|---|---|
| `solc-js` | MIT | `npm install solc` | WASM (works) | Solidity → ABI |
| `vyper` | Apache 2.0 | `pip install vyper` | Native | Vyper → ABI |
| `httpx` | BSD | `pip install httpx` | Native | GitHub API calls |
| LLM chain | N/A | Already installed | N/A | Fallback parsing |
| `git` | GPL-2.0 | System package | Native | Repo cloning |
