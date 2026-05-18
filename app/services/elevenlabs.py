import io
from typing import Optional

import httpx
from fastapi import HTTPException

from app.core.config import API_KEY, BASE_URL


def api_headers(extra: Optional[dict[str, str]] = None) -> dict[str, str]:
    headers = {"xi-api-key": API_KEY}
    if extra:
        headers.update(extra)
    return headers


async def get_json(path: str):
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(f"{BASE_URL}{path}", headers=api_headers())
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


async def synthesize_speech(voice_id: str, payload: dict):
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{BASE_URL}/v1/text-to-speech/{voice_id}",
            headers=api_headers(
                {
                    "Accept": "audio/mpeg",
                    "Content-Type": "application/json",
                }
            ),
            json=payload,
        )

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    return io.BytesIO(response.content), response.headers


async def transcribe_audio(file_name: str, file_bytes: bytes, content_type: str, model_id: str, language_code: str | None):
    data = {"model_id": model_id}
    if language_code:
        data["language_code"] = language_code

    files = {
        "file": (
            file_name,
            file_bytes,
            content_type or "application/octet-stream",
        )
    }

    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.post(
            f"{BASE_URL}/v1/speech-to-text",
            headers=api_headers(),
            data=data,
            files=files,
        )

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    return response.json()