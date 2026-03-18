"""REFINET Cloud — Messaging Schemas"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ── Send Message ─────────────────────────────────────────────────────

class SendDMRequest(BaseModel):
    """Send a DM to a wallet address, email alias, or ENS name."""
    recipient: str = Field(..., min_length=3, description="Address, email alias, or ENS name")
    content: str = Field(..., min_length=1, max_length=10000)
    content_type: str = Field(default="text")


class SendMessageRequest(BaseModel):
    """Send a message in an existing conversation."""
    content: str = Field(..., min_length=1, max_length=10000)
    content_type: str = Field(default="text")
    reply_to_id: Optional[str] = None
    metadata: Optional[dict] = None


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender_id: str
    sender_address: str
    content: str
    content_type: str = "text"
    reply_to_id: Optional[str] = None
    metadata: Optional[dict] = None
    is_edited: bool = False
    created_at: Optional[datetime] = None


# ── Conversations ────────────────────────────────────────────────────

class CreateGroupRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    participants: list[str] = Field(..., min_length=1)


class ParticipantResponse(BaseModel):
    user_id: str
    eth_address: str
    display_name: Optional[str] = None
    role: str = "member"


class ConversationResponse(BaseModel):
    id: str
    title: Optional[str] = None
    is_group: bool = False
    participants: list[ParticipantResponse] = []
    last_message_at: Optional[datetime] = None
    last_message_preview: Optional[str] = None
    unread_count: int = 0
    my_role: str = "member"
    created_at: Optional[datetime] = None


class ConversationListResponse(BaseModel):
    conversations: list[ConversationResponse]
    total: int = 0


class ConversationMessagesResponse(BaseModel):
    conversation_id: str
    messages: list[MessageResponse]
    has_more: bool = False


# ── Email Aliases ────────────────────────────────────────────────────

class SetCustomAliasRequest(BaseModel):
    alias: str = Field(..., min_length=3, max_length=32, pattern=r"^[a-z0-9][a-z0-9._-]*[a-z0-9]$")


class EmailAliasResponse(BaseModel):
    auto: Optional[str] = None
    custom: Optional[str] = None
    ens: Optional[str] = None
    eth_address: str


class EmailResolveRequest(BaseModel):
    email: str


class EmailResolveResponse(BaseModel):
    email: str
    eth_address: Optional[str] = None
    found: bool = False
