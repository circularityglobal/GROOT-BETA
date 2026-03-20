"""
REFINET Cloud — Vector Memory Models
Hybrid vector search: structured SQLAlchemy tables + sqlite-vec virtual table.
Tables in public.db (user-facing, per-agent data).
"""

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Text, ForeignKey
)
from sqlalchemy.sql import func
from api.database import PublicBase
import uuid


def new_uuid() -> str:
    return str(uuid.uuid4())


class VectorMemory(PublicBase):
    """Persistent memory with vector embedding for KNN similarity search."""
    __tablename__ = "vector_memories"

    id = Column(String, primary_key=True, default=new_uuid)
    agent_id = Column(String, ForeignKey("agent_registrations.id", ondelete="CASCADE"),
                      nullable=False, index=True)
    content = Column(Text, nullable=False)
    memory_type = Column(String, nullable=False, index=True)   # user | system | blockchain | tool
    metadata_json = Column(Text, nullable=True)                 # JSON blob for extensibility
    importance = Column(Float, default=0.5)                     # 0.0–1.0, subject to decay
    embedding_json = Column(Text, nullable=True)                # JSON-serialized 384-dim (cache)
    access_count = Column(Integer, default=0)
    last_accessed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())


class VectorInteraction(PublicBase):
    """Agent interaction log — input/output pairs for context linking."""
    __tablename__ = "vector_interactions"

    id = Column(String, primary_key=True, default=new_uuid)
    agent_id = Column(String, ForeignKey("agent_registrations.id", ondelete="CASCADE"),
                      nullable=False, index=True)
    input_text = Column(Text, nullable=False)
    output_text = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class VectorMemoryLink(PublicBase):
    """Links memories to the interactions that produced or used them."""
    __tablename__ = "vector_memory_links"

    id = Column(String, primary_key=True, default=new_uuid)
    memory_id = Column(String, ForeignKey("vector_memories.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    interaction_id = Column(String, ForeignKey("vector_interactions.id", ondelete="CASCADE"),
                            nullable=False, index=True)
    relevance_score = Column(Float, default=1.0)
    created_at = Column(DateTime, server_default=func.now())
