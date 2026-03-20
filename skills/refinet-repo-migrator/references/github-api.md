# GitHub API Reference for Repo Migration

## Access Methods (Priority Order)

### 1. GitHub MCP Server (if connected)
If the user has GitHub MCP connected in REFINET, use MCP tools directly. This is the fastest path and handles authentication automatically.

### 2. GitHub REST API (Public Repos — No Auth Required)

**Base URL**: `https://api.github.com`

**Rate limits**: 60 requests/hour (unauthenticated), 5000/hour (with token)

#### Get Repository Info
```
GET /repos/{owner}/{repo}
```
Returns: repo metadata (default branch, description, language, size)

#### Get Repo Tree (Recursive)
```
GET /repos/{owner}/{repo}/git/trees/{branch}?recursive=1
```
Returns: full file tree with paths, types (blob/tree), sizes, SHAs

This is the key endpoint — one call returns every file path in the repo.

#### Get File Contents
```
GET /repos/{owner}/{repo}/contents/{path}?ref={branch}
```
Returns: base64-encoded file content (for files < 1MB)

#### Get Raw File (Large Files)
```
GET https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}
```
Returns: raw file content (no size limit, no rate limit counting)

### 3. Git Clone (Fallback for Large Repos)
```bash
git clone --depth 1 --single-branch --branch main https://github.com/{owner}/{repo}.git /tmp/repo-{hash}
```
Shallow clone — only latest commit, minimal bandwidth.

## URL Parsing Patterns

| URL Format | Regex |
|---|---|
| `github.com/owner/repo` | `github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$` |
| `github.com/owner/repo/tree/branch` | `github\.com/([^/]+)/([^/]+)/tree/([^/]+)(?:/(.*))?` |
| `github.com/owner/repo/blob/branch/path` | `github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.*)` |

## File Filtering Strategy

After fetching the repo tree, filter for contract files:

```python
CONTRACT_GLOBS = [
    "**/*.sol",       # Solidity
    "**/*.vy",        # Vyper
    "**/programs/**/*.rs",  # Anchor (Solana) programs dir
    "**/*.move",      # Move
    "**/*.clar",      # Clarity
    "**/*.teal",      # TEAL
    "**/*.abi",       # Pre-compiled ABI
    "**/artifacts/**/*.json",   # Hardhat artifacts
    "**/out/**/*.json",         # Foundry artifacts
    "**/build/**/*.json",       # Truffle artifacts
    "**/target/idl/*.json",     # Anchor IDL
]

EXCLUDE_PATTERNS = [
    "node_modules/", "lib/", ".git/", "test/", "tests/",
    "mock/", "mocks/", "script/", "scripts/", "migrations/"
]
```

## Response Handling

```python
import httpx

async def fetch_repo_tree(owner: str, repo: str, branch: str = "main") -> list[dict]:
    """Fetch full repo file tree from GitHub API."""
    async with httpx.AsyncClient() as client:
        # Try with specified branch, fall back to 'main', then 'master'
        for b in [branch, "main", "master"]:
            r = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/git/trees/{b}",
                params={"recursive": "1"},
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=30
            )
            if r.status_code == 200:
                data = r.json()
                return [
                    {"path": item["path"], "type": item["type"], "size": item.get("size", 0)}
                    for item in data.get("tree", [])
                    if item["type"] == "blob"
                ]
        return []


async def fetch_file_content(owner: str, repo: str, path: str, branch: str = "main") -> str:
    """Fetch raw file content from GitHub."""
    async with httpx.AsyncClient() as client:
        # Use raw.githubusercontent.com (no rate limit, no base64)
        r = await client.get(
            f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}",
            timeout=30
        )
        if r.status_code == 200:
            return r.text
    return ""
```
