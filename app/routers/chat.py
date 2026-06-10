"""Chat API routes.

This module exposes the chat endpoint used to answer user questions with
knowledge-base context and conversation memory. It retrieves relevant chunks,
builds session-aware context, calls the LLM service, stores the conversation
turns, and returns the assistant answer with source metadata.
"""

from fastapi import APIRouter, HTTPException

from app.schemas.requests import ChatRequest, ChatResponse, SourceChunk
from app.core.system_prompts import resolve_system_prompt
from app.services.llm import llm_client
from app.services.memory import add_turn, format_history
from app.core.knowledge_sources import resolve_knowledge_namespaces
from app.services.kb import kb_search_many


router = APIRouter()


@router.post("/ask", response_model=ChatResponse)
async def ask(body: ChatRequest):
    conversation_key = f"{body.user_id}:{body.session_id}"

    conversation_history = format_history(
        conversation_key=conversation_key,
        max_turns=8,
    )

    retrieval_query = (
        f"{conversation_history}\n\nCurrent question: {body.question}"
        if conversation_history
        else body.question
    )

    knowledge_source = getattr(body, "knowledge_source", None) or body.namespace
    include_uploaded_pdfs = getattr(body, "include_uploaded_pdfs", False)

    try:
        namespaces = resolve_knowledge_namespaces(
            knowledge_source=knowledge_source,
            session_id=body.session_id,
            include_uploaded_pdfs=include_uploaded_pdfs,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_knowledge_source",
                "message": str(exc),
            },
        ) from exc

    matches = kb_search_many(
        query=retrieval_query,
        namespaces=namespaces,
        top_k=body.top_k,
    )

    context = [
        {
            "chunk_id": m["chunk_id"],
            "title": m["title"],
            "text": m["text"],
            "score": m["score"],
            "source_name": m.get("source_name"),
            "page": m.get("page"),
        }
        for m in matches
    ]

    system_prompt = (
        body.system_prompt.strip()
        if body.system_prompt and body.system_prompt.strip()
        else resolve_system_prompt(
            namespace=body.namespace,
            knowledge_source=knowledge_source,
        )
    )

    answer = await llm_client.answer(
        system_prompt=system_prompt,
        question=body.question,
        context_chunks=context,
        conversation_history=conversation_history,
    )

    add_turn(
        conversation_key=conversation_key,
        role="user",
        content=body.question,
    )

    add_turn(
        conversation_key=conversation_key,
        role="assistant",
        content=answer,
        metadata={
            "sources": context,
            "knowledge_source": knowledge_source,
            "namespaces": namespaces,
            "include_uploaded_pdfs": include_uploaded_pdfs,
        },
    )

    return ChatResponse(
        answer=answer,
        user_id=body.user_id,
        session_id=body.session_id,
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