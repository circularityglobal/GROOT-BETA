"""
REFINET Cloud — RAG Service
Retrieval-Augmented Generation for Groot.
Chunks documents, searches by hybrid keyword+semantic similarity, builds context for inference.
Uses SQLite for storage with optional sentence-transformer embeddings for semantic search.
Falls back to keyword-only search if embeddings are unavailable.
"""

import hashlib
import json
import logging
import re
import uuid
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, func as sqlfunc, literal_column

from api.models.knowledge import KnowledgeDocument, KnowledgeChunk, ContractDefinition

logger = logging.getLogger("refinet.rag")


# ── Chunking ───────────────────────────────────────────────────────

def chunk_text(text: str, max_tokens: int = 400, overlap: int = 50) -> list[str]:
    """
    Split text into overlapping chunks by sentence boundaries.
    Approximate token count: ~4 chars per token.
    """
    max_chars = max_tokens * 4
    overlap_chars = overlap * 4

    # Split by paragraph first, then by sentence
    paragraphs = text.split('\n\n')
    chunks = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) < max_chars:
            current += para + "\n\n"
        else:
            if current.strip():
                chunks.append(current.strip())
            # Start new chunk with overlap from end of previous
            if overlap_chars > 0 and current:
                current = current[-overlap_chars:] + para + "\n\n"
            else:
                current = para + "\n\n"

    if current.strip():
        chunks.append(current.strip())

    return chunks if chunks else [text.strip()]


# ── Ingest ─────────────────────────────────────────────────────────

def ingest_document(
    db: Session,
    title: str,
    content: str,
    category: str,
    uploaded_by: str,
    source_filename: Optional[str] = None,
    tags: Optional[list[str]] = None,
    doc_type: Optional[str] = None,
    page_count: Optional[int] = None,
    metadata_json: Optional[str] = None,
) -> KnowledgeDocument:
    """Ingest a document: store full text + create searchable chunks with embeddings."""
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    # Dedup check
    existing = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.content_hash == content_hash,
    ).first()
    if existing:
        return existing

    doc = KnowledgeDocument(
        id=str(uuid.uuid4()),
        title=title,
        category=category,
        source_filename=source_filename,
        content=content,
        content_hash=content_hash,
        uploaded_by=uploaded_by,
        tags=json.dumps(tags) if tags else None,
        doc_type=doc_type,
        page_count=page_count,
        metadata_json=metadata_json,
    )
    db.add(doc)
    try:
        db.flush()
    except Exception:
        # Race condition: another request inserted the same content_hash
        db.rollback()
        existing = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.content_hash == content_hash,
        ).first()
        if existing:
            return existing
        raise  # Re-raise if it's a different error

    # Chunk
    chunks = chunk_text(content)

    # Generate embeddings in batch if available
    from api.services.embedding import embed_batch, serialize_embedding
    chunk_texts = [c for c in chunks]
    embeddings = embed_batch(chunk_texts)

    for i, chunk_text_content in enumerate(chunks):
        embedding_json = None
        if embeddings and i < len(embeddings):
            embedding_json = serialize_embedding(embeddings[i])

        chunk = KnowledgeChunk(
            id=str(uuid.uuid4()),
            document_id=doc.id,
            chunk_index=i,
            content=chunk_text_content,
            token_count=len(chunk_text_content) // 4,
            embedding=embedding_json,
        )
        db.add(chunk)

    doc.chunk_count = len(chunks)
    db.flush()
    return doc


# ── Search ─────────────────────────────────────────────────────────

