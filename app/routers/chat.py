from fastapi import APIRouter
from app.schemas.requests import ChatRequest
from app.services.kb import kb_search
from app.services.llm import llm_answer

router = APIRouter()


@router.post("/chat")
async def chat(body: ChatRequest):
    matches = kb_search(body.question, body.namespace, body.top_k)
    answer = await llm_answer(body.system_prompt, body.question, matches)
    return {
        "answer": answer,
        "sources": matches,
    }