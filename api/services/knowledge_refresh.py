"""
REFINET Cloud — Knowledge Refresh Handler
Reactive system that responds to knowledge base changes.
When documents are uploaded, deleted, retagged, or visibility changes,
this handler notifies GROOT and triggers background updates.
"""

import logging

logger = logging.getLogger("refinet.knowledge_refresh")


async def on_knowledge_change(event: str, data: dict):
    """
    EventBus handler for knowledge.* events.
    Triggers GROOT awareness refresh when the knowledge base changes.

    Events handled:
    - knowledge.document.uploaded — new document available
    - knowledge.document.deleted — document removed from knowledge
    - knowledge.document.retagged — tags/category changed
    - knowledge.document.visibility_changed — public/private toggle
    - knowledge.document.shared — doc shared with another user
    - knowledge.document.url_ingested — web page ingested
    - knowledge.document.youtube_ingested — YouTube transcript ingested
    - knowledge.contract.added — new CAG contract definition
    """
    doc_id = data.get("document_id", data.get("contract_id", "unknown"))
    title = data.get("title", data.get("name", ""))

    logger.info(f"Knowledge change: {event} — {title} ({doc_id})")

    # When a document becomes public, backfill embeddings for any chunks missing them
    if event == "knowledge.document.visibility_changed":
        new_vis = data.get("new_visibility")
        if new_vis == "public":
            logger.info(f"Document {doc_id} now public — triggering embedding backfill")
            try:
                from api.database import get_public_session
                from api.services.rag import backfill_embeddings
                with get_public_session() as db:
                    updated = backfill_embeddings(db, batch_size=50)
                    if updated > 0:
                        db.commit()
                        logger.info(f"Backfilled {updated} embeddings after visibility change")
            except Exception as e:
                logger.warning(f"Embedding backfill failed: {e}")

    # When a new document is uploaded with content, ensure embeddings are generated
    if event in ("knowledge.document.uploaded", "knowledge.document.url_ingested", "knowledge.document.youtube_ingested"):
        chunk_count = data.get("chunk_count", 0)
        visibility = data.get("visibility", "private")
        logger.info(
            f"New document: {title} — {chunk_count} chunks, visibility={visibility}"
        )

    # When a document is deleted, log for audit trail
    if event == "knowledge.document.deleted":
        user_id = data.get("user_id", "unknown")
        logger.info(f"Document deleted by {user_id}: {title} ({doc_id})")
