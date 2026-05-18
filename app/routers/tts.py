from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas.requests import TTSRequest
from app.services.elevenlabs import synthesize_speech

router = APIRouter()


@router.post(
    "/tts",
    responses={
        200: {
            "description": "MP3 audio stream",
            "content": {
                "audio/mpeg": {
                    "schema": {"type": "string", "format": "binary"}
                }
            },
        }
    },
)
async def tts(body: TTSRequest):
    if not body.voice_id:
        raise HTTPException(status_code=400, detail="voice_id is required")

    payload = body.model_dump(exclude_none=True)
    audio_stream, headers = await synthesize_speech(body.voice_id, payload)

    return StreamingResponse(
        audio_stream,
        media_type="audio/mpeg",
        headers={
            "X-Eleven-Request-Id": headers.get("request-id", ""),
            "X-Eleven-Character-Count": headers.get("x-character-count", ""),
        },
    )