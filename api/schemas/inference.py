"""REFINET Cloud — Inference Schemas (OpenAI-compatible)"""

from pydantic import BaseModel, Field
from typing import Optional


class ChatMessage(BaseModel):
    role: str = Field(description="system | user | assistant")
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "bitnet-b1.58-2b"
    messages: list[ChatMessage]
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=512, ge=1, le=4096)
    stream: bool = False
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    notebook_doc_ids: Optional[list[str]] = None  # Scope RAG to specific documents


class SourceReference(BaseModel):
    """A knowledge base document used as RAG context for a response."""
    document_id: str
    document_title: str
    category: str
    doc_type: Optional[str] = None
    tags: list[str] = []
    score: float
    preview: str  # First ~150 chars of the matched chunk


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: str = "stop"


class UsageInfo(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: UsageInfo
    sources: Optional[list[SourceReference]] = None  # RAG sources used in response


class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str = "refinet"


class ModelListResponse(BaseModel):
    object: str = "list"
    data: list[ModelInfo]
