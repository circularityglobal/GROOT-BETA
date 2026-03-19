#!/usr/bin/env python3
"""
REFINET Cloud — Document Ingestion Script
Ingests documents into the knowledge base with auto-tagging.
Supports PDF, DOCX, XLSX, CSV, TXT, MD, JSON, SOL files.
Idempotent via content hash deduplication.

Usage:
  python3 scripts/ingest_docs.py --local
  python3 scripts/ingest_docs.py --local --directory docs/
  python3 scripts/ingest_docs.py --local --directory /path/to/files --recursive
  python3 scripts/ingest_docs.py --api-url https://api.refinet.io --token <admin_jwt>
"""

SCRIPT_META = {
    "name": "ingest_docs",
    "description": "Ingest documents into knowledge base with auto-tagging and dedup",
    "category": "seed",
    "requires_admin": True,
}

import argparse
import json
import os
import sys

# Documents to ingest — relative to project root (legacy, backward-compatible)
DOC_FILES = [
    {
        "path": "GROOT.md",
        "title": "GROOT Architecture Overview",
        "category": "docs",
    },
    {
        "path": "docs/GROOT_INTELLIGENCE_WHITEPAPER.md",
        "title": "GROOT Intelligence Whitepaper",
        "category": "docs",
    },
    {
        "path": "docs/REFINET_CLOUD_TECHNICAL_SPECIFICATION.md",
        "title": "REFINET Cloud Technical Specification",
        "category": "docs",
    },
    {
        "path": "README.md",
        "title": "REFINET Cloud README",
        "category": "about",
    },
]


def find_project_root():
    """Find the project root directory (two levels up from scripts/seed/)."""
    d = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(d))


def load_doc_files():
    """Load document files from the legacy DOC_FILES list."""
    root = find_project_root()
    docs = []
    for entry in DOC_FILES:
        filepath = os.path.join(root, entry["path"])
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                content = f.read()
            if content.strip():
                docs.append({
                    "title": entry["title"],
                    "category": entry["category"],
                    "content": content,
                    "filename": entry["path"],
                })
                print(f"  Loaded: {entry['path']} ({len(content)} chars)")
            else:
                print(f"  Skipped (empty): {entry['path']}")
        else:
            print(f"  Not found: {entry['path']}")
    return docs


