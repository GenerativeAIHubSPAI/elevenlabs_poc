# app.py
import io
import os
from typing import Any, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

load_dotenv()

API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
AGENT_ID = os.getenv("ELEVENLABS_AGENT_ID", "")
BASE_URL = "https://api.elevenlabs.io"

if not API_KEY:
    raise RuntimeError("ELEVENLABS_API_KEY is required")

app = FastAPI(title="elevenlabs-voice-bot-backend")


def api_headers(extra: Optional[dict[str, str]] = None) -> dict[str, str]:
    headers = {"xi-api-key": API_KEY}
    if extra:
        headers.update(extra)
    return headers


async def get_json(path: str):
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(f"{BASE_URL}{path}", headers=api_headers())
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


class TTSRequest(BaseModel):
    text: str = Field(min_length=1)
    voice_id: str
    model_id: str = "eleven_v3"
    output_format: str = "mp3_44100_128"
    language_code: Optional[str] = None
    voice_settings: Optional[dict[str, Any]] = None


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/eleven/user")
async def eleven_user():
    return await get_json("/v1/user")


@app.get("/eleven/models")
async def eleven_models():
    return await get_json("/v1/models")


@app.get("/eleven/voices")
async def eleven_voices():
    return await get_json("/v1/voices")


@app.get("/eleven/agents")
async def eleven_agents():
    return await get_json("/v1/convai/agents")


@app.get("/config")
async def config():
    return {"agent_id": AGENT_ID or None}


@app.post("/tts")
async def tts(body: TTSRequest):
    payload = body.model_dump(exclude_none=True)

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{BASE_URL}/v1/text-to-speech/{body.voice_id}",
            headers=api_headers(
                {
                    "Accept": "audio/mpeg",
                    "Content-Type": "application/json",
                }
            ),
            json=payload,
        )

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    return StreamingResponse(
        io.BytesIO(response.content),
        media_type="audio/mpeg",
        headers={
            "X-Eleven-Request-Id": response.headers.get("request-id", ""),
            "X-Eleven-Character-Count": response.headers.get("x-character-count", ""),
        },
    )


@app.post("/stt")
async def stt(
    file: UploadFile = File(...),
    model_id: str = Form(default=os.getenv("ELEVENLABS_STT_MODEL", "scribe_v2")),
    language_code: Optional[str] = Form(default=None),
):
    content = await file.read()

    data = {"model_id": model_id}
    if language_code:
        data["language_code"] = language_code

    files = {
        "file": (
            file.filename,
            content,
            file.content_type or "application/octet-stream",
        )
    }

    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.post(
            f"{BASE_URL}/v1/speech-to-text",
            headers=api_headers(),
            data=data,
            files=files,
        )

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    return JSONResponse(response.json())