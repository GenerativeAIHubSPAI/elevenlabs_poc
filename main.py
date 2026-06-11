# main.py

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.routers.chat as chat
import app.routers.health as health
import app.routers.kb as kb
import app.routers.stt as stt
import app.routers.tts as tts
import app.routers.voice as voice
import app.routers.voice_turn as voice_turn

from app.services.static_kb_loader import (
    StaticKBLoaderError,
    list_static_namespaces,
    load_static_namespace,
)

logger = logging.getLogger(__name__)


async def preload_static_kbs() -> None:
    """Preload static KBs into memory when the backend container starts."""
    enabled = os.getenv("KB_AUTOLOAD_STATIC", "true").lower() not in {
        "0",
        "false",
        "no",
    }

    if not enabled:
        logger.info("Static KB autoload disabled.")
        return

    try:
        sources = list_static_namespaces()
        namespaces = [source["value"] for source in sources]

    except StaticKBLoaderError:
        logger.exception("Failed to discover static KB namespaces.")
        return

    if not namespaces:
        logger.warning("No static KB namespaces discovered.")
        return

    for namespace in namespaces:
        try:
            logger.info("Preloading static KB namespace=%s", namespace)

            result = await asyncio.to_thread(
                load_static_namespace,
                namespace,
            )

            logger.info(
                "Static KB preloaded namespace=%s documents=%s chunks=%s",
                namespace,
                result.get("documents_loaded"),
                result.get("chunks_ingested"),
            )

        except Exception:
            logger.exception(
                "Failed to preload static KB namespace=%s",
                namespace,
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    await preload_static_kbs()
    yield


app = FastAPI(
    title="ElevenLabs Voice Bot Backend",
    lifespan=lifespan,
)


_extra_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        *_extra_origins,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Transcript", "X-Reply-Text"],
)

app.include_router(health.router, tags=["meta"])
app.include_router(stt.router, prefix="/stt", tags=["stt"])
app.include_router(tts.router, prefix="/tts", tags=["tts"])
app.include_router(kb.router, prefix="/kb", tags=["kb"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(voice.router, prefix="/chat", tags=["voice"])
app.include_router(voice_turn.router, prefix="/voice", tags=["voice-turn"])


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
            "/kb/ingest-pdf",
            "/kb/search",
            "/kb/static-sources",
            "/kb/load-static",
            "/kb/load-static/{namespace}",
            "/chat/ask",
            "/chat/voice-stream",
            "/tts/speak",
            "/tts/stream",
            "/voice/turn",
        ],
    }