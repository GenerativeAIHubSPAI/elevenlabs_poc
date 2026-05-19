import httpx
from fastapi import HTTPException

from app.core.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


async def llm_answer(system_prompt: str, question: str, context_chunks: list[dict]) -> str:
    context_text = "\n\n".join(
        [f"[{i+1}] {c['title']}\n{c['text']}" for i, c in enumerate(context_chunks)]
    ).strip()

    if not LLM_API_KEY:
        if context_text:
            return (
                "No LLM key configured yet. "
                "Most relevant knowledge found:\n\n"
                f"{context_text[:1500]}"
            )
        return "No LLM key configured yet, and no relevant knowledge was found."

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Question:\n{question}\n\n"
                    f"Knowledge base context:\n{context_text}\n\n"
                    "Answer clearly. Use the context when possible. "
                    "If the context does not fully support the answer, say so."
                ),
            },
        ],
        "temperature": 0.2,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{LLM_BASE_URL.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    data = response.json()
    return data["choices"][0]["message"]["content"].strip()