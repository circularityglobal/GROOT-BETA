"""
REFINET Cloud — Knowledge Base Models
Admin-managed document store for Groot RAG.
Documents are chunked and stored in SQLite for retrieval.
Prepares for CAG (Contract Augmented Generation) with blockchain/DLT logic.
"""

from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from api.database import PublicBase
import uuid


def new_uuid() -> str:
    return str(uuid.uuid4())


class KnowledgeDocument(PublicBase):
    """A document uploaded by admin for Groot's knowledge base."""
    __tablename__ = "knowledge_documents"

    id = Column(String, primary_key=True, default=new_uuid)
    title = Column(String, nullable=False)
    category = Column(String, nullable=False)  # about | product | docs | blockchain | contract | faq
    source_filename = Column(String, nullable=True)
    content = Column(Text, nullable=False)  # Full document text
    content_hash = Column(String, nullable=False, unique=True)  # SHA256 for dedup
    chunk_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    uploaded_by = Column(String, nullable=False)  # admin username or user_id
    user_id = Column(String, nullable=True)      # Owner user ID (null = platform/admin doc)
    visibility = Column(String, default="platform")  # private | public | platform
    tags = Column(Text, nullable=True)          # JSON array: ["defi", "staking", "erc20 token"]
    doc_type = Column(String, nullable=True)     # pdf | docx | xlsx | csv | txt | md | json | sol
    page_count = Column(Integer, nullable=True)  # pages (PDF) or sheets (XLSX)
    metadata_json = Column(Text, nullable=True)  # JSON: {"author": "...", "file_size": 12345, ...}
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())


class KnowledgeChunk(PublicBase):
    """A chunked segment of a document for retrieval."""
    __tablename__ = "knowledge_chunks"

    id = Column(String, primary_key=True, default=new_uuid)
    document_id = Column(String, ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)  # The chunk text
    token_count = Column(Integer, default=0)
    embedding = Column(Text, nullable=True)  # JSON-serialized float array (384-dim)
    created_at = Column(DateTime, server_default=func.now())


class DocumentShare(PublicBase):
    """Share a document with another user for collaboration."""
    __tablename__ = "document_shares"

    id = Column(String, primary_key=True, default=new_uuid)
    document_id = Column(String, ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_id = Column(String, nullable=False)       # Who shared it
    shared_with_id = Column(String, nullable=False, index=True)  # Who it's shared with
    permission = Column(String, default="read")      # read | write
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("document_id", "shared_with_id", name="uq_share_doc_user"),
    )


class ContractDefinition(PublicBase):
    """
    CAG: Contract Augmented Generation
    Stores blockchain/DLT contract definitions, ABIs, and logic descriptions
    that Groot can reference when answering questions about on-chain operations.
    """
    __tablename__ = "contract_definitions"

    id = Column(String, primary_key=True, default=new_uuid)
    name = Column(String, nullable=False)  # e.g. "REFINET Token", "Staking Contract"
    chain = Column(String, nullable=False)  # ethereum | base | arbitrum | polygon
    address = Column(String, nullable=True)  # Contract address if deployed
    abi_json = Column(Text, nullable=True)  # Full ABI JSON
    description = Column(Text, nullable=False)  # Human-readable explanation
    logic_summary = Column(Text, nullable=True)  # Summarized logic for RAG context
    category = Column(String, default="defi")  # defi | token | governance | bridge | utility
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())
