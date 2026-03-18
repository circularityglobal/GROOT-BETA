"""
REFINET Cloud — Document Comparison Service
Compare two documents by semantic similarity, keyword overlap, and structural diff.
Uses existing embedding service. No external APIs. Fully sovereign.
"""

import json
import logging
import re
from collections import Counter
from typing import Optional

from sqlalchemy.orm import Session

from api.models.knowledge import KnowledgeDocument, KnowledgeChunk

logger = logging.getLogger("refinet.document_compare")


def compare_documents(db: Session, doc_id_a: str, doc_id_b: str) -> dict:
    """
    Compare two knowledge base documents.
    Returns similarity scores, keyword overlap, structural diff, and tag overlap.
    """
    doc_a = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == doc_id_a,
        KnowledgeDocument.is_active == True,  # noqa: E712
    ).first()
    doc_b = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == doc_id_b,
        KnowledgeDocument.is_active == True,  # noqa: E712
    ).first()

    if not doc_a:
        return {"error": f"Document not found: {doc_id_a}"}
    if not doc_b:
        return {"error": f"Document not found: {doc_id_b}"}

    result = {
        "doc_a": {"id": doc_a.id, "title": doc_a.title, "category": doc_a.category},
        "doc_b": {"id": doc_b.id, "title": doc_b.title, "category": doc_b.category},
        "semantic_similarity": _compute_semantic_similarity(doc_a.content, doc_b.content),
        "keyword_overlap": _compute_keyword_overlap(doc_a.content, doc_b.content),
        "structural_diff": _compute_structural_diff(doc_a, doc_b, db),
        "tag_overlap": _compute_tag_overlap(
            _parse_tags(doc_a.tags),
            _parse_tags(doc_b.tags),
        ),
    }

    return result


def _parse_tags(tags_json: Optional[str]) -> list[str]:
    """Safely parse tags JSON."""
    if not tags_json:
        return []
    try:
        return json.loads(tags_json)
    except (json.JSONDecodeError, TypeError):
        return []


def _compute_semantic_similarity(text_a: str, text_b: str) -> float:
    """Embed both documents (truncated) and compute cosine similarity."""
    try:
        from api.services.embedding import embed_text, cosine_similarity

        # Truncate to first 2000 chars for embedding (model has input limits)
        vec_a = embed_text(text_a[:2000])
        vec_b = embed_text(text_b[:2000])

        if vec_a is None or vec_b is None:
            return 0.0

        return round(cosine_similarity(vec_a, vec_b), 4)
    except Exception as e:
        logger.warning(f"Semantic similarity computation failed: {e}")
        return 0.0


def _compute_keyword_overlap(text_a: str, text_b: str) -> dict:
    """Extract top keywords from each document and compute Jaccard similarity."""
    kw_a = _extract_top_keywords(text_a, top_n=50)
    kw_b = _extract_top_keywords(text_b, top_n=50)

    set_a = set(kw_a)
    set_b = set(kw_b)

    intersection = set_a & set_b
    union = set_a | set_b

    jaccard = len(intersection) / max(len(union), 1)

    return {
        "score": round(jaccard, 4),
        "shared_keywords": sorted(intersection)[:20],
        "unique_to_a": sorted(set_a - set_b)[:15],
        "unique_to_b": sorted(set_b - set_a)[:15],
        "keywords_a_count": len(set_a),
        "keywords_b_count": len(set_b),
    }


def _compute_structural_diff(
    doc_a: KnowledgeDocument,
    doc_b: KnowledgeDocument,
    db: Session,
) -> dict:
    """Compare document structure: length, chunks, headings."""
    len_a = len(doc_a.content) if doc_a.content else 0
    len_b = len(doc_b.content) if doc_b.content else 0

    chunks_a = db.query(KnowledgeChunk).filter(
        KnowledgeChunk.document_id == doc_a.id,
    ).count()
    chunks_b = db.query(KnowledgeChunk).filter(
        KnowledgeChunk.document_id == doc_b.id,
    ).count()

    # Extract headings (markdown-style or section markers)
    headings_a = _extract_headings(doc_a.content or "")
    headings_b = _extract_headings(doc_b.content or "")

    shared_headings = [h for h in headings_a if h.lower() in {hb.lower() for hb in headings_b}]

    return {
        "length_a": len_a,
        "length_b": len_b,
        "length_ratio": round(len_a / max(len_b, 1), 2),
        "chunk_count_a": chunks_a,
        "chunk_count_b": chunks_b,
        "doc_type_a": doc_a.doc_type,
        "doc_type_b": doc_b.doc_type,
        "headings_a": headings_a[:10],
        "headings_b": headings_b[:10],
        "shared_headings": shared_headings[:10],
    }


def _compute_tag_overlap(tags_a: list[str], tags_b: list[str]) -> dict:
    """Jaccard similarity of tag sets."""
    set_a = set(t.lower() for t in tags_a)
    set_b = set(t.lower() for t in tags_b)

    intersection = set_a & set_b
    union = set_a | set_b

    jaccard = len(intersection) / max(len(union), 1)

    return {
        "score": round(jaccard, 4),
        "shared_tags": sorted(intersection),
        "unique_to_a": sorted(set_a - set_b),
        "unique_to_b": sorted(set_b - set_a),
    }


def _extract_top_keywords(text: str, top_n: int = 50) -> list[str]:
    """Extract top keywords by frequency, filtering stop words."""
    stop = frozenset({
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "are", "was", "were", "be",
        "been", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "shall", "can", "not", "this",
        "that", "these", "those", "it", "its", "they", "them", "their",
        "we", "our", "you", "your", "he", "she", "him", "her",
    })

    words = re.findall(r'[a-z][a-z0-9]+', text.lower())
    words = [w for w in words if w not in stop and len(w) > 2]
    counts = Counter(words)
    return [w for w, _ in counts.most_common(top_n)]


def _extract_headings(text: str) -> list[str]:
    """Extract headings from markdown or section-style text."""
    headings = []

    # Markdown headings
    for match in re.finditer(r'^#{1,4}\s+(.+)$', text, re.MULTILINE):
        headings.append(match.group(1).strip())

    # Section markers (=== Section ===)
    for match in re.finditer(r'^===\s+(.+?)\s+===$', text, re.MULTILINE):
        headings.append(match.group(1).strip())

    return headings
