# app/clients/openai.py

from openai import AsyncOpenAI

from app.core.config import get_settings

settings = get_settings()


def get_openai_client() -> AsyncOpenAI:
    if not settings.LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY is not configured.")

    return AsyncOpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
    )