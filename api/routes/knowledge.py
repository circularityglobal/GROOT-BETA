"""
REFINET Cloud — Knowledge Base Routes
Admin uploads documents → chunked → searchable by Groot via RAG.
Supports file upload (PDF, DOCX, XLSX, CSV, TXT, MD, JSON, SOL),
auto-tagging, document comparison, and CAG contract definitions.
"""

import json
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from sqlalchemy.orm import Session

from api.database import public_db_dependency, internal_db_dependency
from api.auth.jwt import decode_access_token, verify_scope, SCOPE_ADMIN_WRITE, SCOPE_ADMIN_READ
from api.auth.roles import is_admin
from api.models.knowledge import KnowledgeDocument, KnowledgeChunk, ContractDefinition
from api.services.rag import ingest_document, search_knowledge, search_contracts

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def _require_admin(request: Request, int_db: Session) -> str:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        payload = decode_access_token(auth[7:])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    if not is_admin(int_db, payload["sub"]):
        raise HTTPException(status_code=403, detail="Admin required")
    return payload["sub"]


def _require_auth(request: Request) -> str:
    """Require any authenticated user (not necessarily admin). Returns user_id."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        payload = decode_access_token(auth[7:])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload["sub"]


def _check_user_quota(user_id: str, file_size: int, db: Session, int_db: Session):
    """Check storage quotas before allowing a user upload. Raises HTTPException if exceeded."""
    from api.services.config_defaults import get_config_int, get_config_bool

    # Check if user uploads are allowed globally
    if not get_config_bool(int_db, "platform.allow_user_uploads", True):
        raise HTTPException(status_code=403, detail="User uploads are currently disabled by admin")

    # Check document count limit
    max_docs = get_config_int(int_db, "knowledge.max_documents_per_user", 10)
    if max_docs > 0:
        count = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.user_id == user_id,
            KnowledgeDocument.is_active == True,  # noqa
        ).count()
        if count >= max_docs:
            raise HTTPException(
                status_code=429,
                detail=f"Document limit reached ({max_docs}). Contact admin to increase your quota.",
            )

    # Check file size limit
    max_size_mb = get_config_int(int_db, "knowledge.max_file_size_mb", 50)
    if max_size_mb > 0 and file_size > max_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum {max_size_mb}MB. Contact admin to increase limit.",
        )


async def _emit_knowledge_event(event: str, data: dict):
    """Publish a knowledge event to the EventBus for reactive processing."""
    try:
        from api.services.event_bus import bus
        await bus.publish(event, data)
    except Exception:
        pass  # Event emission should never block the main operation


def _parse_tags(tags_json: Optional[str]) -> list:
    """Safely parse tags JSON string."""
    if not tags_json:
        return []
    try:
        return json.loads(tags_json)
    except (json.JSONDecodeError, TypeError):
        return []


# ── Documents (JSON body) ────────────────────────────────────────────

@router.post("/documents")
def upload_document(
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """Upload a document to the knowledge base (JSON body). Admin only."""
    admin_id = _require_admin(request, int_db)
    doc = ingest_document(
        db,
        title=body["title"],
        content=body["content"],
        category=body.get("category", "docs"),
        uploaded_by=admin_id,
        source_filename=body.get("filename"),
    )
    return {
        "id": doc.id,
        "title": doc.title,
        "category": doc.category,
        "chunk_count": doc.chunk_count,
        "message": "Document ingested and chunked for RAG.",
    }


# ── File Upload (multipart) ──────────────────────────────────────────

@router.post("/documents/upload")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """
    Upload a file (PDF, DOCX, XLSX, CSV, TXT, MD, JSON, SOL) to the knowledge base.
    Auto-extracts text, generates semantic tags, infers category. Admin only.
    """
    admin_id = _require_admin(request, int_db)

    # Read file bytes
    file_bytes = await file.read()
    filename = file.filename or "unknown"

    # Size limit: 50MB
    if len(file_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large. Maximum 50MB.")

    # Parse document
    from api.services.document_parser import parse_file, SUPPORTED_EXTENSIONS
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type: {ext}. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    result = parse_file(file_bytes, filename)

    if not result.text.strip():
        detail = "Could not extract text from file."
        if result.error:
            detail += f" {result.error}"
        raise HTTPException(status_code=422, detail=detail)

    # Auto-tag
    from api.services.auto_tagger import generate_tags, infer_category
    tags = generate_tags(result.text, doc_type=result.doc_type, filename=filename)

    # Infer category if not provided
    final_category = category or infer_category(result.text, tags)
    final_title = title or os.path.splitext(filename)[0].replace("-", " ").replace("_", " ").title()

    # Ingest via existing pipeline
    doc = ingest_document(
        db,
        title=final_title,
        content=result.text,
        category=final_category,
        uploaded_by=admin_id,
        source_filename=filename,
        tags=tags,
        doc_type=result.doc_type,
        page_count=result.page_count,
        metadata_json=json.dumps(result.metadata) if result.metadata else None,
    )

    response = {
        "id": doc.id,
        "title": doc.title,
        "category": doc.category,
        "doc_type": doc.doc_type,
        "tags": _parse_tags(doc.tags),
        "chunk_count": doc.chunk_count,
        "page_count": doc.page_count,
        "message": "Document ingested and chunked for RAG.",
    }
    if result.error:
        response["warning"] = result.error

    return response


# ── Document List ─────────────────────────────────────────────────────

@router.get("/documents")
def list_documents(
    request: Request,
    db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    _require_admin(request, int_db)
    docs = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.is_active == True,  # noqa
    ).order_by(KnowledgeDocument.created_at.desc()).all()
    return [
        {
            "id": d.id,
            "title": d.title,
            "category": d.category,
            "doc_type": d.doc_type,
            "tags": _parse_tags(d.tags),
            "chunk_count": d.chunk_count,
            "page_count": d.page_count,
            "source_filename": d.source_filename,
            "created_at": str(d.created_at),
        }
        for d in docs
    ]


@router.delete("/documents/{doc_id}")
def delete_document(
    doc_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    _require_admin(request, int_db)
    doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.is_active = False
    db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc_id).delete()
    return {"message": "Document removed from knowledge base."}


# ── Document Tags ─────────────────────────────────────────────────────

@router.get("/documents/{doc_id}/tags")
def get_document_tags(
    doc_id: str,
    db: Session = Depends(public_db_dependency),
):
    """Get auto-generated semantic tags for a document."""
    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == doc_id,
        KnowledgeDocument.is_active == True,  # noqa
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "id": doc.id,
        "title": doc.title,
        "category": doc.category,
        "doc_type": doc.doc_type,
        "tags": _parse_tags(doc.tags),
    }


@router.post("/documents/{doc_id}/retag")
def retag_document(
    doc_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """Re-generate tags for an existing document. Admin only."""
    _require_admin(request, int_db)

    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == doc_id,
        KnowledgeDocument.is_active == True,  # noqa
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    from api.services.auto_tagger import generate_tags, infer_category
    tags = generate_tags(doc.content, doc_type=doc.doc_type or "txt", filename=doc.source_filename)
    doc.tags = json.dumps(tags)

    # Also update category if it was the default
    if doc.category == "docs":
        doc.category = infer_category(doc.content, tags)

    return {
        "id": doc.id,
        "title": doc.title,
        "category": doc.category,
        "tags": tags,
        "message": "Tags regenerated.",
    }


# ── Document Comparison ───────────────────────────────────────────────

@router.post("/documents/compare")
def compare_docs(
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """Compare two documents by semantic similarity, keyword overlap, and structure. Admin only."""
    _require_admin(request, int_db)

    doc_id_a = body.get("doc_id_a")
    doc_id_b = body.get("doc_id_b")
    if not doc_id_a or not doc_id_b:
        raise HTTPException(status_code=400, detail="Both doc_id_a and doc_id_b required")

    from api.services.document_compare import compare_documents
    result = compare_documents(db, doc_id_a, doc_id_b)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


# ── Document Generation (BitNet-powered) ─────────────────────────────

@router.post("/documents/{doc_id}/summarize")
async def summarize_document(
    doc_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """Generate a summary of a document using BitNet. Admin only."""
    _require_admin(request, int_db)
    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == doc_id,
        KnowledgeDocument.is_active == True,  # noqa
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    from api.services.document_generator import generate_summary
    result = await generate_summary(doc.content, title=doc.title)
    return result


@router.post("/documents/{doc_id}/generate-faq")
async def generate_faq_endpoint(
    doc_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """Generate FAQ from a document using BitNet. Admin only."""
    _require_admin(request, int_db)
    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == doc_id,
        KnowledgeDocument.is_active == True,  # noqa
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    from api.services.document_generator import generate_faq
    result = await generate_faq(doc.content, title=doc.title)
    return result


@router.post("/documents/{doc_id}/generate-overview")
async def generate_overview_endpoint(
    doc_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """Generate a structured overview of a document using BitNet. Admin only."""
    _require_admin(request, int_db)
    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == doc_id,
        KnowledgeDocument.is_active == True,  # noqa
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    from api.services.document_generator import generate_overview
    result = await generate_overview(doc.content, title=doc.title)
    return result


# ── Search (public — used by Groot and by users) ──────────────────

@router.get("/search")
def search(
    q: str,
    category: str = None,
    tags: str = None,
    db: Session = Depends(public_db_dependency),
):
    """
    Search the knowledge base. Available to authenticated users.
    Optional tags parameter: comma-separated tag list for filtering.
    """
    tag_list = None
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    results = search_knowledge(db, q, max_results=5, category=category, tags=tag_list)
    return {"query": q, "results": results}


# ── Contracts (CAG) ────────────────────────────────────────────────

@router.post("/contracts")
def add_contract(
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """Add a contract definition for CAG. Admin only."""
    _require_admin(request, int_db)
    contract = ContractDefinition(
        id=str(uuid.uuid4()),
        name=body["name"],
        chain=body.get("chain", "ethereum"),
        address=body.get("address"),
        abi_json=json.dumps(body.get("abi")) if body.get("abi") else None,
        description=body["description"],
        logic_summary=body.get("logic_summary"),
        category=body.get("category", "defi"),
    )
    db.add(contract)
    return {"id": contract.id, "name": contract.name, "message": "Contract added for CAG."}


@router.get("/contracts")
def list_contracts(
    db: Session = Depends(public_db_dependency),
    chain: str = None,
):
    q = db.query(ContractDefinition).filter(ContractDefinition.is_active == True)  # noqa
    if chain:
        q = q.filter(ContractDefinition.chain == chain)
    return [
        {
            "id": c.id,
            "name": c.name,
            "chain": c.chain,
            "address": c.address,
            "category": c.category,
            "description": c.description[:200],
        }
        for c in q.all()
    ]


# ═══════════════════════════════════════════════════════════════════════
# User-Facing Document Endpoints (no admin required)
# Private/public document layer for NotebookLM-like experience
# ═══════════════════════════════════════════════════════════════════════

@router.post("/my/documents/upload")
async def user_upload_file(
    request: Request,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    visibility: Optional[str] = Form("private"),
    db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """Upload a file to the user's private knowledge base. Any authenticated user."""
    user_id = _require_auth(request)

    file_bytes = await file.read()
    filename = file.filename or "unknown"

    # Enforce admin-configured quotas
    _check_user_quota(user_id, len(file_bytes), db, int_db)

    from api.services.document_parser import parse_file, SUPPORTED_EXTENSIONS
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=422, detail=f"Unsupported file type: {ext}")

    result = parse_file(file_bytes, filename)
    if not result.text.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from file.")

    from api.services.auto_tagger import generate_tags, infer_category
    tags = generate_tags(result.text, doc_type=result.doc_type, filename=filename)
    final_category = category or infer_category(result.text, tags)
    final_title = title or os.path.splitext(filename)[0].replace("-", " ").replace("_", " ").title()

    # Validate visibility
    vis = visibility if visibility in ("private", "public") else "private"

    doc = ingest_document(
        db,
        title=final_title,
        content=result.text,
        category=final_category,
        uploaded_by=user_id,
        source_filename=filename,
        tags=tags,
        doc_type=result.doc_type,
        page_count=result.page_count,
        metadata_json=json.dumps(result.metadata) if result.metadata else None,
    )
    # Set user ownership and visibility
    doc.user_id = user_id
    doc.visibility = vis

    # Emit event for reactive system
    await _emit_knowledge_event("knowledge.document.uploaded", {
        "document_id": doc.id, "title": doc.title, "user_id": user_id,
        "category": doc.category, "doc_type": doc.doc_type,
        "tags": _parse_tags(doc.tags), "visibility": vis,
        "chunk_count": doc.chunk_count,
    })

    return {
        "id": doc.id, "title": doc.title, "category": doc.category,
        "doc_type": doc.doc_type, "tags": _parse_tags(doc.tags),
        "chunk_count": doc.chunk_count, "page_count": doc.page_count,
        "visibility": doc.visibility,
        "message": "Document uploaded to your knowledge base.",
    }


