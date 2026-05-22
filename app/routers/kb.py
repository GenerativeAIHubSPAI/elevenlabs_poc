# app/routers/kb.py

from fastapi import APIRouter

from app.schemas.requests import KBIngestTextRequest, KBSearchRequest
from app.services.kb import kb_ingest_text, kb_search

router = APIRouter()


@router.post("/ingest-text")
async def ingest_text(body: KBIngestTextRequest):
    saved = kb_ingest_text(
        title=body.title,
        text=body.text,
        namespace=body.namespace,
    )

    return {
        "namespace": body.namespace,
        "ingested_chunks": len(saved),
        "sample": saved[:3],
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