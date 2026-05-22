# app/routers/health.py

from fastapi import APIRouter

from app.services.elevenlabs import ElevenLabsClient

router = APIRouter()
eleven = ElevenLabsClient()


@router.get("/health")
async def health():
    return {"ok": True}


@router.get("/models")
async def models():
    return await eleven.get_models()


@router.get("/voices")
async def voices():
    return await eleven.get_voices()