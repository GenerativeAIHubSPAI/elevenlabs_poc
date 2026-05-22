# app/routers/kb.py

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.schemas.requests import KBIngestTextRequest, KBSearchRequest
from app.services.kb import kb_ingest_text, kb_search
from app.services.pdf_parser import extract_pdf_pages

router = APIRouter()


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
    if file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}",
        )

    content = await file.read()

    if not content:
        raise HTTPException(status_code=400, detail="Uploaded PDF is empty.")

    max_size_mb = 20
    if len(content) > max_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"PDF too large. Max allowed is {max_size_mb} MB.",
        )

    doc_title = title or file.filename or "uploaded_pdf"

    pages = extract_pdf_pages(content)

    if not pages:
        raise HTTPException(
            status_code=400,
            detail="No extractable text found in PDF. It may be scanned or image-based.",
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