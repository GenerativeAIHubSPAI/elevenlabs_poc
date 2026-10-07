"""LLM client for knowledge-grounded chatbot responses.

This module defines the LLM client used by the chat and voice pipelines to
generate assistant answers from a user question, optional conversation history,
and retrieved knowledge-base chunks.

Depending on LLM_PROVIDER, the client calls either Amazon Bedrock (Converse API,
model BEDROCK_MODEL_ID) or the OpenAI Responses API. It builds a compact prompt
that includes the system instructions, recent conversation history, the current user question, and
the retrieved context. Provider errors are raised as FastAPI HTTP exceptions so
API routes return proper error responses instead of embedding infrastructure
failures inside successful assistant answers.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re

import boto3
import httpx
from fastapi import HTTPException

from app.core.aws import aws_client_config
from app.core.config import get_settings
from app.core.system_prompts import FAREWELL_PHRASES

settings = get_settings()
logger = logging.getLogger(__name__)

# The model writes a one-line protocol-state note before each answer (see the
# per-turn instructions); it is stripped before the answer is returned.
STATE_TAG_RE = re.compile(r"<estado>(.*?)</estado>", re.S)

# Only applied on voice routes: TTS reads digits and symbols poorly, but the text
# chat should keep regular numerals.
SPOKEN_FORMAT_RULES = """            - Escribe siempre con palabras, tal y como se pronuncian, los números, cifras, precios, fechas, horas, porcentajes, unidades, símbolos y abreviaturas, en el idioma de la respuesta.
              Ejemplos: "384 KB" -> "trescientos ochenta y cuatro kilobytes"; "12,50 €" -> "doce euros con cincuenta"; "15%" -> "quince por ciento";
              "10:30" -> "las diez y media"; "3/5" -> "tres de cinco"; "Nº 2" -> "número dos"; "etc." -> "etcétera".
              Los códigos y referencias se leen carácter a carácter: "AB-12" -> "a, be, uno, dos".
              Los teléfonos se leen SIEMPRE dígito a dígito, también los cortos y los que empiezan por 900, respetando los grupos y nunca como cantidades:
              "1004" -> "uno, cero, cero, cuatro"; "900 300 400" -> "nueve, cero, cero; tres, cero, cero; cuatro, cero, cero"; en inglés "one, zero, zero, four".
              Las horas se leen de forma natural y coherente: "9:00 a 18:30" -> "de nueve de la mañana a seis y media de la tarde".
              No uses markdown, viñetas, emojis ni símbolos como *, #, /, & o +; exprésalos con palabras.\n"""