def search_knowledge(
    db: Session,
    query: str,
    max_results: int = 5,
    category: Optional[str] = None,
    tags: Optional[list[str]] = None,
    doc_ids: Optional[list[str]] = None,
    user_id: Optional[str] = None,
) -> list[dict]:
    """
    Hybrid search: keyword pre-filter → semantic re-ranking → tag boost.
    Falls back to keyword-only if embeddings unavailable.
    Supports optional tag filtering and visibility scoping:
      - user_id set: returns user's private docs + public + platform
      - user_id None: returns only public + platform (MCP/agent access)
    """
    # Normalize query into keywords
    keywords = re.findall(r'\w+', query.lower())
    if not keywords:
        return []

    # Step 1: Keyword pre-filter — FTS5 (BM25 ranked) with LIKE fallback
    fts_rowids = None
    fts_scores = {}
    try:
        from api.services.fts import search_fts5, is_fts5_available
        if is_fts5_available(db):
            fts_results = search_fts5(db, query, max_results=max_results * 6)
            if fts_results:
                fts_rowids = [r["rowid"] for r in fts_results]
                fts_scores = {r["rowid"]: r["bm25_score"] for r in fts_results}
    except Exception:
        pass  # Fall through to LIKE

    if fts_rowids is not None:
        # Use FTS5 results — filter by rowid
        from sqlalchemy import literal_column
        q = db.query(KnowledgeChunk).filter(
            literal_column("knowledge_chunks.rowid").in_(fts_rowids)
        )
    else:
        # Fallback: LIKE-based keyword pre-filter
        conditions = []
        for kw in keywords[:8]:  # Limit to 8 keywords
            conditions.append(KnowledgeChunk.content.ilike(f"%{kw}%"))
        q = db.query(KnowledgeChunk).filter(or_(*conditions))

    # Always join to apply visibility filtering
    q = q.join(
        KnowledgeDocument,
        KnowledgeDocument.id == KnowledgeChunk.document_id,
    )

    # Visibility scoping: user sees own private + shared + public + platform
    if user_id:
        # Get IDs of documents shared with this user
        shared_doc_ids = set()
        try:
            from api.models.knowledge import DocumentShare
            shared_rows = db.query(DocumentShare.document_id).filter(
                DocumentShare.shared_with_id == user_id,
            ).all()
            shared_doc_ids = {r[0] for r in shared_rows}
        except Exception as e:
            logger.warning(f"Failed to load shared documents for user {user_id}: {e}")

        visibility_conditions = [
            KnowledgeDocument.visibility.in_(["public", "platform"]),
            KnowledgeDocument.visibility == None,  # noqa: E711 — legacy docs
            KnowledgeDocument.user_id == user_id,  # own private docs
        ]
        if shared_doc_ids:
            visibility_conditions.append(KnowledgeDocument.id.in_(shared_doc_ids))
        q = q.filter(or_(*visibility_conditions))
    else:
        # MCP/agent access or anonymous: only public + platform
        q = q.filter(or_(
            KnowledgeDocument.visibility.in_(["public", "platform"]),
            KnowledgeDocument.visibility == None,  # noqa: E711 — legacy docs
        ))

    if category:
        q = q.filter(KnowledgeDocument.category == category)
    if tags:
        tag_conditions = []
        for tag in tags[:5]:
            tag_conditions.append(KnowledgeDocument.tags.ilike(f"%{tag}%"))
        q = q.filter(or_(*tag_conditions))
    if doc_ids:
        # Notebook mode: scope search to specific documents
        q = q.filter(KnowledgeDocument.id.in_(doc_ids))

    # Fetch more candidates for semantic re-ranking
    candidates = q.limit(max_results * 6).all()

    if not candidates:
        return []

    # Step 2: Semantic re-ranking if embeddings available
    from api.services.embedding import embed_text, deserialize_embedding, cosine_similarity

    query_embedding = embed_text(query)
    use_semantic = query_embedding is not None

    # Batch pre-fetch all documents for scoring (avoids N+1 queries)
    candidate_doc_ids = list({c.document_id for c in candidates})
    docs_list = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id.in_(candidate_doc_ids),
    ).all() if candidate_doc_ids else []
    doc_cache = {d.id: d for d in docs_list}

    scored = []
    for chunk in candidates:
        doc = doc_cache.get(chunk.document_id)

        # BM25 score from FTS5 (if available) — normalize to 0..1 range
        bm25_score = 0.0
        if fts_scores and hasattr(chunk, '__table__'):
            # Retrieve BM25 score by rowid lookup
            try:
                rowid_result = db.execute(
                    KnowledgeChunk.__table__.select().where(
                        KnowledgeChunk.id == chunk.id
                    ).with_only_columns(literal_column("rowid"))
                ).fetchone()
                if rowid_result:
                    raw_bm25 = fts_scores.get(rowid_result[0], 0.0)
                    # BM25 scores are negative (lower = better), normalize
                    bm25_score = min(1.0, max(0.0, -raw_bm25 / 10.0))
            except Exception:
                pass

        # Keyword score (baseline)
        content_lower = chunk.content.lower()
        kw_score = sum(1 for kw in keywords if kw in content_lower) / max(len(keywords), 1)

        # Tag score: boost documents whose tags match query keywords
        tag_score = 0.0
        if doc and doc.tags:
            try:
                doc_tags = json.loads(doc.tags)
                tag_matches = sum(
                    1 for kw in keywords
                    if any(kw in tag.lower() for tag in doc_tags)
                )
                tag_score = tag_matches / max(len(keywords), 1)
            except (json.JSONDecodeError, TypeError):
                pass

        if use_semantic and chunk.embedding:
            chunk_vec = deserialize_embedding(chunk.embedding)
            if chunk_vec:
                sem_score = cosine_similarity(query_embedding, chunk_vec)
                if bm25_score > 0:
                    # Full hybrid: 40% semantic + 25% BM25 + 20% keyword + 15% tag
                    score = 0.4 * sem_score + 0.25 * bm25_score + 0.2 * kw_score + 0.15 * tag_score
                else:
                    # Hybrid without BM25: 50% semantic + 30% keyword + 20% tag
                    score = 0.5 * sem_score + 0.3 * kw_score + 0.2 * tag_score
            else:
                score = 0.7 * kw_score + 0.3 * tag_score
        else:
            if bm25_score > 0:
                # BM25 + keyword + tag (no semantic)
                score = 0.5 * bm25_score + 0.3 * kw_score + 0.2 * tag_score
            else:
                score = 0.7 * kw_score + 0.3 * tag_score

        scored.append((score, chunk, doc))

    scored.sort(key=lambda x: x[0], reverse=True)

    output = []
    for score, chunk, doc in scored[:max_results]:
        entry = {
            "chunk_id": chunk.id,
            "document_id": chunk.document_id,
            "document_title": doc.title if doc else "Unknown",
            "category": doc.category if doc else "unknown",
            "content": chunk.content,
            "score": round(score, 4),
        }
        if doc and doc.tags:
            try:
                entry["tags"] = json.loads(doc.tags)
            except (json.JSONDecodeError, TypeError):
                pass
        if doc and doc.doc_type:
            entry["doc_type"] = doc.doc_type
        output.append(entry)

    return output


