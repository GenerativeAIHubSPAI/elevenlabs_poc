"""Chat API routes.

This module exposes the chat endpoint used to answer user questions with
knowledge-base context and conversation memory. It retrieves relevant chunks,
builds session-aware context, calls the LLM service, stores the conversation
turns, and returns the assistant answer with source metadata.
"""

from fastapi import APIRouter

from app.schemas.requests import ChatRequest, ChatResponse, SourceChunk
from app.services.kb import kb_search
from app.services.llm import llm_client
from app.services.memory import add_turn, format_history

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

    matches = kb_search(
        query=retrieval_query,
        namespace=body.namespace,
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

    answer = await llm_client.answer(
        system_prompt=body.system_prompt,
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
            "namespace": body.namespace,
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