@router.get("/my/documents")
def list_my_documents(
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """List the current user's own documents."""
    user_id = _require_auth(request)
    docs = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.user_id == user_id,
        KnowledgeDocument.is_active == True,  # noqa
    ).order_by(KnowledgeDocument.created_at.desc()).all()
    return [
        {
            "id": d.id, "title": d.title, "category": d.category,
            "doc_type": d.doc_type, "tags": _parse_tags(d.tags),
            "chunk_count": d.chunk_count, "page_count": d.page_count,
            "visibility": d.visibility or "private",
            "source_filename": d.source_filename,
            "created_at": str(d.created_at),
        }
        for d in docs
    ]


@router.delete("/my/documents/{doc_id}")
async def delete_my_document(
    doc_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Delete a document owned by the current user."""
    user_id = _require_auth(request)
    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == doc_id,
        KnowledgeDocument.user_id == user_id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found or not owned by you")
    title = doc.title
    doc.is_active = False
    db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc_id).delete()
    await _emit_knowledge_event("knowledge.document.deleted", {
        "document_id": doc_id, "title": title, "user_id": user_id,
    })
    return {"message": "Document removed."}


@router.put("/my/documents/{doc_id}/visibility")
async def toggle_visibility(
    doc_id: str,
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Toggle document visibility between private and public. Owner only."""
    user_id = _require_auth(request)
    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == doc_id,
        KnowledgeDocument.user_id == user_id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found or not owned by you")

    old_visibility = doc.visibility or "private"
    new_visibility = body.get("visibility", "private")
    if new_visibility not in ("private", "public"):
        raise HTTPException(status_code=400, detail="Visibility must be 'private' or 'public'")
    doc.visibility = new_visibility
    await _emit_knowledge_event("knowledge.document.visibility_changed", {
        "document_id": doc.id, "user_id": user_id,
        "old_visibility": old_visibility, "new_visibility": new_visibility,
    })
    return {"id": doc.id, "visibility": doc.visibility, "message": f"Document is now {new_visibility}."}


@router.post("/my/documents/{doc_id}/retag")
def retag_my_document(
    doc_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Re-generate tags for a document owned by the current user."""
    user_id = _require_auth(request)
    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == doc_id,
        KnowledgeDocument.user_id == user_id,
        KnowledgeDocument.is_active == True,  # noqa
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found or not owned by you")

    from api.services.auto_tagger import generate_tags, infer_category
    tags = generate_tags(doc.content, doc_type=doc.doc_type or "txt", filename=doc.source_filename)
    doc.tags = json.dumps(tags)
    return {"id": doc.id, "tags": tags, "message": "Tags regenerated."}


@router.post("/my/documents/{doc_id}/summarize")
async def summarize_my_document(
    doc_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Generate a summary of a document owned by the current user."""
    user_id = _require_auth(request)
    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == doc_id,
        KnowledgeDocument.user_id == user_id,
        KnowledgeDocument.is_active == True,  # noqa
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found or not owned by you")

    from api.services.document_generator import generate_summary
    return await generate_summary(doc.content, title=doc.title)


@router.post("/my/documents/{doc_id}/generate-faq")
async def generate_my_faq(
    doc_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Generate FAQ from a document owned by the current user."""
    user_id = _require_auth(request)
    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == doc_id,
        KnowledgeDocument.user_id == user_id,
        KnowledgeDocument.is_active == True,  # noqa
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found or not owned by you")

    from api.services.document_generator import generate_faq
    return await generate_faq(doc.content, title=doc.title)


@router.post("/my/documents/{doc_id}/generate-overview")
async def generate_my_overview(
    doc_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Generate overview from a document owned by the current user."""
    user_id = _require_auth(request)
    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == doc_id,
        KnowledgeDocument.user_id == user_id,
        KnowledgeDocument.is_active == True,  # noqa
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found or not owned by you")

    from api.services.document_generator import generate_overview
    return await generate_overview(doc.content, title=doc.title)


@router.get("/my/search")
def search_my_knowledge(
    q: str,
    request: Request,
    tags: str = None,
    db: Session = Depends(public_db_dependency),
):
    """Search the user's own documents + public + platform docs."""
    user_id = _require_auth(request)
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    results = search_knowledge(db, q, max_results=5, tags=tag_list, user_id=user_id)
    return {"query": q, "results": results}


# ═══════════════════════════════════════════════════════════════════════
# URL Ingestion — fetch web pages and ingest as documents
# ═══════════════════════════════════════════════════════════════════════

@router.post("/documents/ingest-url")
async def admin_ingest_url(
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """Fetch a URL, extract text, and ingest as a knowledge document. Admin only."""
    admin_id = _require_admin(request, int_db)
    url = body.get("url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL required")

    from api.services.url_parser import parse_url
    result = await parse_url(url)
    if not result.text.strip():
        raise HTTPException(status_code=422, detail=result.error or "No text extracted from URL")

    from api.services.auto_tagger import generate_tags, infer_category
    tags = generate_tags(result.text, doc_type="url", filename=url)
    category = body.get("category") or infer_category(result.text, tags)
    title = body.get("title") or result.metadata.get("page_title") or url

    doc = ingest_document(
        db, title=title, content=result.text, category=category,
        uploaded_by=admin_id, source_filename=url,
        tags=tags, doc_type="url",
        metadata_json=json.dumps(result.metadata) if result.metadata else None,
    )
    doc.visibility = "platform"
    return {"id": doc.id, "title": doc.title, "category": doc.category,
            "tags": _parse_tags(doc.tags), "chunk_count": doc.chunk_count,
            "message": f"URL ingested: {url}"}


@router.post("/my/documents/ingest-url")
async def user_ingest_url(
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """Fetch a URL and ingest as a user document. Any authenticated user."""
    user_id = _require_auth(request)
    _check_user_quota(user_id, 0, db, int_db)  # Check doc count (size checked after fetch)
    url = body.get("url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL required")

    from api.services.url_parser import parse_url
    result = await parse_url(url)
    if not result.text.strip():
        raise HTTPException(status_code=422, detail=result.error or "No text extracted from URL")

    from api.services.auto_tagger import generate_tags, infer_category
    tags = generate_tags(result.text, doc_type="url", filename=url)
    category = body.get("category") or infer_category(result.text, tags)
    title = body.get("title") or result.metadata.get("page_title") or url
    vis = body.get("visibility", "private")
    if vis not in ("private", "public"):
        vis = "private"

    doc = ingest_document(
        db, title=title, content=result.text, category=category,
        uploaded_by=user_id, source_filename=url,
        tags=tags, doc_type="url",
        metadata_json=json.dumps(result.metadata) if result.metadata else None,
    )
    doc.user_id = user_id
    doc.visibility = vis
    return {"id": doc.id, "title": doc.title, "category": doc.category,
            "tags": _parse_tags(doc.tags), "chunk_count": doc.chunk_count,
            "visibility": vis, "message": f"URL ingested: {url}"}


# ═══════════════════════════════════════════════════════════════════════
# YouTube Transcript Ingestion
# ═══════════════════════════════════════════════════════════════════════

@router.post("/documents/ingest-youtube")
async def admin_ingest_youtube(
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """Ingest a YouTube video transcript. Admin only. Requires yt-dlp."""
    admin_id = _require_admin(request, int_db)
    url = body.get("url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="YouTube URL required")

    from api.services.youtube_parser import parse_youtube, is_youtube_url
    if not is_youtube_url(url):
        raise HTTPException(status_code=400, detail="Not a valid YouTube URL")

    result = await parse_youtube(url)
    if not result.text.strip():
        raise HTTPException(status_code=422, detail=result.error or "No transcript available")

    from api.services.auto_tagger import generate_tags, infer_category
    tags = generate_tags(result.text, doc_type="youtube", filename=url)
    category = body.get("category") or infer_category(result.text, tags)
    title = body.get("title") or result.metadata.get("video_title") or url

    doc = ingest_document(
        db, title=title, content=result.text, category=category,
        uploaded_by=admin_id, source_filename=url,
        tags=tags, doc_type="youtube",
        metadata_json=json.dumps(result.metadata) if result.metadata else None,
    )
    doc.visibility = "platform"
    return {"id": doc.id, "title": doc.title, "tags": _parse_tags(doc.tags),
            "chunk_count": doc.chunk_count, "message": f"YouTube transcript ingested"}


@router.post("/my/documents/ingest-youtube")
async def user_ingest_youtube(
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """Ingest a YouTube video transcript. Any authenticated user. Requires yt-dlp."""
    user_id = _require_auth(request)
    _check_user_quota(user_id, 0, db, int_db)  # Check doc count
    url = body.get("url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="YouTube URL required")

    from api.services.youtube_parser import parse_youtube, is_youtube_url
    if not is_youtube_url(url):
        raise HTTPException(status_code=400, detail="Not a valid YouTube URL")

    result = await parse_youtube(url)
    if not result.text.strip():
        raise HTTPException(status_code=422, detail=result.error or "No transcript available")

    from api.services.auto_tagger import generate_tags, infer_category
    tags = generate_tags(result.text, doc_type="youtube", filename=url)
    category = body.get("category") or infer_category(result.text, tags)
    title = body.get("title") or result.metadata.get("video_title") or url
    vis = body.get("visibility", "private")

    doc = ingest_document(
        db, title=title, content=result.text, category=category,
        uploaded_by=user_id, source_filename=url,
        tags=tags, doc_type="youtube",
        metadata_json=json.dumps(result.metadata) if result.metadata else None,
    )
    doc.user_id = user_id
    doc.visibility = vis if vis in ("private", "public") else "private"
    return {"id": doc.id, "title": doc.title, "tags": _parse_tags(doc.tags),
            "chunk_count": doc.chunk_count, "visibility": doc.visibility,
            "message": "YouTube transcript ingested"}


# ═══════════════════════════════════════════════════════════════════════
# Document Export — Markdown / PDF
# ═══════════════════════════════════════════════════════════════════════

@router.get("/documents/{doc_id}/export")
def admin_export_document(
    doc_id: str,
    format: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """Export a document as Markdown or PDF. Admin only."""
    _require_admin(request, int_db)
    doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id, KnowledgeDocument.is_active == True).first()  # noqa
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _do_export(doc, format)


@router.get("/my/documents/{doc_id}/export")
def user_export_document(
    doc_id: str,
    format: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Export a user's own document as Markdown or PDF."""
    user_id = _require_auth(request)
    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == doc_id, KnowledgeDocument.user_id == user_id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found or not owned by you")
    return _do_export(doc, format)


def _do_export(doc: KnowledgeDocument, format: str):
    """Perform the actual export."""
    from fastapi.responses import Response
    from api.services.document_exporter import export_markdown, export_pdf

    tags = _parse_tags(doc.tags)
    safe_title = doc.title.replace(" ", "_").replace("/", "-")[:50]

    if format == "md":
        content = export_markdown(doc.title, doc.content, tags=tags, category=doc.category, doc_type=doc.doc_type)
        return Response(
            content=content, media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{safe_title}.md"'},
        )
    elif format == "pdf":
        pdf_bytes = export_pdf(doc.title, doc.content, tags=tags, category=doc.category)
        return Response(
            content=pdf_bytes, media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{safe_title}.pdf"'},
        )
    else:
        raise HTTPException(status_code=400, detail="Format must be 'md' or 'pdf'")


# ═══════════════════════════════════════════════════════════════════════
# Timeline Extraction
# ═══════════════════════════════════════════════════════════════════════

@router.post("/documents/{doc_id}/timeline")
def admin_extract_timeline(
    doc_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """Extract a chronological timeline from a document. Admin only."""
    _require_admin(request, int_db)
    doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id, KnowledgeDocument.is_active == True).first()  # noqa
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    from api.services.timeline_extractor import extract_timeline
    events = extract_timeline(doc.content)
    return {"document_id": doc.id, "title": doc.title, "events": events, "count": len(events)}


@router.post("/my/documents/{doc_id}/timeline")
def user_extract_timeline(
    doc_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Extract a chronological timeline from a user's document."""
    user_id = _require_auth(request)
    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == doc_id, KnowledgeDocument.user_id == user_id,
        KnowledgeDocument.is_active == True,  # noqa
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found or not owned by you")

    from api.services.timeline_extractor import extract_timeline
    events = extract_timeline(doc.content)
    return {"document_id": doc.id, "title": doc.title, "events": events, "count": len(events)}


# ═══════════════════════════════════════════════════════════════════════
# Audio Overview (TTS)
# ═══════════════════════════════════════════════════════════════════════

@router.post("/documents/{doc_id}/audio-overview")
async def admin_audio_overview(
    doc_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
    int_db: Session = Depends(internal_db_dependency),
):
    """Generate an audio overview of a document using Piper TTS. Admin only."""
    _require_admin(request, int_db)
    doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id, KnowledgeDocument.is_active == True).first()  # noqa
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return await _do_audio_overview(doc)


@router.post("/my/documents/{doc_id}/audio-overview")
async def user_audio_overview(
    doc_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Generate an audio overview of a user's document using Piper TTS."""
    user_id = _require_auth(request)
    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == doc_id, KnowledgeDocument.user_id == user_id,
        KnowledgeDocument.is_active == True,  # noqa
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found or not owned by you")
    return await _do_audio_overview(doc)


async def _do_audio_overview(doc: KnowledgeDocument):
    from api.services.tts_generator import generate_audio_overview, is_tts_available
    if not is_tts_available():
        # Return just the script without audio
        from api.services.document_generator import generate_summary
        summary = await generate_summary(doc.content, title=doc.title)
        return {"script": summary.get("content", ""), "audio_available": False,
                "message": "Piper TTS not installed. Returning text script only."}

    result = await generate_audio_overview(doc.content, title=doc.title)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    if result.get("audio_bytes"):
        from fastapi.responses import Response
        return Response(
            content=result["audio_bytes"],
            media_type="audio/wav",
            headers={
                "Content-Disposition": f'attachment; filename="overview_{doc.id[:8]}.wav"',
                "X-Script": result.get("script", "")[:500],
                "X-Duration-Estimate": str(result.get("duration_estimate", 0)),
            },
        )

    return {"script": result.get("script", ""), "audio_available": False,
            "message": result.get("error", "Audio generation failed")}


# ═══════════════════════════════════════════════════════════════════════
# Document Sharing / Collaboration
# ═══════════════════════════════════════════════════════════════════════

@router.post("/my/documents/{doc_id}/share")
def share_document(
    doc_id: str,
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Share a document with another user. Owner only."""
    user_id = _require_auth(request)
    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == doc_id, KnowledgeDocument.user_id == user_id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found or not owned by you")

    shared_with = body.get("shared_with_id", "").strip()
    if not shared_with:
        raise HTTPException(status_code=400, detail="shared_with_id required")
    if shared_with == user_id:
        raise HTTPException(status_code=400, detail="Cannot share with yourself")

    permission = body.get("permission", "read")
    if permission not in ("read", "write"):
        permission = "read"

    from api.models.knowledge import DocumentShare
    # Check for existing share
    existing = db.query(DocumentShare).filter(
        DocumentShare.document_id == doc_id,
        DocumentShare.shared_with_id == shared_with,
    ).first()
    if existing:
        existing.permission = permission
        return {"id": existing.id, "message": "Share permission updated"}

    share = DocumentShare(
        document_id=doc_id, owner_id=user_id,
        shared_with_id=shared_with, permission=permission,
    )
    db.add(share)
    return {"id": share.id, "document_id": doc_id, "shared_with_id": shared_with,
            "permission": permission, "message": "Document shared"}


@router.get("/my/documents/{doc_id}/shares")
def list_document_shares(
    doc_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """List shares for a document. Owner only."""
    user_id = _require_auth(request)
    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == doc_id, KnowledgeDocument.user_id == user_id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found or not owned by you")

    from api.models.knowledge import DocumentShare
    shares = db.query(DocumentShare).filter(DocumentShare.document_id == doc_id).all()
    return [{"id": s.id, "shared_with_id": s.shared_with_id, "permission": s.permission,
             "created_at": str(s.created_at)} for s in shares]


@router.delete("/my/documents/{doc_id}/shares/{share_id}")
def revoke_share(
    doc_id: str,
    share_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Revoke a document share. Owner only."""
    user_id = _require_auth(request)
    from api.models.knowledge import DocumentShare
    share = db.query(DocumentShare).filter(
        DocumentShare.id == share_id,
        DocumentShare.document_id == doc_id,
        DocumentShare.owner_id == user_id,
    ).first()
    if not share:
        raise HTTPException(status_code=404, detail="Share not found")
    db.delete(share)
    return {"message": "Share revoked"}


@router.get("/shared-with-me")
def list_shared_documents(
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """List documents shared with the current user."""
    user_id = _require_auth(request)
    from api.models.knowledge import DocumentShare
    shares = db.query(DocumentShare).filter(DocumentShare.shared_with_id == user_id).all()
    doc_ids = [s.document_id for s in shares]
    if not doc_ids:
        return []

    docs = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id.in_(doc_ids),
        KnowledgeDocument.is_active == True,  # noqa
    ).all()

    share_map = {s.document_id: s.permission for s in shares}
    return [
        {"id": d.id, "title": d.title, "category": d.category,
         "doc_type": d.doc_type, "tags": _parse_tags(d.tags),
         "chunk_count": d.chunk_count, "permission": share_map.get(d.id, "read"),
         "created_at": str(d.created_at)}
        for d in docs
    ]