class LLMClient:
    """Client wrapper for Bedrock Converse and OpenAI Responses API calls."""

    def __init__(self) -> None:
        self._bedrock_client = None
        self.last_usage: dict | None = None
        self.last_state: str | None = None

    def _get_bedrock_client(self):
        if self._bedrock_client is None:
            if settings.AWS_BEARER_TOKEN_BEDROCK:
                os.environ["AWS_BEARER_TOKEN_BEDROCK"] = (
                    settings.AWS_BEARER_TOKEN_BEDROCK
                )

            self._bedrock_client = boto3.client(
                service_name="bedrock-runtime",
                region_name=settings.AWS_REGION,
                config=aws_client_config(read_timeout=60),
            )

        return self._bedrock_client

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
        spoken: bool = False,
        full_guide: str | None = None,
    ) -> str:
        """Generate an answer.

        ``spoken=True`` adds TTS-friendly formatting rules. ``full_guide`` passes the
        whole knowledge base in the (cached) system prompt instead of retrieved
        chunks; ``context_chunks`` is then ignored.
        """
        if full_guide:
            guide_block = (
                "Guía de atención (contexto completo de la base de conocimiento). "
                "Es tu única fuente de datos y procedimientos; síguela fielmente:\n"
                f"<guia>\n{full_guide}\n</guia>"
            )
            context_text = "[La guía completa está en el mensaje de sistema]"
        else:
            guide_block = None
            context_text = self._build_context_text(context_chunks)

        user_text = (
            """Instrucciones para esta respuesta:\n
            - Responde en español salvo que el usuario te hable en ingles, entonces responde en ingles.\n
            - Usa el historial para entender preguntas de seguimiento y mantener continuidad.\n
            - Si la pregunta actual depende de algo anterior, resuelve referencias como 'eso', 'ese', 'el segundo', 'that one' o 'it' usando el historial.\n
            - Usa el contexto de la base de conocimiento para responder datos concretos.\n
            - Si el contexto contiene nombres, referencias, precios, condiciones, pasos o procedimientos, úsalos con precisión.\n
            - Si el usuario hace una pregunta general como '¿en qué puedes ayudarme?', responde como un asistente real: 
              da una bienvenida breve si encaja de manera natural y no has dado la bienvenida anteriormente, ofrece opciones útiles de ayuda según el contexto disponible de manera breve.\n
            - Si no hay contexto relevante y la pregunta es general, no hables de limitaciones internas; guía al usuario hacia una consulta concreta.\n
            - Si el usuario pregunta por un dato concreto y no aparece en el contexto ni en el historial, dilo de forma amable en una frase; ofrece un paso alternativo solo si el contexto lo define. Nunca supongas ni inventes el dato.\n
            - Cumple siempre el protocolo de cierre del mensaje de sistema: si el usuario no necesita nada más o se despide, responde solo con la frase de despedida indicada, aunque quede algo pendiente.\n
            - En español trata siempre al usuario de usted (le, su, puede, desea), nunca de tú.\n
            - Cuando des lo que indica un paso de la guía, incluye todos los datos que la guía da para ese paso (plazos, canales, condiciones), sin añadir otros.\n
            - Si el paso que toca solo da información (no pregunta nada), di esa información completa y, en la misma respuesta, haz la pregunta del paso siguiente. Nunca omitas un paso informativo.\n
            - Si el usuario acepta una oferta o alternativa, su petición original (baja, cancelación…) queda anulada: di solo lo que la guía indica para la aceptación.\n
            - Antes de tu respuesta, escribe una sola línea entre <estado> y </estado>, que no se leerá al usuario, rellenando estos campos:
              <estado>pregunta o petición nueva: ... | despedida: sí/no | protocolo: ... | condiciones especiales cumplidas: ... | datos ya dados por el usuario: ... | paso: ... | rama: ... | protocolo terminado: sí/no | acción: ...</estado>
              "despedida" solo puede ser "sí" si "pregunta o petición nueva" es "ninguna" y el usuario dice que no necesita nada más, se despide o quiere terminar la llamada (aunque esté molesto o quede algo pendiente); entonces la acción es solo la frase de despedida, sin intentar retenerle. Si hay una pregunta o petición nueva, "despedida" es "no" y la atiendes.
              "paso" es siempre el primer paso pendiente del protocolo, empezando por el paso 1 si aún no has empezado.
              "protocolo terminado" es "sí" cuando en esta respuesta das la resolución final del protocolo, incluida una derivación a otro teléfono o canal (salvo que la guía diga no hacer más preguntas); entonces terminas con la pregunta de cierre. Mientras esperas que el usuario responda o compruebe algo, es "no" y no añades la pregunta de cierre.
              En "condiciones especiales cumplidas" revisa todas las condiciones del protocolo, también las de pasos posteriores (por ejemplo, fraude o excepciones), con lo que ya ha dicho el usuario; si alguna se cumple, la acción es aplicarla ya.
              Después escribe solo la respuesta para el usuario, que hace únicamente la acción indicada.\n
            - Si el mensaje de sistema define un protocolo por pasos (por ejemplo, ante un problema o incidencia), síguelo de forma estricta: eso incluye no combinar varias preguntas en la misma respuesta aunque parezca más eficiente. Ser "accionable" en ese caso significa avanzar un solo paso claro, no resolverlo todo de una vez.\n
            - Prioriza una respuesta clara, servicial y accionable antes que una respuesta larga, pero nunca a costa de romper un protocolo por pasos indicado en el mensaje de sistema.\n
            - intenta evitar fillers como "entiendo", "claro", "perfecto", "de acuerdo", "gracias por la información", 
              "es un placer ayudarte", "estoy aquí para ayudarte" y similares, a menos que encajen de forma natural en la respuesta.
            - No es necesario usar fillers en cada respuesta, y a veces es mejor omitirlos para sonar más directo y profesional.
            - Mantén un tono amable, paciente y positivo, sin sonar exagerado ni artificial.\n
            - La respuesta será leída en voz alta: usa frases naturales, breves y fáciles de pronunciar.\n"""
            f"{SPOKEN_FORMAT_RULES if spoken else ''}\n"
            f"Historial de conversación:\n{conversation_history or '[Sin historial previo]'}\n\n"
            f"Pregunta actual del usuario:\n{question}\n\n"
            f"Contexto de la base de conocimiento:\n{context_text or '[No se encontró contexto relevante en la base de conocimiento]'}"
        )

        if settings.LLM_PROVIDER == "bedrock":
            answer = await self._answer_bedrock(system_prompt, user_text, guide_block)
        else:
            full_system = f"{system_prompt}\n\n{guide_block}" if guide_block else system_prompt
            answer = await self._answer_openai(f"{full_system}\n\n{user_text}")

        self.last_state = self._extract_state(answer)
        return self._enforce_farewell(self._strip_state(answer))

    @staticmethod
    def _extract_state(answer: str) -> str | None:
        match = STATE_TAG_RE.search(answer)
        return match.group(1).strip() if match else None

    @staticmethod
    def _strip_state(answer: str) -> str:
        """Remove the model's private <estado> note so it never reaches the user or TTS."""
        text = STATE_TAG_RE.sub("", answer)
        # An unclosed tag would leak the note: drop everything up to the end of that line.
        text = re.sub(r"<estado>[^\n]*\n?", "", text)
        return text.replace("</estado>", "").strip()

    def _enforce_farewell(self, answer: str) -> str:
        """Return only the farewell phrase when the model used it, dropping any extra text."""
        normalized = answer.lower().replace("“", "").replace("”", "").replace('"', "")
        for phrase in FAREWELL_PHRASES:
            if phrase.lower() in normalized:
                return phrase
        return answer

    async def _answer_bedrock(
        self,
        system_prompt: str,
        user_text: str,
        guide_block: str | None = None,
    ) -> str:
        system: list[dict] = [{"text": system_prompt}]

        if guide_block:
            # The prompt and guide are identical on every turn of a call, so cache
            # them: later turns are faster and the cached tokens cost ~10%.
            system += [{"text": guide_block}, {"cachePoint": {"type": "default"}}]

        def _converse() -> dict:
            return self._get_bedrock_client().converse(
                modelId=settings.BEDROCK_MODEL_ID,
                system=system,
                messages=[{"role": "user", "content": [{"text": user_text}]}],
                inferenceConfig={
                    "maxTokens": settings.BEDROCK_MAX_TOKENS,
                    "temperature": settings.BEDROCK_TEMPERATURE,
                },
            )

        try:
            response = await asyncio.to_thread(_converse)
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail={
                    "provider": "bedrock",
                    "message": "Bedrock request failed. Check AWS_REGION, BEDROCK_MODEL_ID and credentials.",
                    "model": settings.BEDROCK_MODEL_ID,
                    "error": str(exc),
                },
            ) from exc

        self.last_usage = {
            **response.get("usage", {}),
            "latencyMs": response.get("metrics", {}).get("latencyMs"),
        }
        logger.info("Bedrock usage: %s", self.last_usage)

        content = response.get("output", {}).get("message", {}).get("content", [])
        text = "\n".join(block["text"] for block in content if "text" in block).strip()

        if not text:
            raise HTTPException(
                status_code=502,
                detail={
                    "provider": "bedrock",
                    "message": "Bedrock returned an empty response.",
                    "stop_reason": response.get("stopReason"),
                },
            )

        return text

    async def _answer_openai(self, input_text: str) -> str:
        if not settings.LLM_API_KEY:
            raise HTTPException(
                status_code=500,
                detail={
                    "provider": "openai",
                    "message": "LLM_API_KEY is not configured.",
                },
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