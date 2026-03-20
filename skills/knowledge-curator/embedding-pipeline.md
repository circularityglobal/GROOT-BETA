# REFINET Embedding Pipeline Reference

## Pipeline Flow

```
Document upload
    │
    ▼
Format detection (by extension + magic bytes)
    │
    ▼
Content extraction
  ├── PDF:     pdfplumber / PyMuPDF → text per page
  ├── DOCX:    python-docx → text per paragraph
  ├── XLSX:    openpyxl → text per row-group (headers preserved)
  ├── CSV:     csv module → text per row-group
  ├── TXT/MD:  raw text read
  ├── JSON:    key-path flattening → text per branch
  ├── SOL:     source stored separately, ABI extracted → function-level
  ├── YouTube: youtube-transcript-api → timed text segments
  └── URL:     httpx + BeautifulSoup → main content extraction
    │
    ▼
Chunking (sentence-aware splitting)
  ├── Target: 512 tokens per chunk
  ├── Overlap: 64 tokens between consecutive chunks
  ├── Minimum: 50 chars (skip tiny fragments)
  ├── Maximum: 500 chunks per document (safety limit)
  └── Metadata: page number, section heading, chunk_index preserved
    │
    ▼
Embedding (sentence-transformers)
  ├── Model: all-MiniLM-L6-v2
  ├── Dimensions: 384
  ├── Batch size: 32 chunks at a time
  └── Storage: JSON array in chunk_embeddings table
    │
    ▼
Indexing
  ├── Vector: INSERT INTO chunk_embeddings
  ├── FTS5: INSERT INTO document_chunks_fts
  └── Metadata: UPDATE documents SET status = 'active'
    │
    ▼
Verification
  └── verify_ingestion() confirms all stages completed
```

## Hybrid Search Algorithm

REFINET uses a 3-signal fusion for knowledge search:

```python
def hybrid_search(query: str, top_k: int = 5) -> list[dict]:
    # 1. Semantic search — cosine similarity against embeddings
    query_embedding = embed(query)  # 384-dim
    semantic_results = cosine_search(query_embedding, top_k=top_k * 3)

    # 2. Keyword scoring — BM25-style term matching
    query_terms = tokenize(query)
    keyword_results = bm25_search(query_terms, top_k=top_k * 3)

    # 3. Full-text search — SQLite FTS5 rank
    fts_results = fts5_search(query, top_k=top_k * 3)

    # Fusion: weighted combination
    WEIGHTS = {
        "semantic": 0.6,
        "keyword": 0.15,
        "fts5": 0.25
    }

    # Reciprocal rank fusion across all three signals
    fused = reciprocal_rank_fusion(
        semantic_results, keyword_results, fts_results,
        weights=WEIGHTS
    )

    return fused[:top_k]
```

## Re-Embedding Strategy

When a full re-embed is triggered (embedding drift detected or model upgrade):

1. **Do NOT delete existing embeddings first** — keep them serving search
2. Create new embeddings in a staging column or table
3. Verify new embeddings pass the benchmark queries
4. Swap: rename staging → production in a single transaction
5. Delete old embeddings
6. Rebuild FTS5 index

This ensures zero-downtime during re-embedding on a single-server setup.

## Capacity Planning (Oracle Cloud ARM A1)

| Metric | Limit | Current Estimate |
|---|---|---|
| public.db max size | ~50GB (200GB disk) | Depends on doc volume |
| Chunks per 1MB PDF | ~40-80 chunks | ~30KB per chunk with embedding |
| Embedding time per chunk | ~10ms (CPU) | Batch of 32 = ~320ms |
| Full re-embed 10K chunks | ~5 minutes | Non-blocking via staging |
| FTS5 index rebuild | ~2 minutes for 10K | Blocking — schedule during low traffic |
| Max concurrent searches | ~20 (SQLite WAL) | WAL allows concurrent reads |

## Sentence-Transformer Setup

The embedding model runs locally on the ARM server. No external API calls.

```bash
pip install sentence-transformers
```

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')

def embed(text: str) -> list[float]:
    return model.encode(text, normalize_embeddings=True).tolist()

def embed_batch(texts: list[str]) -> list[list[float]]:
    return model.encode(texts, normalize_embeddings=True, batch_size=32).tolist()
```

Model size: ~80MB. Loads once at startup. Inference on ARM A1 is fast enough for real-time search.
