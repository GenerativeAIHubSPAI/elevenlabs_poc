"""Runtime metadata routes.

This module exposes application metadata useful for debugging and frontend
configuration. It reports selected runtime settings such as configured voice,
agent, model, and provider information without exposing sensitive credentials.
"""

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/config")
async def config():
    return {
        "elevenlabs": {
            "base_url": settings.ELEVENLABS_BASE_URL,
            "voice_id": settings.ELEVENLABS_DEFAULT_VOICE_ID or settings.ELEVENLABS_VOICE_ID,
            "agent_id": settings.ELEVENLABS_AGENT_ID,
            "tts_model": settings.ELEVENLABS_TTS_MODEL,
            "stt_model": settings.ELEVENLABS_STT_MODEL,
            "realtime_stt_model": settings.ELEVENLABS_REALTIME_STT_MODEL,
            "tts_output_format": settings.ELEVENLABS_TTS_OUTPUT_FORMAT,
            "stt_audio_format": settings.ELEVENLABS_STT_AUDIO_FORMAT,
            "stt_sample_rate": settings.ELEVENLABS_STT_SAMPLE_RATE,
        },
        "llm": {
            "base_url": settings.LLM_BASE_URL,
            "model": settings.LLM_MODEL,
            "configured": bool(settings.LLM_API_KEY),
        },
        "kb": {
            "default_namespace": settings.KB_DEFAULT_NAMESPACE,
            "chunk_size": settings.KB_CHUNK_SIZE,
            "chunk_overlap": settings.KB_CHUNK_OVERLAP,
            "top_k": settings.KB_TOP_K,
        },
        "output_dir": settings.OUTPUT_DIR,
    }