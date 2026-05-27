# app/services/llm.py

from __future__ import annotations

import httpx

from app.core.config import get_settings

import asyncio
import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError


settings = get_settings()


class LLMClient:
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

        return f"Unexpected LLM response format: {data}"

    async def answer(
        self,
        system_prompt: str,
        question: str,
        context_chunks: list[dict],
        conversation_history: str | None = None,
    ) -> str:
        if not settings.LLM_API_KEY:
            return (
                "LLM_API_KEY is not configured. "
                "Set LLM_API_KEY in .env to use the Azure/OpenAI Responses API."
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

        # Some GPT-5-style deployments may reject temperature.
        # Keep it only if your deployment supports it.
        if settings.LLM_TEMPERATURE is not None:
            payload["temperature"] = settings.LLM_TEMPERATURE

        headers = {
            "api-key": settings.LLM_API_KEY,
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    settings.LLM_BASE_URL,
                    headers=headers,
                    json=payload,
                )

            if response.is_error:
                try:
                    error_detail = response.json()
                except Exception:
                    error_detail = response.text

                if response.status_code == 401:
                    return (
                        "Azure/OpenAI request failed: 401 Unauthorized. "
                        "Check LLM_API_KEY."
                    )

                if response.status_code == 404:
                    return (
                        "Azure/OpenAI request failed: 404 Not Found. "
                        "Check LLM_BASE_URL, api-version, and model/deployment name."
                    )

                return (
                    f"Azure/OpenAI request failed: HTTP {response.status_code}. "
                    f"{error_detail}"
                )

            data = response.json()
            return self._extract_response_text(data)

        except httpx.RequestError as exc:
            return f"Azure/OpenAI request failed due to network error: {exc}"

        except Exception as exc:
            return f"Unexpected Azure/OpenAI error: {exc}"


# class LLMClientBedrock:
#     def _get_client(self):
#         if settings.AWS_BEARER_TOKEN_BEDROCK:
#             os.environ["AWS_BEARER_TOKEN_BEDROCK"] = settings.AWS_BEARER_TOKEN_BEDROCK

#         return boto3.client(
#             service_name="bedrock-runtime",
#             region_name=settings.AWS_REGION,
#         )

#     def _build_context_text(self, context_chunks: list[dict]) -> str:
#         return "\n\n".join(
#             [
#                 f"[{i + 1}] {chunk['title']}\n{chunk['text']}"
#                 for i, chunk in enumerate(context_chunks)
#             ]
#         ).strip()

#     def _answer_sync(
#         self,
#         system_prompt: str,
#         question: str,
#         context_chunks: list[dict],
#     ) -> str:
#         context_text = self._build_context_text(context_chunks)

#         user_content = (
#             f"Question:\n{question}\n\n"
#             f"Knowledge base context:\n{context_text or '[No relevant KB context found]'}\n\n"
#             "Answer clearly and only rely on the knowledge base when possible. "
#             "If the answer is not fully supported, say so."
#         )

#         client = self._get_client()

#         response = client.converse(
#             modelId=settings.BEDROCK_MODEL_ID,
#             messages=[
#                 {
#                     "role": "user",
#                     "content": [
#                         {
#                             "text": user_content,
#                         }
#                     ],
#                 }
#             ],
#             system=[
#                 {
#                     "text": system_prompt,
#                 }
#             ],
#             inferenceConfig={
#                 "maxTokens": settings.BEDROCK_MAX_TOKENS,
#                 "temperature": settings.BEDROCK_TEMPERATURE,
#             },
#         )

#         return response["output"]["message"]["content"][0]["text"].strip()

#     async def answer(
#         self,
#         system_prompt: str,
#         question: str,
#         context_chunks: list[dict],
#     ) -> str:
#         try:
#             return await asyncio.to_thread(
#                 self._answer_sync,
#                 system_prompt,
#                 question,
#                 context_chunks,
#             )

#         except NoCredentialsError:
#             return (
#                 "Bedrock credentials are not configured. "
#                 "Set AWS_BEARER_TOKEN_BEDROCK or standard AWS credentials."
#             )

#         except ClientError as exc:
#             error = exc.response.get("Error", {})
#             code = error.get("Code", "Unknown")
#             message = error.get("Message", str(exc))

#             return f"Bedrock request failed: {code}. {message}"

#         except BotoCoreError as exc:
#             return f"Bedrock request failed: {exc}"

#         except Exception as exc:
#             return f"Unexpected Bedrock error: {exc}"


# llm_client = LLMClientBedrock()
llm_client = LLMClient()