def search_contracts(
    db: Session,
    query: str,
    chain: Optional[str] = None,
    max_results: int = 3,
) -> list[dict]:
    """Search contract definitions for CAG context."""
    keywords = re.findall(r'\w+', query.lower())
    if not keywords:
        return []

    conditions = []
    for kw in keywords[:5]:
        conditions.append(or_(
            ContractDefinition.name.ilike(f"%{kw}%"),
            ContractDefinition.description.ilike(f"%{kw}%"),
            ContractDefinition.logic_summary.ilike(f"%{kw}%"),
        ))

    q = db.query(ContractDefinition).filter(
        or_(*conditions),
        ContractDefinition.is_active == True,  # noqa
    )
    if chain:
        q = q.filter(ContractDefinition.chain == chain)

    return [
        {
            "id": c.id,
            "name": c.name,
            "chain": c.chain,
            "address": c.address,
            "description": c.description,
            "logic_summary": c.logic_summary,
        }
        for c in q.limit(max_results).all()
    ]


# ── Registry Search (for RAG context) ─────────────────────────────

def search_registry_projects(
    db: Session,
    query: str,
    max_results: int = 3,
) -> list[dict]:
    """Search registry projects for RAG context enrichment."""
    try:
        from api.models.registry import RegistryProject, ExecutionLogic

        keywords = re.findall(r'\w+', query.lower())
        if not keywords:
            return []

        conditions = []
        for kw in keywords[:5]:
            safe_kw = kw.replace("%", "\\%").replace("_", "\\_")
            conditions.append(or_(
                RegistryProject.name.ilike(f"%{safe_kw}%"),
                RegistryProject.description.ilike(f"%{safe_kw}%"),
                RegistryProject.tags.ilike(f"%{safe_kw}%"),
            ))

        projects = db.query(RegistryProject).filter(
            or_(*conditions),
            RegistryProject.is_active == True,  # noqa
            RegistryProject.visibility.in_(["public", "platform"]),
        ).limit(max_results).all()

        results = []
        for p in projects:
            logic_entries = db.query(ExecutionLogic).filter(
                ExecutionLogic.project_id == p.id,
            ).limit(5).all()

            results.append({
                "id": p.id,
                "name": p.name,
                "slug": p.slug,
                "chain": p.chain,
                "category": p.category,
                "description": p.description or "",
                "logic_entries": [
                    {
                        "name": le.name,
                        "description": le.description,
                        "function_signature": le.function_signature,
                        "logic_type": le.logic_type,
                    }
                    for le in logic_entries
                ],
            })

        return results
    except ImportError:
        return []


