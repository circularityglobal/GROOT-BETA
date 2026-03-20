"""
REFINET Cloud — Embedding Service
CPU-native semantic embeddings for RAG.
Uses sentence-transformers all-MiniLM-L6-v2 (22MB, 384-dim).
Falls back gracefully if model is unavailable.
"""

import json
import logging
import math
import threading
from collections import OrderedDict
from typing import Optional

logger = logging.getLogger("refinet.embedding")

# Lazy-loaded singleton
_model = None
_model_load_attempted = False

# In-memory embedding cache — 512 entries x 384 dims x 4 bytes ≈ 750KB
_EMBED_CACHE_MAX = 512
_embed_cache: OrderedDict[str, list[float]] = OrderedDict()
_embed_cache_lock = threading.Lock()


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
    """Embed a single text string. Returns 384-dim float list or None if model unavailable.
    Results are cached in an LRU cache (max 512 entries, ~750KB)."""
    # Check cache first
    with _embed_cache_lock:
        cached = _embed_cache.get(text)
        if cached is not None:
            _embed_cache.move_to_end(text)
            return cached

    model = _load_model()
    if model is None:
        return None
    try:
        vec = model.encode(text, normalize_embeddings=True)
        result = vec.tolist()
        # Store in cache
        with _embed_cache_lock:
            _embed_cache[text] = result
            _embed_cache.move_to_end(text)
            while len(_embed_cache) > _EMBED_CACHE_MAX:
                _embed_cache.popitem(last=False)
        return result
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        return None


def embed_batch(texts: list[str]) -> Optional[list[list[float]]]:
    """Embed multiple texts in batch. Returns list of 384-dim vectors or None.
    Checks cache for each text, only computes embeddings for cache misses."""
    model = _load_model()
    if model is None:
        return None

    results: list[Optional[list[float]]] = [None] * len(texts)
    uncached_indices: list[int] = []
    uncached_texts: list[str] = []

    # Gather cache hits
    with _embed_cache_lock:
        for i, text in enumerate(texts):
            cached = _embed_cache.get(text)
            if cached is not None:
                _embed_cache.move_to_end(text)
                results[i] = cached
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)

    # Compute only cache misses
    if uncached_texts:
        try:
            vecs = model.encode(uncached_texts, normalize_embeddings=True, batch_size=32)
            with _embed_cache_lock:
                for idx, text, vec in zip(uncached_indices, uncached_texts, vecs):
                    vec_list = vec.tolist()
                    results[idx] = vec_list
                    _embed_cache[text] = vec_list
                    _embed_cache.move_to_end(text)
                    while len(_embed_cache) > _EMBED_CACHE_MAX:
                        _embed_cache.popitem(last=False)
        except Exception as e:
            logger.error(f"Batch embedding error: {e}")
            return None

    return results


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
