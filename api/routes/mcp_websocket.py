"""
REFINET Cloud — WebSocket Endpoint for Registry
Real-time updates, event subscriptions, and tool execution.
"""

import json
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from api.database import get_public_session
from api.middleware.protocol_auth import authenticate_token, AuthError
from api.services.mcp_gateway import dispatch_tool, list_tools
from api.services.event_bus import EventBus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


# ── Connection Manager ───────────────────────────────────────────────

class WebSocketState:
    def __init__(self, websocket: WebSocket, user_id: Optional[str] = None):
        self.websocket = websocket
        self.user_id = user_id
        self.subscriptions: Set[str] = set()
        self.filters: Dict[str, str] = {}
        self.authenticated = False
        self.last_ping = datetime.now(timezone.utc)


class ConnectionManager:
    def __init__(self):
        self.connections: Dict[str, WebSocketState] = {}
        self._counter = 0

    async def connect(self, websocket: WebSocket) -> str:
        await websocket.accept()
        self._counter += 1
        conn_id = f"ws_{self._counter}"
        self.connections[conn_id] = WebSocketState(websocket)
        return conn_id

    async def disconnect(self, conn_id: str):
        if conn_id in self.connections:
            del self.connections[conn_id]

    async def send(self, conn_id: str, message: dict):
        state = self.connections.get(conn_id)
        if state:
            try:
                await state.websocket.send_json(message)
            except Exception:
                await self.disconnect(conn_id)

    async def broadcast_event(self, event: str, data: dict):
        """Broadcast an event to all subscribers matching the channel."""
        disconnected = []
        for conn_id, state in self.connections.items():
            if not state.authenticated:
                continue

            # Check if connection is subscribed to this event
            matched = False
            for sub in state.subscriptions:
                if sub == "*" or event.startswith(sub.rstrip("*")):
                    matched = True
                    break

            if not matched:
                continue

            # Apply filters
            if state.filters:
                skip = False
                for key, value in state.filters.items():
                    if key in data and data[key] != value:
                        skip = True
                        break
                if skip:
                    continue

            try:
                await state.websocket.send_json({
                    "type": "event",
                    "channel": event,
                    "data": data,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except Exception:
                disconnected.append(conn_id)

        for conn_id in disconnected:
            await self.disconnect(conn_id)


ws_manager = ConnectionManager()


# ── WebSocket Endpoint ───────────────────────────────────────────────

@router.websocket("/ws/registry")
async def websocket_registry(websocket: WebSocket):
    conn_id = await ws_manager.connect(websocket)
    state = ws_manager.connections[conn_id]

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws_manager.send(conn_id, {
                    "type": "error",
                    "code": "INVALID_JSON",
                    "message": "Invalid JSON message",
                })
                continue

            msg_type = msg.get("type", "")

            # ── Authentication ────────────────────────────────
            if msg_type == "authenticate":
                token = msg.get("token", "")
                db_gen = get_public_session()
                db = next(db_gen)
                try:
                    result = authenticate_token(token, db)
                    state.user_id = result.user_id
                    state.authenticated = True
                    await ws_manager.send(conn_id, {
                        "type": "authenticated",
                        "user_id": result.user_id,
                        "scopes": result.scopes,
                    })
                except AuthError as e:
                    await ws_manager.send(conn_id, {
                        "type": "error",
                        "code": "AUTH_FAILED",
                        "message": e.message,
                    })
                finally:
                    db.close()

            # ── Subscribe ─────────────────────────────────────
            elif msg_type == "subscribe":
                if not state.authenticated:
                    await ws_manager.send(conn_id, {
                        "type": "error",
                        "code": "NOT_AUTHENTICATED",
                        "message": "Authenticate first",
                    })
                    continue

                channels = msg.get("channels", [])
                filters = msg.get("filters", {})
                state.subscriptions.update(channels)
                state.filters.update(filters)
                await ws_manager.send(conn_id, {
                    "type": "subscribed",
                    "channels": list(state.subscriptions),
                })

            # ── Unsubscribe ───────────────────────────────────
            elif msg_type == "unsubscribe":
                channels = msg.get("channels", [])
                state.subscriptions -= set(channels)
                await ws_manager.send(conn_id, {
                    "type": "unsubscribed",
                    "channels": list(state.subscriptions),
                })

            # ── Tool Call ─────────────────────────────────────
            elif msg_type == "tool_call":
                if not state.authenticated:
                    await ws_manager.send(conn_id, {
                        "type": "error",
                        "code": "NOT_AUTHENTICATED",
                        "message": "Authenticate first",
                    })
                    continue

                req_id = msg.get("id", "")
                tool = msg.get("tool", "")
                arguments = msg.get("arguments", {})

                db_gen = get_public_session()
                db = next(db_gen)
                try:
                    result = await dispatch_tool(tool, arguments, db, user_id=state.user_id)
                finally:
                    db.close()
                await ws_manager.send(conn_id, {
                    "type": "tool_result",
                    "id": req_id,
                    "result": result.get("result"),
                    "error": result.get("error"),
                })

            # ── List Tools ────────────────────────────────────
            elif msg_type == "list_tools":
                tools = list_tools()
                await ws_manager.send(conn_id, {
                    "type": "tools",
                    "tools": tools,
                })

            # ── Ping/Pong ─────────────────────────────────────
            elif msg_type == "ping":
                state.last_ping = datetime.now(timezone.utc)
                await ws_manager.send(conn_id, {"type": "pong"})

            else:
                await ws_manager.send(conn_id, {
                    "type": "error",
                    "code": "UNKNOWN_TYPE",
                    "message": f"Unknown message type: {msg_type}",
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error ({conn_id}): {e}")
    finally:
        await ws_manager.disconnect(conn_id)
