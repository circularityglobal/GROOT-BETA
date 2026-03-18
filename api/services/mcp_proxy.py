"""
REFINET Cloud — MCP Proxy Service
Proxies tool calls to registered MCP servers.
Auth credentials decrypted at call time, never logged.
"""

import json
import logging
from typing import Optional

import httpx

logger = logging.getLogger("refinet.mcp")


async def call_mcp_tool(
    server_url: str,
    transport: str,
    auth_type: str,
    auth_value: Optional[str],
    tool_name: str,
    arguments: dict,
) -> dict:
    """
    Call a tool on a registered MCP server.
    Handles HTTP transport. SSE/stdio transports are roadmap items.
    """
    if transport != "http":
        return {"error": f"Transport '{transport}' not yet supported. Only HTTP is available."}

    headers = {"Content-Type": "application/json"}

    # Decrypt and apply auth
    if auth_type == "api_key" and auth_value:
        from api.routes.admin import _decrypt_internal
        try:
            decrypted = _decrypt_internal(auth_value)
            headers["Authorization"] = f"Bearer {decrypted}"
        except Exception as e:
            logger.error(f"MCP auth decryption failed: {e}")
            return {"error": "Failed to decrypt MCP server credentials"}

    # Build MCP-compatible request
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
        "id": 1,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(server_url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            if "result" in data:
                return data["result"]
            elif "error" in data:
                return {"error": data["error"]}
            return data

    except httpx.TimeoutException:
        return {"error": "MCP server timed out"}
    except Exception as e:
        logger.error(f"MCP call failed: {e}")
        return {"error": str(e)}
