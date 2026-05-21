# app/services/llm.py

import httpx

from app.core.config import get_settings

settings = get_settings()


class LLMClient:
    async def answer(
        self,
        system_prompt: str,
        question: str,
        context_chunks: list[dict],
    ) -> str:
        context_text = "\n\n".join(
            [
                f"[{i + 1}] {c['title']}\n{c['text']}"
                for i, c in enumerate(context_chunks)
            ]
        ).strip()

        if not settings.LLM_API_KEY:
            if context_text:
                return (
                    "No LLM key configured yet. "
                    "Based on the knowledge base, the most relevant context is:\n\n"
                    f"{context_text[:1200]}"
                )

            return "No LLM key configured yet, and no relevant knowledge was found."

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Question:\n{question}\n\n"
                    f"Knowledge base context:\n{context_text}\n\n"
                    "Answer clearly and only rely on the knowledge base when possible. "
                    "If the answer is not fully supported, say so."
                ),
            },
        ]

        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.LLM_MODEL,
                    "messages": messages,
                    "temperature": 0.2,
                },
            )
            r.raise_for_status()
            data = r.json()

        return data["choices"][0]["message"]["content"].strip()


llm_client = LLMClient()