# app/routers/chat.py

from fastapi import APIRouter

from app.schemas.requests import ChatRequest, ChatResponse, SourceChunk
from app.services.kb import kb_search
from app.services.llm import llm_client

router = APIRouter()


@router.post("/ask", response_model=ChatResponse)
async def ask(body: ChatRequest):
    matches = kb_search(
        query=body.question,
        namespace=body.namespace,
        top_k=body.top_k,
    )

    context = [
        {
            "chunk_id": m["chunk_id"],
            "title": m["title"],
            "text": m["text"],
            "score": m["score"],
        }
        for m in matches
    ]

    answer = await llm_client.answer(
        system_prompt=body.system_prompt,
        question=body.question,
        context_chunks=context,
    )

    return ChatResponse(
        answer=answer,
        sources=[
            SourceChunk(
                chunk_id=m["chunk_id"],
                title=m["title"],
                text=m["text"],
                score=m["score"],
            )
            for m in matches
        ],
    )