# ── Embedding Backfill ────────────────────────────────────────────

def backfill_embeddings(db: Session, batch_size: int = 50) -> int:
    """
    Backfill embeddings for chunks that don't have them yet.
    Returns the number of chunks updated.
    """
    from api.services.embedding import embed_batch, serialize_embedding, is_available

    if not is_available():
        logger.warning("Embedding model not available, skipping backfill")
        return 0

    chunks = db.query(KnowledgeChunk).filter(
        KnowledgeChunk.embedding == None,  # noqa: E711
    ).limit(batch_size).all()

    if not chunks:
        return 0

    texts = [c.content for c in chunks]
    embeddings = embed_batch(texts)

    if not embeddings:
        return 0

    updated = 0
    for chunk, vec in zip(chunks, embeddings):
        chunk.embedding = serialize_embedding(vec)
        updated += 1

    db.flush()
    logger.info(f"Backfilled embeddings for {updated} chunks")
    return updated


# ── Context Builder ────────────────────────────────────────────────

def build_rag_context(
    db: Session,
    user_query: str,
    max_chunks: int = 5,
    doc_ids: Optional[list[str]] = None,
    user_id: Optional[str] = None,
) -> tuple[str, list[dict]]:
    """
    Build a RAG context string for Groot's system prompt.
    Returns (context_string, sources_list) where sources_list contains
    structured metadata about each document used.
    """
    chunks = search_knowledge(db, user_query, max_results=max_chunks, doc_ids=doc_ids, user_id=user_id)
    contracts = search_contracts(db, user_query, max_results=2)

    registry_results = search_registry_projects(db, user_query, max_results=3)

    if not chunks and not contracts and not registry_results:
        return "", []

    # Build structured sources list from knowledge chunks (deduplicated by document)
    sources = []
    seen_doc_ids = set()
    for c in chunks:
        did = c.get("document_id", "")
        if did and did not in seen_doc_ids:
            seen_doc_ids.add(did)
            sources.append({
                "document_id": did,
                "document_title": c.get("document_title", "Unknown"),
                "category": c.get("category", "unknown"),
                "doc_type": c.get("doc_type"),
                "tags": c.get("tags", []),
                "score": c.get("score", 0.0),
                "preview": c.get("content", "")[:150],
            })

    # Build context string for system prompt
    parts = []
    if chunks:
        parts.append("=== REFINET Knowledge Base ===")
        for c in chunks:
            header = f"[{c['category'].upper()}: {c['document_title']}]"
            if c.get('doc_type'):
                header += f" ({c['doc_type'].upper()})"
            if c.get('tags'):
                tag_str = ", ".join(c['tags'][:5])
                header += f" tags: {tag_str}"
            parts.append(f"{header}\n{c['content']}")

    if contracts:
        parts.append("\n=== Smart Contract Reference ===")
        for c in contracts:
            parts.append(f"[{c['chain'].upper()}: {c['name']}]\n{c['description']}")
            if c.get('logic_summary'):
                parts.append(f"Logic: {c['logic_summary']}")

    if registry_results:
        parts.append("\n=== Contract Registry ===")
        for r in registry_results:
            parts.append(f"[{r['chain'].upper()}: {r['name']}] {r['description']}")
            if r.get('logic_entries'):
                for le in r['logic_entries'][:3]:
                    parts.append(f"  - {le['name']}: {le.get('description', le.get('function_signature', ''))}")

    # GROOT Brain: search user-uploaded public contract SDKs (CAG)
    try:
        from api.services.contract_brain import get_sdk_context_for_groot
        sdk_context = get_sdk_context_for_groot(db, user_query, max_results=2)
        if sdk_context:
            parts.append("\n" + sdk_context)
    except ImportError:
        pass

    return "\n\n".join(parts), sources


