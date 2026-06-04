"""Knowledge-base API routes.

This module exposes endpoints for ingesting text and PDF documents into the
knowledge base and for searching stored chunks by namespace. It validates uploads,
extracts PDF text, delegates chunk creation and embedding to the knowledge-base
service, and returns ingestion/search results for downstream chat and voice flows.
"""
import logging

from app.services.kb import (
    EmbeddingConfigurationError,
    EmbeddingProviderError,
    KnowledgeBaseError,
    kb_ingest_text,
    kb_search,
)

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.schemas.requests import KBIngestTextRequest, KBSearchRequest
from app.services.kb import kb_ingest_text, kb_search
from app.services.pdf_parser import extract_pdf_pages

router = APIRouter()
logger = logging.getLogger(__name__)

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