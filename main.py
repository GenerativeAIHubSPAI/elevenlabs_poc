# main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.routers.health as health
import app.routers.voice as voice
import app.routers.stt as stt
import app.routers.kb as kb
import app.routers.chat as chat
import app.routers.tts as tts


app = FastAPI(title="ElevenLabs Voice Bot Backend")

app.include_router(health.router, tags=["meta"])
app.include_router(stt.router, prefix="/stt", tags=["stt"])
app.include_router(tts.router, prefix="/tts", tags=["tts"])
app.include_router(kb.router, prefix="/kb", tags=["kb"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(voice.router, prefix="/chat", tags=["voice"])


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Transcript", "X-Reply-Text"],
)


@app.get("/")
async def root():
    return {
        "message": "Voice bot backend is running",
        "docs": "/docs",
        "routes": [
            "/health",
            "/models",
            "/voices",
            "/stt/transcribe",
            "/kb/ingest-text",
            "/kb/search",
            "/chat/ask",
            "/tts/speak",
            "/tts/stream",
            "/chat/voice-stream",
        ],
    }