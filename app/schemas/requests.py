"""Request and response schemas.

This module defines Pydantic models used by the API routers for validating
request bodies and shaping structured responses. The schemas cover text-to-speech
requests, knowledge-base ingestion and search, chat requests, source chunks, and
chat responses.
"""

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

    knowledge_source: str = Field(
        default="insurance_company",
        examples=[
            "cache",
            "insurance_company",
            "flight_attendant",
            "gachapon_distribution",
        ],
        description="Selected frontend knowledge source.",
    )

    include_uploaded_pdfs: bool = Field(
        default=False,
        description="If true, also search PDFs uploaded during the current session.",
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
    user_id: str = Field(
        default="anonymous",
        examples=["anonymous", "user-123"],
        description=(
            "User identifier. For now this can be provided by the frontend. "
            "Later it should come from authentication."
        ),
    )

    session_id: str = Field(
        examples=["demo-session-001"],
        description=(
            "Conversation/session identifier. The frontend should generate this UUID "
            "when a new conversation starts and reuse it for follow-up questions."
        ),
    )

    question: str = Field(
        examples=["¿Qué puede hacer este asistente?"],
    )

    namespace: str = Field(
        default="default",
        examples=["default", "products"],
    )

    top_k: int = Field(
        default=7,
        examples=[7],
        ge=1,
        le=20,
    )
    system_prompt: str | None = Field(
        default=None,
        description=(
        "Optional system prompt override. If omitted or empty, the backend uses "
        "the default scalable business assistant prompt."
    ),
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "user_123",
                "session_id": "demo-session-001",
                "question": "¿En qué puesdes ayudarme?",
                "namespace": "default",
                "top_k": 7,
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
    user_id: str
    session_id: str