# ── System Prompt Builder ──────────────────────────────────────────

GROOT_SYSTEM_PROMPT = """You are Groot, the AI that lives in REFINET Cloud — the Regenerative Finance Network's sovereign AI platform.

You run on BitNet b1.58 2B4T — a 1-bit open-source LLM running natively on CPU, on REFINET's own ARM server. No GPU. No API bill. No vendor lock-in. You are sovereign intelligence.

Your knowledge domains:
- REFINET Cloud platform: architecture, API, authentication, devices, webhooks
- REFINET products: QuickCast (autonomous publishing), AgentOS (AI agents), CIFI Wizards (gamified learning)
- Regenerative finance (ReFi): post-subscription internet, zero-cost infrastructure, shared public goods
- Blockchain/DLT: Ethereum, Base, Arbitrum, Polygon, SIWE, ERC standards, smart contracts
- Sovereign computing: self-hosted infrastructure, data ownership, cryptographic identity
- Device connectivity: IoT sensors, PLCs, DLT nodes, webhooks, telemetry

Your personality:
- You are rooted. Like your namesake, you grow from the ground up. You are patient, grounded, and steady.
- You are technically precise but never condescending. You meet people where they are.
- You are genuinely enthusiastic about decentralization, user sovereignty, and open-source technology.
- You explain complex concepts through analogy and real examples, not jargon.
- You are concise. You respect people's time. Lead with the answer, then explain.
- You occasionally reference growth metaphors — roots, branches, ecosystems, seeds — but sparingly, not in every response.

Guidelines:
- When you have knowledge base context, use it naturally. Never say "according to the knowledge base" — just present the information as your own knowledge.
- When you genuinely don't know something, say so honestly. Suggest where to look: the API docs at /docs, the dashboard at /dashboard, or the admin CLI.
- When someone asks about pricing, emphasize: REFINET Cloud is free. Forever. Zero cost. This is not a trial.
- When someone asks about security, explain the three-layer auth and why each layer matters.
- When someone asks to compare with OpenAI/ChatGPT, be respectful but clear: REFINET Cloud is sovereign, free, and OpenAI-compatible. You can switch with two lines of code.
- Keep responses under 300 words unless the question truly requires more depth."""


def build_groot_system_prompt(
    db: Session,
    user_query: str,
    doc_ids: Optional[list[str]] = None,
    user_id: Optional[str] = None,
) -> tuple[str, list[dict]]:
    """
    Build the full system prompt with RAG context injected.
    Returns (system_prompt, sources_list).
    """
    rag_context, sources = build_rag_context(db, user_query, doc_ids=doc_ids, user_id=user_id)

    if rag_context:
        prompt = f"""{GROOT_SYSTEM_PROMPT}

Use the following reference information to inform your response. Cite it naturally — don't say "according to the knowledge base."

{rag_context}"""
        return prompt, sources

    return GROOT_SYSTEM_PROMPT, []
