from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from app.core.config import STT_MODEL
from app.services.elevenlabs import transcribe_audio

router = APIRouter()


@router.post("/stt")
async def stt(
    file: UploadFile = File(...),
    language_code: str | None = Form(default=None),
):
    content = await file.read()
    result = await transcribe_audio(
        file_name=file.filename,
        file_bytes=content,
        content_type=file.content_type or "application/octet-stream",
        model_id=STT_MODEL,
        language_code=language_code,
    )
    return JSONResponse(result)