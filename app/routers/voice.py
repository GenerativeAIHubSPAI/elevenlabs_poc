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

@router.websocket("/voice-stream")
async def voice_stream(websocket: WebSocket):
    await websocket.accept()

    voice_id = (
        websocket.query_params.get("voice_id")
        or settings.ELEVENLABS_DEFAULT_VOICE_ID
        or settings.ELEVENLABS_VOICE_ID
    )
    namespace = websocket.query_params.get("namespace") or settings.KB_DEFAULT_NAMESPACE
    language_code = websocket.query_params.get("language_code")

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
                    raw = await stt_ws.recv()
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

        await websocket.send_json(
            {
                "type": "error",
                "message": str(exc),
            }
        )
        await websocket.close()