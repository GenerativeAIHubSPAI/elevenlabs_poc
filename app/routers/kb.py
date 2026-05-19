from fastapi import APIRouter
from app.schemas.requests import KBIngestTextRequest, KBSearchRequest
from app.services.kb import kb_ingest_text, kb_search

router = APIRouter()


@router.post("/kb/ingest-text")
async def ingest_text(body: KBIngestTextRequest):
    saved = kb_ingest_text(body.title, body.text, body.namespace)
    return {
        "namespace": body.namespace,
        "ingested_chunks": len(saved),
        "sample": saved[:3],
    }


@router.post("/kb/search")
async def search_kb(body: KBSearchRequest):
    return {
        "namespace": body.namespace,
        "results": kb_search(body.query, body.namespace, body.top_k),
    }