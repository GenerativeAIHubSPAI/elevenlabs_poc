# app/services/llm.py

from __future__ import annotations

import asyncio
import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from app.core.config import get_settings

settings = get_settings()


class LLMClient:
    def _get_client(self):
        if settings.AWS_BEARER_TOKEN_BEDROCK:
            os.environ["AWS_BEARER_TOKEN_BEDROCK"] = settings.AWS_BEARER_TOKEN_BEDROCK

        return boto3.client(
            service_name="bedrock-runtime",
            region_name=settings.AWS_REGION,
        )

    def _build_context_text(self, context_chunks: list[dict]) -> str:
        return "\n\n".join(
            [
                f"[{i + 1}] {chunk['title']}\n{chunk['text']}"
                for i, chunk in enumerate(context_chunks)
            ]
        ).strip()

    def _answer_sync(
        self,
        system_prompt: str,
        question: str,
        context_chunks: list[dict],
    ) -> str:
        context_text = self._build_context_text(context_chunks)

        user_content = (
            f"Question:\n{question}\n\n"
            f"Knowledge base context:\n{context_text or '[No relevant KB context found]'}\n\n"
            "Answer clearly and only rely on the knowledge base when possible. "
            "If the answer is not fully supported, say so."
        )

        client = self._get_client()

        response = client.converse(
            modelId=settings.BEDROCK_MODEL_ID,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "text": user_content,
                        }
                    ],
                }
            ],
            system=[
                {
                    "text": system_prompt,
                }
            ],
            inferenceConfig={
                "maxTokens": settings.BEDROCK_MAX_TOKENS,
                "temperature": settings.BEDROCK_TEMPERATURE,
            },
        )

        return response["output"]["message"]["content"][0]["text"].strip()

    async def answer(
        self,
        system_prompt: str,
        question: str,
        context_chunks: list[dict],
    ) -> str:
        try:
            return await asyncio.to_thread(
                self._answer_sync,
                system_prompt,
                question,
                context_chunks,
            )

        except NoCredentialsError:
            return (
                "Bedrock credentials are not configured. "
                "Set AWS_BEARER_TOKEN_BEDROCK or standard AWS credentials."
            )

        except ClientError as exc:
            error = exc.response.get("Error", {})
            code = error.get("Code", "Unknown")
            message = error.get("Message", str(exc))

            return f"Bedrock request failed: {code}. {message}"

        except BotoCoreError as exc:
            return f"Bedrock request failed: {exc}"

        except Exception as exc:
            return f"Unexpected Bedrock error: {exc}"


llm_client = LLMClient()