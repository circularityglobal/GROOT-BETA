"""
REFINET Cloud — Embedding Service
CPU-native semantic embeddings for RAG.
Uses sentence-transformers all-MiniLM-L6-v2 (22MB, 384-dim).
Falls back gracefully if model is unavailable.
"""

import json
import logging
import math
from typing import Optional

logger = logging.getLogger("refinet.embedding")

# Lazy-loaded singleton
_model = None
_model_load_attempted = False


def _load_model():
    """Load the embedding model once. Returns None if unavailable."""
    global _model, _model_load_attempted
    if _model_load_attempted:
        return _model
    _model_load_attempted = True
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Embedding model loaded: all-MiniLM-L6-v2 (384-dim)")
    except Exception as e:
        logger.warning(f"Embedding model unavailable (keyword search will be used): {e}")
        _model = None
    return _model


def embed_text(text: str) -> Optional[list[float]]:
    """Embed a single text string. Returns 384-dim float list or None if model unavailable."""
    model = _load_model()
    if model is None:
        return None
    try:
        vec = model.encode(text, normalize_embeddings=True)
        return vec.tolist()
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        return None


def embed_batch(texts: list[str]) -> Optional[list[list[float]]]:
    """Embed multiple texts in batch. Returns list of 384-dim vectors or None."""
    model = _load_model()
    if model is None:
        return None
    try:
        vecs = model.encode(texts, normalize_embeddings=True, batch_size=32)
        return [v.tolist() for v in vecs]
    except Exception as e:
        logger.error(f"Batch embedding error: {e}")
        return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors. Pure Python, no numpy required."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def serialize_embedding(vec: list[float]) -> str:
    """Serialize embedding to compact JSON for SQLite TEXT column."""
    return json.dumps([round(v, 6) for v in vec])


def deserialize_embedding(data: str) -> Optional[list[float]]:
    """Deserialize embedding from JSON string."""
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return None


def is_available() -> bool:
    """Check if the embedding model is available."""
    return _load_model() is not None
