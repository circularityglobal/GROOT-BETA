"""
REFINET Cloud — MCP Routes
MCP server registry proxy — users call tools, REFINET handles auth.
"""

import json
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from api.database import internal_db_dependency
from api.auth.jwt import decode_access_token, verify_scope, SCOPE_INFERENCE_READ
from api.models.internal import MCPServerRegistry
from api.schemas.admin import MCPServerItem, MCPCallRequest
from api.services.mcp_proxy import call_mcp_tool

router = APIRouter(prefix="/mcp", tags=["mcp"])


def _require_auth(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        payload = decode_access_token(auth_header[7:])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    if not verify_scope(payload, SCOPE_INFERENCE_READ):
        raise HTTPException(status_code=403, detail="Requires inference:read scope")
    return payload["sub"]


@router.get("/servers")
def list_mcp_servers(
    request: Request,
    db: Session = Depends(internal_db_dependency),
):
    _require_auth(request)
    servers = db.query(MCPServerRegistry).filter(
        MCPServerRegistry.status == "active",
    ).all()
    return [
        MCPServerItem(
            id=s.id, name=s.name, url=s.url,
            transport=s.transport, auth_type=s.auth_type,
            capabilities=json.loads(s.capabilities) if s.capabilities else [],
            status=s.status, is_healthy=s.is_healthy,
        )
        for s in servers
    ]


@router.get("/servers/{name}/tools")
def get_server_tools(
    name: str,
    request: Request,
    db: Session = Depends(internal_db_dependency),
):
    _require_auth(request)
    server = db.query(MCPServerRegistry).filter(
        MCPServerRegistry.name == name,
    ).first()
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return {
        "server": name,
        "tools": json.loads(server.capabilities) if server.capabilities else [],
    }


@router.post("/call")
async def mcp_call(
    req: MCPCallRequest,
    request: Request,
    db: Session = Depends(internal_db_dependency),
):
    _require_auth(request)
    server = db.query(MCPServerRegistry).filter(
        MCPServerRegistry.name == req.server,
        MCPServerRegistry.status == "active",
    ).first()
    if not server:
        raise HTTPException(status_code=404, detail=f"MCP server '{req.server}' not found")

    if not server.is_healthy:
        raise HTTPException(status_code=503, detail=f"MCP server '{req.server}' is unhealthy")

    result = await call_mcp_tool(
        server_url=server.url,
        transport=server.transport,
        auth_type=server.auth_type,
        auth_value=server.auth_value,
        tool_name=req.tool,
        arguments=req.arguments or {},
    )

    return {"server": req.server, "tool": req.tool, "result": result}
