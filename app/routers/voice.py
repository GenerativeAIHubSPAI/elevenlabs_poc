"""Realtime voice WebSocket routes.

This module implements the realtime voice-chat WebSocket pipeline. It receives
browser audio chunks, forwards them to ElevenLabs realtime speech to text,
processes committed transcripts with knowledge-base retrieval and LLM generation,
and streams synthesized assistant audio back to the client.

The route also supports interruption handling by cancelling active assistant
speech when the frontend sends an interrupt event.
"""

import asyncio
import base64
import json
from urllib.parse import urlencode
import contextlib
import uuid
import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.services.elevenlabs import ElevenLabsClient
from app.services.llm import llm_client
from app.services.kb import kb_search

router = APIRouter()
settings = get_settings()
eleven = ElevenLabsClient()

# ─── Voice ID matrix ──────────────────────────────────────────────────────────
# Key: (language_code, gender, tone)  → ElevenLabs voice_id
VOICE_MAP: dict[tuple[str, str, str], str] = {
    # ── Spanish ────────────────────────────────────────────────────────────────
    ("es", "hombre", "energico"): "eEyWolF7iBpMA65GbtAm",
    ("es", "hombre", "cercano"):  "w8u1dIxiWVelUtUQg1MB",
    ("es", "hombre", "serio"):    "m8dLaNJTf2Faapk51VKn",
    ("es", "mujer",  "energico"): "uQw4jpKzMLrZuo0RLPS9",
    ("es", "mujer",  "cercano"):  "1eHrpOW5l98cxiSRjbzJ",
    ("es", "mujer",  "serio"):    "kwNLkNjbQHMw9YUFZsHI",
    # ── English ────────────────────────────────────────────────────────────────
    ("en", "hombre", "energico"): "s0XGIcqmceN2l7kjsqoZ",
    ("en", "hombre", "cercano"):  "TWutjvRaJqAX89preB4e",
    ("en", "hombre", "serio"):    "xKhbyU7E3bC6T89Kn26c",
    ("en", "mujer",  "energico"): "8vf2Pg7VZD0Piv8GA8v9",
    ("en", "mujer",  "cercano"):  "2vbhUP8zyKg4dEZaTWGn",
    ("en", "mujer",  "serio"):    "gJx1vCzNCD1EQHT212Ls",
}


def _resolve_voice_id(
    explicit_voice_id: str | None,
    language_code: str | None,
    gender: str | None,
    tone: str | None,
) -> str | None:
    """
    Return the voice_id to use, in priority order:
    1. An explicit ?voice_id= query param (overrides everything).
    2. The VOICE_MAP lookup from language_code + gender + tone.
    3. The settings fallbacks (ELEVENLABS_DEFAULT_VOICE_ID / ELEVENLABS_VOICE_ID).
    """
    if explicit_voice_id:
        return explicit_voice_id

    if language_code and gender and tone:
        key = (language_code.lower(), gender.lower(), tone.lower())
        mapped = VOICE_MAP.get(key)
        if mapped:
            return mapped

    return settings.ELEVENLABS_DEFAULT_VOICE_ID or settings.ELEVENLABS_VOICE_ID


def _build_realtime_stt_url(language_code: str | None = None) -> str:
    query = {
        "model_id": settings.ELEVENLABS_REALTIME_STT_MODEL,
        "audio_format": settings.ELEVENLABS_STT_AUDIO_FORMAT,
        "commit_strategy": "vad",
        "vad_silence_threshold_secs": "1.2",
        "vad_threshold": "0.4",
        "min_speech_duration_ms": "100",
        "min_silence_duration_ms": "250",
        "include_timestamps": "false",
    }

    if language_code:
        query["language_code"] = language_code

    return f"wss://api.elevenlabs.io/v1/speech-to-text/realtime?{urlencode(query)}"

async def _send_answer_audio(
    websocket: WebSocket,
    answer: str,
    voice_id: str,
    turn_id: str,
    language_code: str | None = None,
):
    await websocket.send_json(
        {
            "type": "assistant_text",
            "turn_id": turn_id,
            "text": answer,
        }
    )

    try:
        async for chunk in eleven.stream_tts(
            text=answer,
            voice_id=voice_id,
            model_id=settings.ELEVENLABS_TTS_MODEL,
            output_format=settings.ELEVENLABS_TTS_OUTPUT_FORMAT,
            language_code=language_code,
        ):
            await websocket.send_json(
                {
                    "type": "assistant_audio_chunk",
                    "turn_id": turn_id,
                    "audio_base64": base64.b64encode(chunk).decode("utf-8"),
                    "format": settings.ELEVENLABS_TTS_OUTPUT_FORMAT,
                }
            )

        await websocket.send_json(
            {
                "type": "assistant_audio_done",
                "turn_id": turn_id,
            }
        )

    except asyncio.CancelledError:
        with contextlib.suppress(Exception):
            await websocket.send_json(
                {
                    "type": "assistant_interrupted",
                    "turn_id": turn_id,
                }
            )
        raise

    except Exception as exc:
        # Catch TTS errors (e.g. voice_not_found 404) and forward them to the
        # client over the WebSocket so the error is visible instead of only
        # appearing as an unhandled task exception in the server logs.
        with contextlib.suppress(Exception):
            await websocket.send_json(
                {
                    "type": "error",
                    "turn_id": turn_id,
                    "message": f"TTS error: {exc}",
                }
            )

