"""OpenAI client for knowledge-grounded chatbot responses.

This module defines the LLM client used by the chat and voice pipelines to
generate assistant answers from a user question, optional conversation history,
and retrieved knowledge-base chunks.

The client calls the OpenAI Responses API using the endpoint and API key
configured in application settings. It builds a compact prompt that includes the
system instructions, recent conversation history, the current user question, and
the retrieved context. Provider errors are raised as FastAPI HTTP exceptions so
API routes return proper error responses instead of embedding infrastructure
failures inside successful assistant answers.
"""

from __future__ import annotations

import httpx
from fastapi import HTTPException

from app.core.config import get_settings

settings = get_settings()


class LLMClient:
    """Client wrapper for OpenAI Responses API calls."""

    def _build_context_text(self, context_chunks: list[dict]) -> str:
        return "\n\n".join(
            [
                (
                    f"[{i + 1}] "
                    f"Title: {chunk.get('title', 'Untitled')}\n"
                    f"Source: {chunk.get('source_name', 'unknown')}\n"
                    f"Page: {chunk.get('page', 'unknown')}\n"
                    f"Content:\n{chunk.get('text', '')}"
                )
                for i, chunk in enumerate(context_chunks)
            ]
        ).strip()

    def _extract_response_text(self, data: dict) -> str:
        if isinstance(data.get("output_text"), str):
            return data["output_text"].strip()

        output = data.get("output", [])
        text_parts: list[str] = []

        for item in output:
            content = item.get("content", [])

            for content_item in content:
                if content_item.get("type") in {"output_text", "text"}:
                    text = content_item.get("text")
                    if text:
                        text_parts.append(text)

        if text_parts:
            return "\n".join(text_parts).strip()

        choices = data.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content")
            if isinstance(content, str):
                return content.strip()

        raise HTTPException(
            status_code=502,
            detail={
                "provider": "openai",
                "message": "Unexpected OpenAI response format.",
                "response": data,
            },
        )

    def _raise_provider_error(self, response: httpx.Response) -> None:
        try:
            error_detail = response.json()
        except Exception:
            error_detail = response.text

        if response.status_code in {401, 403}:
            raise HTTPException(
                status_code=502,
                detail={
                    "provider": "openai",
                    "message": "LLM provider authentication failed. Check backend credentials.",
                    "upstream_status_code": response.status_code,
                    "error": error_detail,
                },
            )

        if response.status_code == 404:
            raise HTTPException(
                status_code=502,
                detail={
                    "provider": "openai",
                    "message": "OpenAI endpoint or model was not found. Check LLM_BASE_URL and LLM_MODEL.",
                    "upstream_status_code": response.status_code,
                    "error": error_detail,
                },
            )

        raise HTTPException(
            status_code=502,
            detail={
                "provider": "openai",
                "message": "OpenAI request failed.",
                "upstream_status_code": response.status_code,
                "error": error_detail,
            },
        )

    async def answer(
        self,
        system_prompt: str,
        question: str,
        context_chunks: list[dict],
        conversation_history: str | None = None,
    ) -> str:
        if not settings.LLM_API_KEY:
            raise HTTPException(
                status_code=500,
                detail={
                    "provider": "openai",
                    "message": "LLM_API_KEY is not configured.",
                },
            )

        context_text = self._build_context_text(context_chunks)

        input_text = (
            f"{system_prompt}\n\n"
            "Rules:\n"
            "- Answer in Spanish unless the user asks otherwise.\n"
            "- Use the conversation history to understand follow-up questions.\n"
            "- Use the knowledge base context for factual answers.\n"
            "- If the current question is a follow-up, resolve references like 'it', 'that one', 'the second one', 'ese', 'eso', 'el segundo', using the conversation history.\n"
            "- If the knowledge base context contains product catalogue information, extract product names, references, descriptions, and prices.\n"
            "- If the answer is not present in the context or history, say exactly what information is missing.\n"
            "- Keep the answer concise because it may be spoken aloud.\n\n"
            f"Conversation history:\n{conversation_history or '[No previous conversation history]'}\n\n"
            f"Current user question:\n{question}\n\n"
            f"Knowledge base context:\n{context_text or '[No relevant KB context found]'}"
        )

        payload = {
            "model": settings.LLM_MODEL,
            "input": input_text,
            "max_output_tokens": settings.LLM_MAX_OUTPUT_TOKENS,
        }

        if settings.LLM_TEMPERATURE is not None:
            payload["temperature"] = settings.LLM_TEMPERATURE

        headers = {
            "Authorization": f"Bearer {settings.LLM_API_KEY}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    settings.LLM_BASE_URL,
                    headers=headers,
                    json=payload,
                )

        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=502,
                detail={
                    "provider": "openai",
                    "message": "OpenAI network request failed.",
                    "error": str(exc),
                },
            ) from exc

        if response.is_error:
            self._raise_provider_error(response)

        data = response.json()
        return self._extract_response_text(data)


llm_client = LLMClient()