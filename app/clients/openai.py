from openai import AsyncAzureOpenAI, AsyncOpenAI
from fastapi import HTTPException

from app.core.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_API_VERSION


def _get_client():
    if LLM_API_VERSION:
        return AsyncAzureOpenAI(
            api_key=LLM_API_KEY,
            azure_endpoint=LLM_BASE_URL,
            api_version=LLM_API_VERSION,
        )
    return AsyncOpenAI(
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
    )


async def call(system_prompt: str, user_content: str) -> str:
    client = _get_client()

    try:
        response = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_content},
            ],
            temperature=0.2,
            max_tokens=10,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI error: {e}")
