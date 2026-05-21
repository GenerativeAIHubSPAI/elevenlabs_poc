# app/services/elevenlabs.py

import io
from collections.abc import AsyncIterator

import httpx
from fastapi import HTTPException

from app.core.config import get_settings

settings = get_settings()

def _clean_tts_language_code(language_code: str | None) -> str | None:
    if not language_code:
        return None

    value = language_code.strip()

    if not value or value.lower() in {"string", "none", "null", "spa"}:
        return None

    return value

class ElevenLabsClient:
    def __init__(self):
        self.base_url = settings.ELEVENLABS_BASE_URL.rstrip("/")
        self.headers = {"xi-api-key": settings.ELEVENLABS_API_KEY}

    def _raise_elevenlabs_error(self, response: httpx.Response):
        try:
            detail = response.json()
        except Exception:
            detail = response.text

        raise HTTPException(
            status_code=response.status_code,
            detail={
                "provider": "elevenlabs",
                "status_code": response.status_code,
                "error": detail,
            },
        )

    async def get_models(self):
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.get(
                f"{self.base_url}/v1/models",
                headers=self.headers,
            )

            if r.is_error:
                self._raise_elevenlabs_error(r)

            return r.json()

    async def get_voices(self):
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.get(
                f"{self.base_url}/v1/voices",
                headers=self.headers,
            )

            if r.is_error:
                self._raise_elevenlabs_error(r)

            return r.json()

    async def transcribe(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str = "audio/mpeg",
        language_code: str | None = None,
    ):
        data = {
            "model_id": settings.ELEVENLABS_STT_MODEL,
        }

        if language_code:
            data["language_code"] = language_code

        files = {
            "file": (
                filename,
                file_bytes,
                content_type or "application/octet-stream",
            )
        }

        async with httpx.AsyncClient(timeout=300) as client:
            r = await client.post(
                f"{self.base_url}/v1/speech-to-text",
                headers=self.headers,
                data=data,
                files=files,
            )

            if r.is_error:
                self._raise_elevenlabs_error(r)

            return r.json()

    async def tts(
        self,
        text: str,
        voice_id: str,
        model_id: str | None = None,
        output_format: str = "mp3_44100_128",
        language_code: str | None = None,
        voice_settings: dict | None = None,
    ):
        payload = {
            "text": text,
            "model_id": model_id or settings.ELEVENLABS_TTS_MODEL,
        }

        language_code = _clean_tts_language_code(language_code)

        if language_code:
            payload["language_code"] = language_code

        if voice_settings:
            payload["voice_settings"] = voice_settings

        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(
                f"{self.base_url}/v1/text-to-speech/{voice_id}",
                params={"output_format": output_format},
                headers={
                    **self.headers,
                    "Accept": "audio/mpeg",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

            if r.is_error:
                self._raise_elevenlabs_error(r)

            return io.BytesIO(r.content)

    async def stream_tts(
        self,
        text: str,
        voice_id: str,
        model_id: str | None = None,
        output_format: str = "mp3_44100_128",
        language_code: str | None = None,
        voice_settings: dict | None = None,
    ) -> AsyncIterator[bytes]:
        payload = {
            "text": text,
            "model_id": model_id or settings.ELEVENLABS_TTS_MODEL,
        }

        language_code = _clean_tts_language_code(language_code)

        if language_code:
            payload["language_code"] = language_code

        if voice_settings:
            payload["voice_settings"] = voice_settings

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/v1/text-to-speech/{voice_id}/stream",
                params={"output_format": output_format},
                headers={
                    **self.headers,
                    "Accept": "audio/mpeg",
                    "Content-Type": "application/json",
                },
                json=payload,
            ) as r:
                if r.is_error:
                    body = await r.aread()
                    try:
                        detail = body.decode("utf-8")
                    except Exception:
                        detail = str(body)

                    raise HTTPException(
                        status_code=r.status_code,
                        detail={
                            "provider": "elevenlabs",
                            "status_code": r.status_code,
                            "error": detail,
                        },
                    )

                async for chunk in r.aiter_bytes():
                    if chunk:
                        yield chunk