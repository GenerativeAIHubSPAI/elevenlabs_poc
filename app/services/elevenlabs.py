"""ElevenLabs API service.

This module provides an asynchronous client wrapper for ElevenLabs APIs used by
the backend. It supports model and voice listing, file-based transcription,
standard text-to-speech, and streaming text-to-speech.

Provider errors are converted into FastAPI HTTP exceptions so API routes return
structured error responses instead of generic internal server errors.
"""

import io
from collections.abc import AsyncIterator
from typing import Any

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

    async def get_voices(
        self,
        language: str | None = None,
        gender: str | None = None,
        accent: str | None = None,
        use_case: str | None = None,
        category: str | None = None,
        search: str | None = None,
        include_raw: bool = False,
    ):
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.get(
                f"{self.base_url}/v1/voices",
                headers=self.headers,
            )

            if r.is_error:
                self._raise_elevenlabs_error(r)

            payload = r.json()

        raw_voices = payload.get("voices", [])

        voices = [
            self._normalize_voice(voice)
            for voice in raw_voices
            if self._voice_matches(
                voice,
                language=language,
                gender=gender,
                accent=accent,
                use_case=use_case,
                category=category,
                search=search,
            )
        ]

        result = {
            "count": len(voices),
            "filters": {
                "language": language,
                "gender": gender,
                "accent": accent,
                "use_case": use_case,
                "category": category,
                "search": search,
            },
            "voices": voices,
        }

        if include_raw:
            result["raw"] = payload

        return result

    def _voice_matches(
        self,
        voice: dict[str, Any],
        language: str | None = None,
        gender: str | None = None,
        accent: str | None = None,
        use_case: str | None = None,
        category: str | None = None,
        search: str | None = None,
    ) -> bool:
        labels = voice.get("labels") or {}

        if category and self._norm(voice.get("category")) != self._norm(category):
            return False

        if gender and self._norm(labels.get("gender")) != self._norm(gender):
            return False

        if accent and self._norm(labels.get("accent")) != self._norm(accent):
            return False

        if use_case and self._norm(labels.get("use_case")) != self._norm(use_case):
            return False

        if language and not self._supports_language(voice, language):
            return False

        if search:
            search_value = self._norm(search) or ""
            haystack = " ".join(
                str(value or "")
                for value in [
                    voice.get("name"),
                    voice.get("description"),
                    voice.get("category"),
                    labels.get("gender"),
                    labels.get("age"),
                    labels.get("accent"),
                    labels.get("language"),
                    labels.get("use_case"),
                    labels.get("descriptive"),
                ]
            ).lower()

            if search_value not in haystack:
                return False

        return True

    def _supports_language(
        self,
        voice: dict[str, Any],
        language: str,
    ) -> bool:
        target = self._norm(language)
        labels = voice.get("labels") or {}
        fine_tuning = voice.get("fine_tuning") or {}

        candidates = {
            self._norm(labels.get("language")),
            self._norm(fine_tuning.get("language")),
        }

        for item in voice.get("verified_languages") or []:
            candidates.add(self._norm(item.get("language")))
            candidates.add(self._norm(item.get("locale")))

        return target in candidates

    def _normalize_voice(self, voice: dict[str, Any]) -> dict[str, Any]:
        labels = voice.get("labels") or {}
        verified_languages = voice.get("verified_languages") or []

        supported_languages = sorted(
            {
                item.get("language")
                for item in verified_languages
                if item.get("language")
            }
        )

        supported_locales = sorted(
            {
                item.get("locale")
                for item in verified_languages
                if item.get("locale")
            }
        )

        return {
            "voice_id": voice.get("voice_id"),
            "name": voice.get("name"),
            "category": voice.get("category"),
            "description": voice.get("description"),
            "preview_url": voice.get("preview_url"),
            "gender": labels.get("gender"),
            "age": labels.get("age"),
            "accent": labels.get("accent"),
            "language": labels.get("language"),
            "use_case": labels.get("use_case"),
            "descriptive": labels.get("descriptive"),
            "supported_languages": supported_languages,
            "supported_locales": supported_locales,
            "models": voice.get("high_quality_base_model_ids") or [],
            "is_owner": voice.get("is_owner"),
            "is_bookmarked": voice.get("is_bookmarked"),
        }

    def _norm(self, value: Any) -> str | None:
        if value is None:
            return None

        value = str(value).strip().lower()

        if not value:
            return None

        return value

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