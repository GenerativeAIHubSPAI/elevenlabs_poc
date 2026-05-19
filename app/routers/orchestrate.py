from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.core.config import STT_MODEL, TTS_MODEL, VOICE_ID
from app.services.elevenlabs import transcribe_audio, synthesize_speech
from app.services.kb import kb_search
from app.services.llm import llm_answer

router = APIRouter()

_SYSTEM_PROMPT = (
    "You are a helpful voice assistant. "
    "Answer using the provided knowledge base context whenever possible. "
    "If the knowledge is insufficient, say what is missing."
)


@router.post("/orchestrate")
async def orchestrate(
    audio: UploadFile = File(...),
    language_code: str | None = Form(default=None),
    namespace: str = Form(default="default"),
    voice_id: str = Form(default=VOICE_ID),
):
    if not voice_id:
        raise HTTPException(status_code=400, detail="voice_id is required (set ELEVENLABS_VOICE_ID or pass voice_id)")

    # STT
    content = await audio.read()
    stt_result = await transcribe_audio(
        file_name=audio.filename,
        file_bytes=content,
        content_type=audio.content_type or "application/octet-stream",
        model_id=STT_MODEL,
        language_code=language_code,
    )
    transcript = stt_result.get("text", "")

    # Chat
    matches = kb_search(transcript, namespace)
    reply_text = await llm_answer(_SYSTEM_PROMPT, transcript, matches)

    # TTS
    tts_payload = {
        "text": reply_text,
        "model_id": TTS_MODEL,
        "output_format": "mp3_44100_128",
        "language_code": "es",
    }
    audio_stream, _ = await synthesize_speech(voice_id, tts_payload)

    return StreamingResponse(
        audio_stream,
        media_type="audio/mpeg",
        headers={
            "X-Transcript": transcript.encode("utf-8").hex(),
            "X-Reply-Text": reply_text.encode("utf-8").hex(),
        },
    )
