from fastapi import APIRouter
from app.core.config import AGENT_ID, VOICE_ID, TTS_MODEL, STT_MODEL, LLM_MODEL
from app.services.elevenlabs import get_json

router = APIRouter()


@router.get("/")
async def root():
    return {
        "message": "API is running",
        "docs": "/docs",
        "routes": [
            "/health",
            "/eleven/user",
            "/eleven/models",
            "/eleven/voices",
            "/eleven/agents",
            "/config",
            "/stt",
            "/kb/ingest-text",
            "/kb/search",
            "/chat",
            "/tts",
        ],
    }


@router.get("/health")
async def health():
    return {"ok": True}


@router.get("/eleven/user")
async def eleven_user():
    return await get_json("/v1/user")


@router.get("/eleven/models")
async def eleven_models():
    return await get_json("/v1/models")


@router.get("/eleven/voices")
async def eleven_voices():
    return await get_json("/v1/voices")


@router.get("/eleven/agents")
async def eleven_agents():
    return await get_json("/v1/convai/agents")


@router.get("/config")
async def config():
    return {
        "agent_id": AGENT_ID or None,
        "voice_id": VOICE_ID or None,
        "tts_model": TTS_MODEL,
        "stt_model": STT_MODEL,
        "llm_model": LLM_MODEL,
    }