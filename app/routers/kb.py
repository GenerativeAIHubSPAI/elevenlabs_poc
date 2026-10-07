"""Knowledge-base API routes.

This module exposes endpoints for ingesting text and PDF documents into the
knowledge base and for searching stored chunks by namespace. It validates uploads,
extracts PDF text, delegates chunk creation and embedding to the knowledge-base
service, and returns ingestion/search results for downstream chat and voice flows.
"""

from typing import Any
import asyncio
import logging

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)

from app.core.knowledge_sources import list_knowledge_source_options
from app.schemas.requests import KBIngestTextRequest, KBSearchRequest
from app.services.kb import (
    EmbeddingConfigurationError,
    EmbeddingProviderError,
    KnowledgeBaseError,
    kb_ingest_pages,
    kb_ingest_text,
    kb_search,
    kb_store,
)
from app.services.pdf_parser import extract_pdf_pages
from app.services.static_kb_jobs import (
    get_static_kb_job,
    get_static_kb_status,
    list_static_kb_jobs,
    queue_static_kb_load,
)
from app.services.static_kb_loader import (
    StaticKBLoaderError,
    list_static_namespaces,
)

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/ingest-text")
async def ingest_text(body: KBIngestTextRequest):
    """Ingest plain text into the knowledge base."""
    saved = await asyncio.to_thread(
        kb_ingest_text,
        title=body.title,
        text=body.text,
        namespace=body.namespace,
        source_type="text",
        source_name=body.title,
    )

    return {
        "namespace": body.namespace,
        "ingested_chunks": len(saved),
        "sample": saved[:3],
    }


@router.post("/ingest-pdf")
async def ingest_pdf(
    file: UploadFile = File(...),
    namespace: str = Form(default="default"),
    title: str | None = Form(default=None),
):
    """Ingest a PDF into the knowledge base."""
    if file.content_type not in {
        "application/pdf",
        "application/octet-stream",
    }:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "unsupported_file_type",
                "message": f"Unsupported file type: {file.content_type}",
            },
        )

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "empty_pdf",
                "message": "Uploaded PDF is empty.",
            },
        )

    max_size_mb = 20

    if len(content) > max_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail={
                "code": "pdf_too_large",
                "message": f"PDF too large. Maximum allowed size is {max_size_mb} MB.",
            },
        )

    doc_title = title or file.filename or "uploaded_pdf"

    # Parsing and embedding are blocking; running them inline on the event loop
    # froze the single uvicorn worker -- voice streams and every other request
    # included -- for as long as the upload took.
    try:
        pages = await asyncio.to_thread(extract_pdf_pages, content)

        if not pages:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "no_extractable_text",
                    "message": (
                        "No extractable text was found in the PDF. "
                        "The document may be scanned or image-based."
                    ),
                },
            )

        all_saved = await asyncio.to_thread(
            kb_ingest_pages,
            title=doc_title,
            pages=pages,
            namespace=namespace,
            source_type="pdf",
            source_name=file.filename,
        )

        return {
            "namespace": namespace,
            "title": doc_title,
            "source_name": file.filename,
            "pages_processed": len(pages),
            "ingested_chunks": len(all_saved),
            "sample": all_saved[:3],
        }

    except HTTPException:
        raise

    except EmbeddingConfigurationError as exc:
        logger.exception("Embedding configuration error during PDF ingestion.")

        raise HTTPException(
            status_code=500,
            detail={
                "code": "embedding_configuration_error",
                "message": str(exc),
            },
        ) from exc

    except EmbeddingProviderError as exc:
        logger.exception("Embedding provider error during PDF ingestion.")

        raise HTTPException(
            status_code=502,
            detail={
                "code": "embedding_provider_error",
                "provider": "bedrock",
                "message": str(exc),
            },
        ) from exc

    except KnowledgeBaseError as exc:
        logger.exception("Knowledge-base error during PDF ingestion.")

        raise HTTPException(
            status_code=500,
            detail={
                "code": "knowledge_base_error",
                "message": str(exc),
            },
        ) from exc

    except Exception as exc:
        logger.exception("Unexpected PDF ingestion error.")

        raise HTTPException(
            status_code=500,
            detail={
                "code": "pdf_ingestion_error",
                "message": "Unexpected error while ingesting the PDF.",
                "error": str(exc),
            },
        ) from exc


@router.post("/search")
async def search_kb(body: KBSearchRequest):
    """Search the knowledge base."""
    return {
        "namespace": body.namespace,
        "results": await asyncio.to_thread(
            kb_search,
            query=body.query,
            namespace=body.namespace,
            top_k=body.top_k,
        ),
    }


@router.post(
    "/load-static",
    status_code=status.HTTP_202_ACCEPTED,
)
def load_static_examples():
    """Queue static KB loading for all discovered namespaces."""
    try:
        namespaces = [
            source["value"]
            for source in list_static_namespaces()
        ]

    except StaticKBLoaderError as exc:
        logger.exception("Static KB source listing failed.")

        raise HTTPException(
            status_code=500,
            detail={
                "code": "static_kb_source_listing_error",
                "message": str(exc),
            },
        ) from exc

    queued = [
        job
        for job in (queue_static_kb_load(namespace) for namespace in namespaces)
        if job is not None
    ]

    return {
        "status": "queued",
        "jobs": queued,
    }


@router.post(
    "/load-static/{namespace}",
    status_code=status.HTTP_202_ACCEPTED,
)
def load_static_example(namespace: str):
    """Queue static KB loading for one namespace."""
    return queue_static_kb_load(namespace)


@router.get("/static-status")
def list_static_load_statuses():
    """List static KB loading statuses."""
    return {
        "jobs": list_static_kb_jobs(),
    }


@router.get("/static-status/{namespace}")
def get_static_load_status(namespace: str):
    """Get static KB loading status for one namespace."""
    job = get_static_kb_job(namespace)

    if job is None:
        return {
            "namespace": namespace,
            "status": "not_started",
        }

    return job


@router.get("/static-sources")
def list_static_sources():
    """List the selectable static business topics.

    Driven by the in-code registry, so the option list is byte-identical in every
    environment and always contains only namespaces that the chat/voice flows
    accept. The S3 listing is reported as diagnostics only: an unreachable or
    differently-shaped bucket must not empty the selector nor fail the request,
    which previously left the frontend with no options and no visible error.
    """
    sources = []

    for option in list_knowledge_source_options():
        chunks = len(kb_store.get(option["value"], []))
        readiness = get_static_kb_status(option["value"])

        sources.append(
            {
                **option,
                "chunks": chunks,
                "loaded": readiness["status"] == "ready",
                # "ready" | "loading" | "unavailable"; error says why when not ready.
                "status": readiness["status"],
                "error": readiness["error"],
            }
        )

    discovery: dict[str, Any] = {
        "ok": True,
        "namespaces": [],
        "error": None,
    }

    try:
        discovery["namespaces"] = [
            source["value"] for source in list_static_namespaces()
        ]

    except StaticKBLoaderError as exc:
        logger.warning("Static KB discovery unavailable: %s", exc)

        discovery["ok"] = False
        discovery["error"] = str(exc)

    return {
        "sources": sources,
        "discovery": discovery,
    }