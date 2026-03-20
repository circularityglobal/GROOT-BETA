# REFINET Knowledge Base API Reference

## Endpoints

### Document Management

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/knowledge/upload` | Admin | Upload document (PDF, DOCX, XLSX, CSV, TXT, MD, JSON, SOL) |
| `POST` | `/knowledge/youtube` | Admin | Ingest YouTube transcript by URL |
| `POST` | `/knowledge/url` | Admin | Ingest web page content by URL |
| `GET` | `/knowledge/documents` | Any | List all documents (respects visibility) |
| `GET` | `/knowledge/documents/{id}` | Owner/Admin | Get document metadata and chunk count |
| `DELETE` | `/knowledge/documents/{id}` | Owner/Admin | Delete document and all chunks/embeddings |
| `POST` | `/knowledge/documents/{id}/reindex` | Admin | Re-chunk and re-embed a specific document |

### Search

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/knowledge/search` | Any | Hybrid search (semantic + keyword + FTS5) |

**Search request body:**
```json
{
  "query": "How does SIWE authentication work?",
  "top_k": 5,
  "min_score": 0.3,
  "filters": {
    "format": "pdf",
    "visibility": "public"
  }
}
```

**Search response:**
```json
{
  "results": [
    {
      "chunk_id": "abc123",
      "document_id": "doc456",
      "document_title": "REFINET Auth Guide",
      "content": "SIWE (Sign-In with Ethereum) implements EIP-4361...",
      "score": 0.87,
      "score_breakdown": {
        "semantic": 0.82,
        "keyword": 0.15,
        "fts5": 0.90
      },
      "chunk_index": 3,
      "metadata": {
        "format": "pdf",
        "page": 5
      }
    }
  ],
  "total_results": 12,
  "query_time_ms": 45
}
```

### Advanced Operations

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/knowledge/stats` | Admin | Knowledge base statistics (doc count, chunk count, DB size) |
| `POST` | `/knowledge/compare` | Any | Compare two documents for similarity |
| `POST` | `/knowledge/timeline` | Any | Extract timeline/chronology from document |
| `POST` | `/knowledge/tags` | Admin | Auto-tag document based on content |
| `POST` | `/knowledge/reindex-all` | Admin | Full re-embedding of entire knowledge base |

### CAG-Specific

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/knowledge/cag/search` | Any | Search contract ABIs and SDKs |
| `POST` | `/knowledge/cag/sync` | Admin | Sync CAG index with registry ABIs |
| `GET` | `/knowledge/cag/stats` | Admin | CAG index statistics |

## Database Schema (SQLite)

### documents
```sql
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    format TEXT NOT NULL,        -- pdf, docx, xlsx, csv, txt, md, json, sol, youtube, url
    visibility TEXT DEFAULT 'public',  -- public, private
    owner_id TEXT,               -- user who uploaded
    file_size INTEGER,
    status TEXT DEFAULT 'active', -- active, pending, error
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### document_chunks
```sql
CREATE TABLE document_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id),
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER,
    metadata JSON,              -- page number, section, headers
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### chunk_embeddings
```sql
CREATE TABLE chunk_embeddings (
    id TEXT PRIMARY KEY,
    chunk_id TEXT NOT NULL REFERENCES document_chunks(id),
    embedding JSON NOT NULL,    -- 384-dim float array
    model TEXT DEFAULT 'all-MiniLM-L6-v2',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### document_chunks_fts (FTS5 virtual table)
```sql
CREATE VIRTUAL TABLE document_chunks_fts USING fts5(
    content,
    content_rowid='rowid'
);
```

### cag_index
```sql
CREATE TABLE cag_index (
    id TEXT PRIMARY KEY,
    abi_id TEXT NOT NULL REFERENCES contract_abis(id),
    function_signature TEXT,     -- e.g. "transfer(address,uint256)"
    function_description TEXT,   -- generated SDK description
    embedding JSON,              -- 384-dim float array
    is_dangerous BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
