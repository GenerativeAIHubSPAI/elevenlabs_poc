# app/schemas/requests.py

from typing import Any

from pydantic import BaseModel, Field


class TTSRequest(BaseModel):
    text: str = Field(
        min_length=1,
        examples=["Hola, soy tu asistente de voz. ¿En qué puedo ayudarte?"],
    )
    voice_id: str | None = Field(
        default=None,
        examples=["CwhRBWXzGAHq8TQ4Fs17"],
        description="Optional. If empty, the backend uses ELEVENLABS_DEFAULT_VOICE_ID.",
    )
    model_id: str | None = Field(
        default=None,
        examples=["eleven_flash_v2_5"],
        description="Optional. If empty, the backend uses ELEVENLABS_TTS_MODEL.",
    )
    output_format: str = Field(
        default="mp3_44100_128",
        examples=["mp3_44100_128"],
    )
    language_code: str | None = Field(
        default=None,
        examples=[None],
        description="Optional for TTS. Leave empty so ElevenLabs infers the language from the text.",
    )
    voice_settings: dict[str, Any] | None = Field(
        default=None,
        examples=[
            {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True,
            }
        ],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "text": "Hola, soy tu asistente de voz. ¿En qué puedo ayudarte?",
                "voice_id": "CwhRBWXzGAHq8TQ4Fs17",
                "model_id": "eleven_flash_v2_5",
                "output_format": "mp3_44100_128",
                "language_code": None,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                    "style": 0.0,
                    "use_speaker_boost": True,
                },
            }
        }
    }

class SpeakRequest(TTSRequest):
    """Backward-compatible alias for older code using SpeakRequest."""


class KBIngestTextRequest(BaseModel):
    title: str = Field(
        examples=["Manual interno de pruebas"],
    )
    text: str = Field(
        examples=[
            "Este documento explica cómo usar el chatbot de voz con ElevenLabs y una base de conocimiento local."
        ],
    )
    namespace: str = Field(
        default="default",
        examples=["default"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Manual interno de pruebas",
                "text": "Este documento explica cómo usar el chatbot de voz con ElevenLabs y una base de conocimiento local.",
                "namespace": "default",
            }
        }
    }


class KBSearchRequest(BaseModel):
    query: str = Field(
        examples=["¿Cómo funciona el chatbot de voz?"],
    )
    namespace: str = Field(
        default="default",
        examples=["default"],
    )
    top_k: int = Field(
        default=4,
        examples=[4],
        ge=1,
        le=20,
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "¿Cómo funciona el chatbot de voz?",
                "namespace": "default",
                "top_k": 4,
            }
        }
    }


class ChatRequest(BaseModel):
    question: str = Field(
        examples=["¿Qué puede hacer este asistente?"],
    )
    namespace: str = Field(
        default="default",
        examples=["default"],
    )
    top_k: int = Field(
        default=4,
        examples=[4],
        ge=1,
        le=20,
    )
    system_prompt: str = Field(
        default=(
            "You are a helpful voice assistant. "
            "Answer using the provided knowledge base context whenever possible. "
            "If the knowledge is insufficient, say what is missing."
        ),
        examples=[
            (
                "You are a concise Spanish voice assistant. "
                "Answer using the provided knowledge base context whenever possible. "
                "Keep the answer short because it will be spoken aloud."
            )
        ],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "question": "¿Qué puede hacer este asistente?",
                "namespace": "default",
                "top_k": 4,
                "system_prompt": (
                    "You are a concise Spanish voice assistant. "
                    "Answer using the provided knowledge base context whenever possible. "
                    "Keep the answer short because it will be spoken aloud."
                ),
            }
        }
    }


class SourceChunk(BaseModel):
    chunk_id: str
    title: str
    text: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]