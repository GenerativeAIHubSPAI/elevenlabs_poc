from typing import Any, Optional
from pydantic import BaseModel, Field
from app.core.config import VOICE_ID, TTS_MODEL


class TTSRequest(BaseModel):
    text: str = Field(min_length=1)
    voice_id: str = Field(default=VOICE_ID)
    model_id: str = TTS_MODEL
    output_format: str = "mp3_44100_128"
    language_code: str = "es"
    voice_settings: Optional[dict[str, Any]] = None


class KBIngestTextRequest(BaseModel):
    title: str
    text: str
    namespace: str = "default"


class KBSearchRequest(BaseModel):
    query: str
    namespace: str = "default"
    top_k: int = 4


class ChatRequest(BaseModel):
    question: str
    namespace: str = "default"
    top_k: int = 4
    system_prompt: str = (
        "You are a helpful voice assistant. "
        "Answer using the provided knowledge base context whenever possible. "
        "If the knowledge is insufficient, say what is missing."
    )