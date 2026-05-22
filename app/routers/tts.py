# app/routers/tts.py

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core.config import get_settings
from app.schemas.requests import TTSRequest
from app.services.elevenlabs import ElevenLabsClient

router = APIRouter()
settings = get_settings()
eleven = ElevenLabsClient()


def resolve_voice_id(voice_id: str | None) -> str:
    selected_voice_id = (
        voice_id
        or settings.ELEVENLABS_DEFAULT_VOICE_ID
        or settings.ELEVENLABS_VOICE_ID
    )

    if not selected_voice_id:
        raise HTTPException(
            status_code=400,
            detail="voice_id is required. Pass voice_id or set ELEVENLABS_DEFAULT_VOICE_ID.",
        )

    return selected_voice_id


@router.post("/speak")
async def speak(body: TTSRequest):
    audio = await eleven.tts(
        text=body.text,
        voice_id=resolve_voice_id(body.voice_id),
        model_id=body.model_id,
        output_format=body.output_format,
        language_code=body.language_code,
        voice_settings=body.voice_settings,
    )

    return StreamingResponse(audio, media_type="audio/mpeg")


@router.post("/stream")
async def stream_speak(body: TTSRequest):
    audio_stream = eleven.stream_tts(
        text=body.text,
        voice_id=resolve_voice_id(body.voice_id),
        model_id=body.model_id,
        output_format=body.output_format,
        language_code=body.language_code,
        voice_settings=body.voice_settings,
    )

    return StreamingResponse(audio_stream, media_type="audio/mpeg")