def discover_files(directory: str, recursive: bool = True) -> list[dict]:
    """
    Discover supported document files in a directory.
    Returns list of dicts with path and filename.
    """
    sys.path.insert(0, find_project_root())
    from api.services.document_parser import SUPPORTED_EXTENSIONS

    results = []
    if recursive:
        for root, dirs, files in os.walk(directory):
            # Skip hidden dirs and common non-doc dirs
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', '__pycache__', '.git', 'venv')]
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    results.append({
                        "path": os.path.join(root, f),
                        "filename": f,
                    })
    else:
        for f in os.listdir(directory):
            filepath = os.path.join(directory, f)
            if os.path.isfile(filepath):
                ext = os.path.splitext(f)[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    results.append({
                        "path": filepath,
                        "filename": f,
                    })

    return sorted(results, key=lambda x: x["filename"])


def ingest_local(docs):
    """Ingest pre-loaded text documents via direct DB access (legacy path)."""
    sys.path.insert(0, find_project_root())

    from api.database import get_public_db
    from api.services.rag import ingest_document
    import api.models  # noqa

    with get_public_db() as db:
        for doc in docs:
            print(f"  Ingesting: {doc['title']}...")
            result = ingest_document(
                db,
                title=doc["title"],
                content=doc["content"],
                category=doc["category"],
                uploaded_by="ingest_script",
                source_filename=doc.get("filename"),
            )
            print(f"    -> Chunks: {result.chunk_count}")

    print(f"\n  Done. {len(docs)} documents ingested.")


def ingest_files_local(file_entries: list[dict]):
    """Ingest files from disk with auto-parsing and auto-tagging."""
    sys.path.insert(0, find_project_root())

    from api.database import get_public_db
    from api.services.rag import ingest_document
    from api.services.document_parser import parse_file
    from api.services.auto_tagger import generate_tags, infer_category
    import api.models  # noqa

    success = 0
    errors = 0

    with get_public_db() as db:
        for entry in file_entries:
            filepath = entry["path"]
            filename = entry["filename"]
            print(f"  Parsing: {filename}...")

            try:
                with open(filepath, "rb") as f:
                    file_bytes = f.read()

                result = parse_file(file_bytes, filename)

                if not result.text.strip():
                    print(f"    -> Skipped (no text extracted)")
                    if result.error:
                        print(f"       Error: {result.error}")
                    errors += 1
                    continue

                # Auto-tag
                tags = generate_tags(result.text, doc_type=result.doc_type, filename=filename)
                category = infer_category(result.text, tags)
                title = os.path.splitext(filename)[0].replace("-", " ").replace("_", " ").title()

                # Ingest
                doc = ingest_document(
                    db,
                    title=title,
                    content=result.text,
                    category=category,
                    uploaded_by="ingest_script",
                    source_filename=filename,
                    tags=tags,
                    doc_type=result.doc_type,
                    page_count=result.page_count,
                    metadata_json=json.dumps(result.metadata) if result.metadata else None,
                )

                tag_preview = ", ".join(tags[:5])
                print(f"    -> Category: {category} | Chunks: {doc.chunk_count} | Tags: [{tag_preview}]")
                if result.page_count:
                    print(f"       Pages: {result.page_count}")
                if result.error:
                    print(f"       Warning: {result.error}")
                success += 1

            except Exception as e:
                print(f"    -> ERROR: {e}")
                errors += 1

    print(f"\n  Done. {success} ingested, {errors} errors.")


def ingest_api(docs, api_url, token):
    """Ingest via HTTP API (legacy text-only path)."""
    import urllib.request

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    for doc in docs:
        print(f"  Uploading: {doc['title']}...")
        payload = json.dumps({
            "title": doc["title"],
            "content": doc["content"],
            "category": doc["category"],
            "filename": doc.get("filename"),
        }).encode()

        req = urllib.request.Request(
            f"{api_url}/knowledge/documents",
            data=payload,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
                print(f"    -> {result.get('message', 'OK')} (chunks: {result.get('chunk_count', '?')})")
        except Exception as e:
            print(f"    -> ERROR: {e}")


def main():
    parser = argparse.ArgumentParser(description="Ingest documents into knowledge base")
    parser.add_argument("--api-url", help="API base URL")
    parser.add_argument("--token", help="Admin JWT token")
    parser.add_argument("--local", action="store_true", help="Direct DB access")
    parser.add_argument("--directory", help="Directory to scan for supported files")
    parser.add_argument("--no-recursive", action="store_true", help="Don't recurse into subdirectories")
    args = parser.parse_args()

    print("REFINET Cloud — Document Ingestion")
    print()

    if args.directory:
        # New path: discover and ingest files from directory
        directory = os.path.abspath(args.directory)
        if not os.path.isdir(directory):
            print(f"  Error: {directory} is not a directory")
            sys.exit(1)

        print(f"  Scanning: {directory}")
        file_entries = discover_files(directory, recursive=not args.no_recursive)
        print(f"  Found {len(file_entries)} supported files")
        print()

        if not file_entries:
            print("  No supported files found.")
            sys.exit(0)

        if args.local:
            ingest_files_local(file_entries)
        else:
            print("  Directory ingestion requires --local flag for now.")
            sys.exit(1)

    else:
        # Legacy path: ingest from DOC_FILES list
        docs = load_doc_files()
        if not docs:
            print("No documents found to ingest.")
            sys.exit(1)

        print()

        if args.local:
            ingest_local(docs)
        elif args.api_url and args.token:
            ingest_api(docs, args.api_url, args.token)
        else:
            print("Usage:")
            print("  python3 scripts/ingest_docs.py --local")
            print("  python3 scripts/ingest_docs.py --local --directory docs/")
            print("  python3 scripts/ingest_docs.py --local --directory /path/to/pdfs --recursive")
            print("  python3 scripts/ingest_docs.py --api-url https://api.refinet.io --token <jwt>")
            sys.exit(1)


if __name__ == "__main__":
    main()
