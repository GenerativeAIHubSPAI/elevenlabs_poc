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
            """Instrucciones para esta respuesta:\n
            - Responde en español salvo que el usuario te hable en ingles, entonces responde en ingles.\n
            - Usa el historial para entender preguntas de seguimiento y mantener continuidad.\n
            - Si la pregunta actual depende de algo anterior, resuelve referencias como 'eso', 'ese', 'el segundo', 'that one' o 'it' usando el historial.\n
            - Usa el contexto de la base de conocimiento para responder datos concretos.\n
            - Si el contexto contiene nombres, referencias, precios, condiciones, pasos o procedimientos, úsalos con precisión.\n
            - Si el usuario hace una pregunta general como '¿en qué puedes ayudarme?', responde como un asistente real: 
              da una bienvenida breve si encaja de manera natural y no has dado la bienvenida anteriormente, ofrece opciones útiles de ayuda según el contexto disponible de manera breve.\n
            - Si no hay contexto relevante y la pregunta es general, no hables de limitaciones internas; guía al usuario hacia una consulta concreta.\n
            - Si el usuario pregunta por un dato concreto y no aparece en el contexto ni en el historial, dilo de forma amable y ofrece el siguiente paso más útil.\n
            - Prioriza una respuesta clara, servicial y accionable antes que una respuesta larga.\n
            - intenta evitar fillers como "entiendo", "claro", "perfecto", "de acuerdo", "gracias por la información", 
              "es un placer ayudarte", "estoy aquí para ayudarte" y similares, a menos que encajen de forma natural en la respuesta.
            - No es necesario usar fillers en cada respuesta, y a veces es mejor omitirlos para sonar más directo y profesional.
            - Mantén un tono amable, paciente y positivo, sin sonar exagerado ni artificial.\n
            - La respuesta será leída en voz alta: usa frases naturales, breves y fáciles de pronunciar.\n\n"""
            f"Historial de conversación:\n{conversation_history or '[Sin historial previo]'}\n\n"
            f"Pregunta actual del usuario:\n{question}\n\n"
            f"Contexto de la base de conocimiento:\n{context_text or '[No se encontró contexto relevante en la base de conocimiento]'}"
        )

        payload = {
            "model": settings.LLM_MODEL,
            "input": input_text,
            "max_output_tokens": settings.LLM_MAX_OUTPUT_TOKENS,
        }

        # if settings.LLM_TEMPERATURE is not None:
        #     payload["temperature"] = settings.LLM_TEMPERATURE

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