@router.websocket("/voice-stream")
async def voice_stream(websocket: WebSocket):
    await websocket.accept()

    language_code = websocket.query_params.get("language_code")
    gender        = websocket.query_params.get("gender")
    tone          = websocket.query_params.get("tone")
    namespace     = websocket.query_params.get("namespace") or settings.KB_DEFAULT_NAMESPACE

    voice_id = _resolve_voice_id(
        explicit_voice_id=websocket.query_params.get("voice_id"),
        language_code=language_code,
        gender=gender,
        tone=tone,
    )

    if not voice_id:
        await websocket.send_json(
            {
                "type": "error",
                "message": "Missing voice_id. Pass ?voice_id=... or set ELEVENLABS_DEFAULT_VOICE_ID.",
            }
        )
        await websocket.close()
        return

    stt_url = _build_realtime_stt_url(language_code=language_code)

    current_tts_task: asyncio.Task | None = None
    current_turn_id: str | None = None

    try:
        async with websockets.connect(
            stt_url,
            additional_headers={"xi-api-key": settings.ELEVENLABS_API_KEY},
            max_size=10 * 1024 * 1024,
        ) as stt_ws:

            async def browser_to_elevenlabs():
                nonlocal current_tts_task, current_turn_id
                while True:
                    msg = await websocket.receive_json()

                    if msg.get("type") == "audio_chunk":
                        audio_base64 = msg["audio_base64"]

                        await stt_ws.send(
                            json.dumps(
                                {
                                    "message_type": "input_audio_chunk",
                                    "audio_base_64": audio_base64,
                                    "sample_rate": settings.ELEVENLABS_STT_SAMPLE_RATE,
                                }
                            )
                        )
                    elif msg.get("type") == "interrupt":
                        if current_tts_task and not current_tts_task.done():
                            current_tts_task.cancel()

                            with contextlib.suppress(asyncio.CancelledError):
                                await current_tts_task

                        await websocket.send_json(
                            {
                                "type": "interrupt_ack",
                                "turn_id": current_turn_id,
                            }
                        )

                        current_tts_task = None
                        current_turn_id = None
                    elif msg.get("type") == "commit":
                        await stt_ws.send(
                            json.dumps(
                                {
                                    "message_type": "input_audio_chunk",
                                    "audio_base_64": "",
                                    "commit": True,
                                    "sample_rate": settings.ELEVENLABS_STT_SAMPLE_RATE,
                                }
                            )
                        )

                    elif msg.get("type") == "close":
                        if current_tts_task and not current_tts_task.done():
                            current_tts_task.cancel()

                            with contextlib.suppress(asyncio.CancelledError):
                                await current_tts_task

                        await websocket.close()
                        break

            async def elevenlabs_to_browser():
                nonlocal current_tts_task, current_turn_id
                while True:
                    try:
                        raw = await stt_ws.recv()
                    except websockets.exceptions.ConnectionClosed:
                        # ElevenLabs closed the STT socket cleanly — nothing to do
                        return
                    event = json.loads(raw)
                    message_type = event.get("message_type")

                    if message_type == "session_started":
                        await websocket.send_json(
                            {
                                "type": "stt_session_started",
                                "config": event.get("config", {}),
                            }
                        )

                    elif message_type == "partial_transcript":
                        await websocket.send_json(
                            {
                                "type": "user_partial_transcript",
                                "text": event.get("text", ""),
                            }
                        )

                    elif message_type == "committed_transcript":
                        transcript = event.get("text", "").strip()
                        if not transcript:
                            continue

                        await websocket.send_json(
                            {
                                "type": "user_committed_transcript",
                                "text": transcript,
                            }
                        )

                        matches = kb_search(
                            query=transcript,
                            namespace=namespace,
                            top_k=settings.KB_TOP_K,
                        )

                        context = [
                            {
                                "chunk_id": m["chunk_id"],
                                "title": m["title"],
                                "text": m["text"],
                                "score": m["score"],
                            }
                            for m in matches
                        ]

                        answer = await llm_client.answer(
                            system_prompt=(
                                "You are a concise voice assistant. "
                                "Use the provided knowledge base context when possible. "
                                "If the context is insufficient, say what is missing. "
                                "Keep answers short because they will be spoken aloud."
                            ),
                            question=transcript,
                            context_chunks=context,
                        )

                        await websocket.send_json(
                            {
                                "type": "sources",
                                "sources": context,
                            }
                        )

                        if current_tts_task and not current_tts_task.done():
                            current_tts_task.cancel()

                            with contextlib.suppress(asyncio.CancelledError):
                                await current_tts_task

                        current_turn_id = str(uuid.uuid4())

                        current_tts_task = asyncio.create_task(
                            _send_answer_audio(
                                websocket=websocket,
                                answer=answer,
                                voice_id=voice_id,
                                turn_id=current_turn_id,
                                language_code=None,
                            )
                        )

                    elif message_type and "error" in message_type:
                        await websocket.send_json(
                            {
                                "type": "stt_error",
                                "event": event,
                            }
                        )

            await asyncio.gather(
                browser_to_elevenlabs(),
                elevenlabs_to_browser(),
            )

    except WebSocketDisconnect:
        if current_tts_task and not current_tts_task.done():
            current_tts_task.cancel()
        return

    except Exception as exc:
        if current_tts_task and not current_tts_task.done():
            current_tts_task.cancel()

        with contextlib.suppress(Exception):
            await websocket.send_json(
                {
                    "type": "error",
                    "message": str(exc),
                }
            )
            await websocket.close()