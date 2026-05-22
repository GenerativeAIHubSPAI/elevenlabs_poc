# app/routers/stt.py

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.services.elevenlabs import ElevenLabsClient

router = APIRouter()
eleven = ElevenLabsClient()


def clean_language_code(language_code: str | None) -> str:
    if not language_code:
        return "spa"

    language_code = language_code.strip()

    if not language_code or language_code.lower() == "string":
        return "spa"

    return language_code


@router.post("/transcribe")
async def transcribe(
    file: UploadFile = File(
        ...,
        description="Audio file to transcribe. Example: mp3, wav, m4a.",
    ),
    language_code: str | None = Form(
        default="spa",
        description="ElevenLabs language code. Use 'spa' for Spanish, 'eng' for English, 'cat' for Catalan.",
        examples=["spa"],
    ),
):
    content = await file.read()

    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    max_size_mb = 25
    if len(content) > max_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"Uploaded file is too large. Max allowed by this backend is {max_size_mb} MB.",
        )

    result = await eleven.transcribe(
        file_bytes=content,
        filename=file.filename or "audio",
        content_type=file.content_type or "application/octet-stream",
        language_code=clean_language_code(language_code),
    )

    return result