#!/usr/bin/env python3
"""Comprehensive system health report."""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "health_report",
    "description": "Generate a comprehensive system health report",
    "category": "ops",
    "requires_admin": False,
}


def main():
    import platform
    import resource

    print("=== REFINET Cloud Health Report ===")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print(f"Platform: {platform.system()} {platform.machine()}")
    print(f"Python: {platform.python_version()}")

    # Memory usage
    usage = resource.getrusage(resource.RUSAGE_SELF)
    print(f"Memory (max RSS): {usage.ru_maxrss / 1024:.1f} MB")

    # Database connectivity
    print("\n--- Database ---")
    try:
        from api.database import get_public_engine, get_internal_engine
        from sqlalchemy import text

        with get_public_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
            print("Public DB: OK")

        with get_internal_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
            print("Internal DB: OK")
    except Exception as e:
        print(f"Database: ERROR ({e})")

    # BitNet connectivity
    print("\n--- Inference ---")
    try:
        import urllib.request
        start = time.time()
        req = urllib.request.Request("http://127.0.0.1:8080/health", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            latency = int((time.time() - start) * 1000)
            print(f"BitNet sidecar: OK ({latency}ms)")
    except Exception as e:
        print(f"BitNet sidecar: UNAVAILABLE ({e})")

    # Knowledge base stats
    print("\n--- Knowledge Base ---")
    try:
        from api.database import create_public_session
        from api.models.knowledge import KnowledgeDocument, KnowledgeChunk
        db = create_public_session()
        doc_count = db.query(KnowledgeDocument).count()
        chunk_count = db.query(KnowledgeChunk).count()
        print(f"Documents: {doc_count}")
        print(f"Chunks: {chunk_count}")
        db.close()
    except Exception as e:
        print(f"Knowledge base: ERROR ({e})")

    print("\n=== Report Complete ===")


if __name__ == "__main__":
    main()
