from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import meta, stt, kb, chat, tts

app = FastAPI(title="elevenlabs-voice-bot-backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meta.router)
app.include_router(stt.router)
app.include_router(kb.router)
app.include_router(chat.router)
app.include_router(tts.router)