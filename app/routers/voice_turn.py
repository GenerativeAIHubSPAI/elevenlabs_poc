"""Single-turn voice orchestration routes.

This module exposes an audio-in/audio-out voice turn endpoint. It accepts a user
audio file, transcribes it with ElevenLabs, retrieves relevant knowledge-base
context, generates an assistant answer, and streams the spoken response back to
the client.

This route provides a simpler alternative to the realtime WebSocket pipeline for
testing and frontend integration.
"""

from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.core.config import get_settings
from app.services.elevenlabs import ElevenLabsClient
from app.services.kb import kb_search
from app.services.llm import llm_client

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


def clean_stt_language_code(language_code: str | None) -> str:
    if not language_code:
        return "spa"

    value = language_code.strip()

    if not value or value.lower() in {"string", "none", "null"}:
        return "spa"

    return value


def extract_transcript(stt_result: dict) -> str:
    transcript = (
        stt_result.get("text")
        or stt_result.get("transcript")
        or ""
    )

    return transcript.strip()


def safe_header_value(value: str) -> str:
    # Headers cannot safely contain arbitrary unicode/newlines.
    # URL-encoding lets the frontend decode it later.
    return quote(value.replace("\n", " ").strip())


@router.post("/turn")
async def voice_turn(
    file: UploadFile = File(...),
    voice_id: str | None = Form(default=None),
    namespace: str = Form(default="default"),
    language_code: str | None = Form(default="spa"),
    top_k: int = Form(default=4),
):
    selected_voice_id = resolve_voice_id(voice_id)

    content = await file.read()

    if not content:
        raise HTTPException(status_code=400, detail="Uploaded audio file is empty.")

    stt_result = await eleven.transcribe(
        file_bytes=content,
        filename=file.filename or "audio",
        content_type=file.content_type or "application/octet-stream",
        language_code=clean_stt_language_code(language_code),
    )

    transcript = extract_transcript(stt_result)

    if not transcript:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "No transcript was produced.",
                "stt_result": stt_result,
            },
        )

    matches = kb_search(
        query=transcript,
        namespace=namespace,
        top_k=top_k,
    )

    context = [
        {
            "chunk_id": item["chunk_id"],
            "title": item["title"],
            "text": item["text"],
            "score": item["score"],
        }
        for item in matches
    ]

    answer = await llm_client.answer(
        system_prompt=(
            "You are a concise Spanish voice assistant. "
            "Answer using the provided knowledge base context whenever possible. "
            "If the knowledge base does not contain the answer, say what is missing. "
            "Keep the answer short because it will be spoken aloud."
        ),
        question=transcript,
        context_chunks=context,
    )

    audio_stream = eleven.stream_tts(
        text=answer,
        voice_id=selected_voice_id,
        model_id=settings.ELEVENLABS_TTS_MODEL,
        output_format=settings.ELEVENLABS_TTS_OUTPUT_FORMAT,
        language_code=None,
    )

    return StreamingResponse(
        audio_stream,
        media_type="audio/mpeg",
        headers={
            "X-Transcript": safe_header_value(transcript),
            "X-Reply-Text": safe_header_value(answer),
            "X-Sources-Count": str(len(context)),
        },
    )