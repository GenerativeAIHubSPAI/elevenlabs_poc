"""Knowledge-base API routes.

This module exposes endpoints for ingesting text and PDF documents into the
knowledge base and for searching stored chunks by namespace. It validates uploads,
extracts PDF text, delegates chunk creation and embedding to the knowledge-base
service, and returns ingestion/search results for downstream chat and voice flows.
"""

from datetime import UTC, datetime
from threading import Lock
from typing import Any
import logging

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)

from app.schemas.requests import KBIngestTextRequest, KBSearchRequest
from app.services.kb import (
    EmbeddingConfigurationError,
    EmbeddingProviderError,
    KnowledgeBaseError,
    kb_ingest_text,
    kb_search,
)
from app.services.pdf_parser import extract_pdf_pages
from app.services.static_kb_loader import (
    StaticKBLoaderError,
    list_static_namespaces,
    load_static_namespace,
)

router = APIRouter()
logger = logging.getLogger(__name__)

_static_kb_jobs: dict[str, dict[str, Any]] = {}
_static_kb_jobs_lock = Lock()


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(UTC).isoformat()


def _set_static_kb_job(namespace: str, payload: dict[str, Any]) -> None:
    """Store static KB load job status in memory."""
    with _static_kb_jobs_lock:
        current = _static_kb_jobs.get(namespace, {})
        _static_kb_jobs[namespace] = {
            **current,
            **payload,
            "updated_at": _now_iso(),
        }


def _get_static_kb_job(namespace: str) -> dict[str, Any] | None:
    """Get static KB load job status."""
    with _static_kb_jobs_lock:
        job = _static_kb_jobs.get(namespace)

        if job is None:
            return None

        return dict(job)


def _list_static_kb_jobs() -> list[dict[str, Any]]:
    """List static KB load job statuses."""
    with _static_kb_jobs_lock:
        return [dict(job) for job in _static_kb_jobs.values()]


def _run_static_kb_load(namespace: str) -> None:
    """Load one static KB namespace in the background."""
    _set_static_kb_job(
        namespace,
        {
            "namespace": namespace,
            "status": "running",
            "started_at": _now_iso(),
            "finished_at": None,
            "result": None,
            "error": None,
        },
    )

    try:
        logger.info("Background static KB load started namespace=%s", namespace)

        result = load_static_namespace(namespace)

        _set_static_kb_job(
            namespace,
            {
                "status": "succeeded",
                "finished_at": _now_iso(),
                "result": result,
                "error": None,
            },
        )

        logger.info(
            "Background static KB load succeeded namespace=%s result=%s",
            namespace,
            result,
        )

    except StaticKBLoaderError as exc:
        logger.exception(
            "Background static KB load failed namespace=%s",
            namespace,
        )

        _set_static_kb_job(
            namespace,
            {
                "status": "failed",
                "finished_at": _now_iso(),
                "result": None,
                "error": str(exc),
            },
        )

    except Exception as exc:
        logger.exception(
            "Unexpected background static KB load error namespace=%s",
            namespace,
        )

        _set_static_kb_job(
            namespace,
            {
                "status": "failed",
                "finished_at": _now_iso(),
                "result": None,
                "error": str(exc),
            },
        )


@router.post("/ingest-text")
async def ingest_text(body: KBIngestTextRequest):
    saved = kb_ingest_text(
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

    try:
        pages = extract_pdf_pages(content)

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

        all_saved = []

        for page in pages:
            saved = kb_ingest_text(
                title=doc_title,
                text=page["text"],
                namespace=namespace,
                source_type="pdf",
                source_name=file.filename,
                page=page["page"],
            )
            all_saved.extend(saved)

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
    return {
        "namespace": body.namespace,
        "results": kb_search(
            query=body.query,
            namespace=body.namespace,
            top_k=body.top_k,
        ),
    }


@router.post(
    "/load-static",
    status_code=status.HTTP_202_ACCEPTED,
)
async def load_static_examples(background_tasks: BackgroundTasks):
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

    queued = []

    for namespace in namespaces:
        existing = _get_static_kb_job(namespace)

        if existing and existing.get("status") in {"queued", "running"}:
            queued.append(existing)
            continue

        _set_static_kb_job(
            namespace,
            {
                "namespace": namespace,
                "status": "queued",
                "queued_at": _now_iso(),
                "started_at": None,
                "finished_at": None,
                "result": None,
                "error": None,
            },
        )

        background_tasks.add_task(_run_static_kb_load, namespace)

        job = _get_static_kb_job(namespace)

        if job is not None:
            queued.append(job)

    return {
        "status": "queued",
        "jobs": queued,
    }


@router.post(
    "/load-static/{namespace}",
    status_code=status.HTTP_202_ACCEPTED,
)
async def load_static_example(
    namespace: str,
    background_tasks: BackgroundTasks,
):
    """Queue static KB loading for one namespace."""
    existing = _get_static_kb_job(namespace)

    if existing and existing.get("status") in {"queued", "running"}:
        return existing

    _set_static_kb_job(
        namespace,
        {
            "namespace": namespace,
            "status": "queued",
            "queued_at": _now_iso(),
            "started_at": None,
            "finished_at": None,
            "result": None,
            "error": None,
        },
    )

    background_tasks.add_task(_run_static_kb_load, namespace)

    return _get_static_kb_job(namespace)


@router.get("/static-status")
def list_static_load_statuses():
    """List static KB loading statuses."""
    return {
        "jobs": _list_static_kb_jobs(),
    }


@router.get("/static-status/{namespace}")
def get_static_load_status(namespace: str):
    """Get static KB loading status for one namespace."""
    job = _get_static_kb_job(namespace)

    if job is None:
        return {
            "namespace": namespace,
            "status": "not_started",
        }

    return job


@router.get("/static-sources")
def list_static_sources():
    """List available static KB namespaces from S3 folders."""
    try:
        return {
            "sources": list_static_namespaces(),
        }

    except StaticKBLoaderError as exc:
        logger.exception("Static KB source listing failed.")

        raise HTTPException(
            status_code=500,
            detail={
                "code": "static_kb_source_listing_error",
                "message": str(exc),
            },
        ) from exc