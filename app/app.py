import io
import os
import re
import uuid
from typing import Any, Optional
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
load_dotenv()

API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
AGENT_ID = os.getenv("ELEVENLABS_AGENT_ID", "")
BASE_URL = os.getenv("ELEVENLABS_BASE_URL", "https://api.elevenlabs.io")
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")
TTS_MODEL = os.getenv("ELEVENLABS_TTS_MODEL", "eleven_flash_v2_5")
STT_MODEL = os.getenv("ELEVENLABS_STT_MODEL", "scribe_v2")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4.1-mini")

if not API_KEY:
    raise RuntimeError("ELEVENLABS_API_KEY is required")

app = FastAPI(title="elevenlabs-voice-bot-backend")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        # "http://127.0.0.1:5500",
        # "http://localhost:5500",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Transcript", "X-Reply-Text"],
)

kb_store: dict[str, list[dict[str, Any]]] = {}


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


def normalize(text: str) -> list[str]:
    return re.findall(r"\b\w+\b", text.lower())


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 80) -> list[str]:
    words = text.split()
    if not words:
        return []

    chunks = []
    step = max(1, chunk_size - overlap)

    for i in range(0, len(words), step):
        chunk = " ".join(words[i:i + chunk_size]).strip()
        if chunk:
            chunks.append(chunk)

    return chunks


def kb_ingest_text(title: str, text: str, namespace: str):
    if namespace not in kb_store:
        kb_store[namespace] = []

    chunks = chunk_text(text)
    saved = []

    for chunk in chunks:
        item = {
            "chunk_id": str(uuid.uuid4()),
            "title": title,
            "text": chunk,
            "namespace": namespace,
        }
        kb_store[namespace].append(item)
        saved.append(item)

    return saved


def kb_search(query: str, namespace: str, top_k: int = 4):
    q_tokens = set(normalize(query))
    results = []

    for item in kb_store.get(namespace, []):
        c_tokens = set(normalize(item["text"]))
        overlap = len(q_tokens & c_tokens)
        if overlap == 0:
            continue

        score = overlap / max(len(q_tokens), 1)
        results.append({**item, "score": round(score, 4)})

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


async def llm_answer(system_prompt: str, question: str, context_chunks: list[dict[str, Any]]) -> str:
    context_text = "\n\n".join(
        [f"[{i+1}] {c['title']}\n{c['text']}" for i, c in enumerate(context_chunks)]
    ).strip()

    if not LLM_API_KEY:
        if context_text:
            return (
                "No LLM key configured yet. "
                "Most relevant knowledge found:\n\n"
                f"{context_text[:1500]}"
            )
        return "No LLM key configured yet, and no relevant knowledge was found."

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Question:\n{question}\n\n"
                    f"Knowledge base context:\n{context_text}\n\n"
                    "Answer clearly. Use the context when possible. "
                    "If the context does not fully support the answer, say so."
                ),
            },
        ],
        "temperature": 0.2,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{LLM_BASE_URL.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


class TTSRequest(BaseModel):
    text: str = Field(min_length=1)
    voice_id: str = Field(default=VOICE_ID)
    model_id: str = TTS_MODEL
    output_format: str = "mp3_44100_128"
    language_code: str = "es"
    voice_settings: Optional[dict[str, Any]] = None


class KBIngestTextRequest(BaseModel):
    title: str
    text: str
    namespace: str = "default"


class KBSearchRequest(BaseModel):
    query: str
    namespace: str = "default"
    top_k: int = 4


class ChatRequest(BaseModel):
    question: str
    namespace: str = "default"
    top_k: int = 4
    system_prompt: str = (
        "You are a helpful voice assistant. "
        "Answer using the provided knowledge base context whenever possible. "
        "If the knowledge is insufficient, say what is missing."
    )


@app.get("/")
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
    return {
        "agent_id": AGENT_ID or None,
        "voice_id": VOICE_ID or None,
        "tts_model": TTS_MODEL,
        "stt_model": STT_MODEL,
        "llm_model": LLM_MODEL,
    }


@app.post("/stt")
async def stt(
    file: UploadFile = File(...),
    language_code: str | None = Form(default=None),
):
    content = await file.read()

    data = {"model_id": STT_MODEL}
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


@app.post("/kb/ingest-text")
async def ingest_text(body: KBIngestTextRequest):
    saved = kb_ingest_text(body.title, body.text, body.namespace)
    return {
        "namespace": body.namespace,
        "ingested_chunks": len(saved),
        "sample": saved[:3],
    }


@app.post("/kb/search")
async def search_kb(body: KBSearchRequest):
    return {
        "namespace": body.namespace,
        "results": kb_search(body.query, body.namespace, body.top_k),
    }


@app.post("/chat")
async def chat(body: ChatRequest):
    matches = kb_search(body.question, body.namespace, body.top_k)
    answer = await llm_answer(body.system_prompt, body.question, matches)
    return {
        "answer": answer,
        "sources": matches,
    }

@app.post("/orchestrate")
async def orchestrate(
    audio: UploadFile = File(...),
    language_code: str | None = Form(default=None),
    namespace: str = Form(default="default"),
    voice_id: str = Form(default=VOICE_ID),
):
    if not voice_id:
        raise HTTPException(status_code=400, detail="voice_id is required (set ELEVENLABS_VOICE_ID or pass voice_id)")

    # STT
    content = await audio.read()
    stt_data = {"model_id": STT_MODEL}
    if language_code:
        stt_data["language_code"] = language_code

    async with httpx.AsyncClient(timeout=300) as client:
        stt_response = await client.post(
            f"{BASE_URL}/v1/speech-to-text",
            headers=api_headers(),
            data=stt_data,
            files={"file": (audio.filename, content, audio.content_type or "application/octet-stream")},
        )
    if stt_response.status_code >= 400:
        raise HTTPException(status_code=stt_response.status_code, detail=stt_response.text)

    transcript = stt_response.json().get("text", "")

    # Chat
    matches = kb_search(transcript, namespace)
    reply_text = await llm_answer(
        "You are a helpful voice assistant. Answer using the provided knowledge base context whenever possible.",
        transcript,
        matches,
    )

    # TTS
    tts_payload = {
        "text": reply_text,
        "model_id": TTS_MODEL,
        "output_format": "mp3_44100_128",
        "language_code": "es",
    }
    async with httpx.AsyncClient(timeout=120) as client:
        tts_response = await client.post(
            f"{BASE_URL}/v1/text-to-speech/{voice_id}",
            headers=api_headers({"Accept": "audio/mpeg", "Content-Type": "application/json"}),
            json=tts_payload,
        )
    if tts_response.status_code >= 400:
        raise HTTPException(status_code=tts_response.status_code, detail=tts_response.text)

    return StreamingResponse(
        io.BytesIO(tts_response.content),
        media_type="audio/mpeg",
        headers={
            "X-Transcript": transcript.encode("utf-8").hex(),
            "X-Reply-Text": reply_text.encode("utf-8").hex(),
        },
    )


@app.post(
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
