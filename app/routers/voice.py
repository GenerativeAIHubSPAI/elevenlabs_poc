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
import contextlib
import json
import uuid
from urllib.parse import urlencode

import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.core.system_prompts import resolve_system_prompt
from app.services.elevenlabs import ElevenLabsClient
from app.services.kb import kb_search
from app.services.llm import llm_client
from app.services.memory import add_turn, format_history

router = APIRouter()
settings = get_settings()
eleven = ElevenLabsClient()

EARLY_TURN_COUNT = 3
EARLY_RESPONSE_DELAY_SECONDS = 0.0
EARLY_TRANSCRIPT_MERGE_SECONDS = 0.15
NORMAL_TRANSCRIPT_MERGE_SECONDS = 1.0
INCOMPLETE_TRANSCRIPT_MERGE_SECONDS = 1.6
MEMORY_MAX_TURNS = 16

# ─── Voice ID matrix ──────────────────────────────────────────────────────────
# Key: (language_code, gender, tone) -> ElevenLabs voice_id
VOICE_MAP: dict[tuple[str, str, str], str] = {
    # Spanish
    ("es", "hombre", "energico"): "eEyWolF7iBpMA65GbtAm",
    ("es", "hombre", "cercano"): "w8u1dIxiWVelUtUQg1MB",
    ("es", "hombre", "serio"): "m8dLaNJTf2Faapk51VKn",
    ("es", "mujer", "energico"): "uQw4jpKzMLrZuo0RLPS9",
    ("es", "mujer", "cercano"): "1eHrpOW5l98cxiSRjbzJ",
    ("es", "mujer", "serio"): "kwNLkNjbQHMw9YUFZsHI",

    # English
    ("en", "hombre", "energico"): "s0XGIcqmceN2l7kjsqoZ",
    ("en", "hombre", "cercano"): "TWutjvRaJqAX89preB4e",
    ("en", "hombre", "serio"): "xKhbyU7E3bC6T89Kn26c",
    ("en", "mujer", "energico"): "8vf2Pg7VZD0Piv8GA8v9",
    ("en", "mujer", "cercano"): "2vbhUP8zyKg4dEZaTWGn",
    ("en", "mujer", "serio"): "gJx1vCzNCD1EQHT212Ls",
}


def _resolve_voice_id(
    explicit_voice_id: str | None,
    language_code: str | None,
    gender: str | None,
    tone: str | None,
) -> str | None:
    """Resolve the ElevenLabs voice ID from explicit input, UI config, or settings."""
    if explicit_voice_id:
        return explicit_voice_id

    if language_code and gender and tone:
        key = (language_code.lower(), gender.lower(), tone.lower())
        mapped = VOICE_MAP.get(key)

        if mapped:
            return mapped

    return settings.ELEVENLABS_DEFAULT_VOICE_ID or settings.ELEVENLABS_VOICE_ID


def _build_realtime_stt_url(language_code: str | None = None) -> str:
    """Build the ElevenLabs realtime STT WebSocket URL."""
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


def _clean_display_name(user_name: str | None) -> str:
    """Return a safe display name for prompt use."""
    value = (user_name or "Guest user").strip()
    value = value.replace("\n", " ").replace("\r", " ")
    value = " ".join(value.split())

    return value[:80] or "Guest user"


def _clean_auth_mode(auth_mode: str | None) -> str:
    """Normalize auth mode."""
    value = (auth_mode or "guest").strip().lower()

    if value not in {"guest", "authenticated"}:
        return "guest"

    return value

def _extract_name_from_transcript(transcript: str) -> str | None:
    """Extract a simple user name from common introduction phrases."""
    text = transcript.strip()
    lowered = text.lower()

    prefixes = [
        "my name is ",
        "i am ",
        "i'm ",
        "call me ",
        "me llamo ",
        "soy ",
        "mi nombre es ",
    ]

    for prefix in prefixes:
        if lowered.startswith(prefix):
            name = text[len(prefix):].strip(" .,!?:;")
            return name[:80] if name else None

    return None

def _looks_like_plain_name(transcript: str) -> bool:
    """Return True when the transcript is probably just a short display name."""
    text = transcript.strip(" .,!?:;")

    if not text:
        return False

    words = text.split()

    if len(words) > 3:
        return False

    blocked = {
        "hello",
        "hi",
        "hey",
        "hola",
        "yes",
        "no",
        "thanks",
        "thank you",
        "ok",
        "okay",
        "what",
        "why",
        "how",
        "que",
        "qué",
        "cuando",
        "cuándo",
        "como",
        "cómo",
        "gracias",
        "sí",
        "si",
    }

    return text.lower() not in blocked


def _looks_incomplete(transcript: str) -> bool:
    """Return True when a committed transcript probably continues."""
    text = transcript.strip().lower()

    if not text:
        return False

    if text.endswith(("-", "—", "...", "…", ",", ":")):
        return True

    last_word = text.strip(" .,!?:;").split()[-1]

    return last_word in {
        "a",
        "al",
        "and",
        "because",
        "but",
        "con",
        "de",
        "del",
        "el",
        "en",
        "for",
        "la",
        "las",
        "los",
        "o",
        "para",
        "pero",
        "porque",
        "que",
        "the",
        "to",
        "un",
        "una",
        "y",
    }


def _transcript_merge_wait_seconds(
    completed_turns: int,
    transcript: str,
) -> float:
    """Return the quiet period required before processing a transcript."""
    if _looks_incomplete(transcript):
        return INCOMPLETE_TRANSCRIPT_MERGE_SECONDS

    if completed_turns < EARLY_TURN_COUNT:
        return EARLY_TRANSCRIPT_MERGE_SECONDS

    return NORMAL_TRANSCRIPT_MERGE_SECONDS


def _response_delay_seconds(completed_turns: int) -> float:
    """Use immediate replies for the first turns and normal pacing afterwards."""
    if completed_turns < EARLY_TURN_COUNT:
        return EARLY_RESPONSE_DELAY_SECONDS

    return max(0.0, settings.VOICE_RESPONSE_DELAY_SECONDS)



def _build_user_aware_system_prompt(
    namespace: str,
    user_id: str,
    display_name: str,
    auth_mode: str,
) -> str:
    """Add identity, continuity, and process rules to the business prompt."""
    base_prompt = resolve_system_prompt(namespace=namespace)

    normalized_name = display_name.strip().lower()

    is_unknown_user = normalized_name in {
        "guest user",
        "portal user",
        "guest",
        "anonymous",
    }

    if is_unknown_user:
        name_instruction = (
            "El nombre del usuario todavía no se conoce. "
            "Pregúntalo una sola vez, de forma breve y natural. "
            "Cuando el usuario lo proporcione, no vuelvas a preguntarlo."
        )
    else:
        name_instruction = (
            "El nombre del usuario ya se conoce. "
            "Úsalo solo cuando resulte natural o útil. "
            "No lo repitas en cada respuesta."
        )

    session_rules = """
                    Reglas obligatorias para esta conversación de voz:

                    - Mantén internamente una lista de los datos ya recopilados y de los datos
                    todavía pendientes.
                    - No muestres esa lista interna al usuario salvo que solicite un resumen.
                    - Revisa el mensaje actual y el historial antes de formular una pregunta.
                    - Nunca vuelvas a pedir un dato que el usuario ya haya proporcionado.
                    - Esto incluye nombre, documento de identidad, número de póliza, teléfono,
                    dirección, fechas, cantidades, disponibilidad, destino, propiedad y cualquier
                    otro dato relevante para el proceso.
                    - Si el usuario proporciona varios datos juntos, registra todos y avanza a los
                    siguientes requisitos pendientes.
                    - No solicites confirmación de un dato salvo que sea ambiguo, incompleto o
                    contradiga información anterior.
                    - Formula como máximo dos preguntas relacionadas en una misma respuesta.
                    - Solicita como máximo dos datos pendientes por turno.
                    - No expliques todos los pasos restantes de un proceso de una sola vez.
                    - Presenta únicamente el siguiente paso o los dos siguientes y espera la
                    respuesta del usuario.
                    - Continúa siempre desde el punto actual del proceso; no regreses a preguntas
                    generales cuando el producto, incidencia o solicitud ya estén definidos.
                    - Interpreta respuestas breves, pronombres y referencias utilizando el historial.
                    - Mantén las respuestas normalmente por debajo de 80 palabras.
                    - Si el usuario solicita una explicación extensa, divídela en partes breves.
                    - No repitas el nombre del usuario en cada mensaje.
                    - Si un dato pertenece a un sistema interno, no pidas al usuario que lo confirme.
                    Indica que debe comprobarse internamente, pero no inventes el resultado ni
                    afirmes que ya se ha comprobado si el sistema no lo confirma.
                """

    return (
        f"{base_prompt}\n\n"
        "Contexto de identidad de la sesión:\n"
        f"- user_id: {user_id}\n"
        f"- auth_mode: {auth_mode}\n"
        f"- display_name: {display_name}\n\n"
        f"{name_instruction}\n"
        "Los nombres de usuarios invitados o del portal son solo nombres "
        "mostrados y no representan una identidad verificada.\n\n"
        f"{session_rules.strip()}"
    )



async def _send_answer_audio(
    websocket: WebSocket,
    answer: str,
    voice_id: str,
    turn_id: str,
    language_code: str | None = None,
) -> None:
    """Send assistant text and streamed TTS audio to the browser."""
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
        with contextlib.suppress(Exception):
            await websocket.send_json(
                {
                    "type": "error",
                    "turn_id": turn_id,
                    "message": f"TTS error: {exc}",
                }
            )


@router.websocket("/voice-stream")
async def voice_stream(websocket: WebSocket) -> None:
    """Realtime browser audio -> STT -> KB -> LLM -> TTS WebSocket route."""
    await websocket.accept()

    language_code = websocket.query_params.get("language_code")
    gender = websocket.query_params.get("gender")
    tone = websocket.query_params.get("tone")
    namespace = websocket.query_params.get("namespace") or settings.KB_DEFAULT_NAMESPACE

    user_id = websocket.query_params.get("user_id") or "guest:anonymous"
    user_name = websocket.query_params.get("user_name") or "Guest user"
    session_id = websocket.query_params.get("session_id") or str(uuid.uuid4())
    conversation_key = f"{user_id}:{session_id}"
    auth_mode = _clean_auth_mode(websocket.query_params.get("auth_mode"))
    token = websocket.query_params.get("token")

    # TODO(@auth): verify Cognito token when auth_mode == "authenticated".
    # For now, guest mode is supported and authenticated mode is accepted but not verified.
    _ = token

    display_name = _clean_display_name(user_name)

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
                "message": (
                    "Missing voice_id. Pass ?voice_id=... or set "
                    "ELEVENLABS_DEFAULT_VOICE_ID."
                ),
            }
        )
        await websocket.close()
        return

    stt_url = _build_realtime_stt_url(language_code=language_code)

    current_tts_task: asyncio.Task | None = None
    current_turn_id: str | None = None
    known_display_name = display_name
    has_asked_name = False
    assistant_turn_count = 0
    transcript_queue: asyncio.Queue[str] = asyncio.Queue()

    try:
        async with websockets.connect(
            stt_url,
            additional_headers={"xi-api-key": settings.ELEVENLABS_API_KEY},
            max_size=10 * 1024 * 1024,
        ) as stt_ws:

            async def browser_to_elevenlabs() -> None:
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

            async def collect_transcript(first_fragment: str) -> str:
                """Merge committed STT fragments until the caller has been quiet."""
                fragments = [first_fragment]

                while True:
                    combined = " ".join(fragment for fragment in fragments if fragment).strip()
                    wait_seconds = _transcript_merge_wait_seconds(
                        completed_turns=assistant_turn_count,
                        transcript=combined,
                    )

                    try:
                        next_fragment = await asyncio.wait_for(
                            transcript_queue.get(),
                            timeout=wait_seconds,
                        )
                    except asyncio.TimeoutError:
                        return combined

                    if next_fragment:
                        fragments.append(next_fragment)

            def drain_transcript_queue() -> list[str]:
                """Drain transcript fragments already waiting in the queue."""
                fragments: list[str] = []

                while True:
                    try:
                        fragment = transcript_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        return fragments

                    if fragment:
                        fragments.append(fragment)

            async def committed_transcript_worker() -> None:
                """Merge user fragments and process one stable conversational turn."""
                nonlocal current_tts_task, current_turn_id
                nonlocal known_display_name, has_asked_name, assistant_turn_count

                while True:
                    first_fragment = await transcript_queue.get()
                    transcript = await collect_transcript(first_fragment)

                    while transcript:
                        is_unknown_user = known_display_name.strip().lower() in {
                            "guest user",
                            "portal user",
                            "guest",
                            "anonymous",
                        }

                        extracted_name = _extract_name_from_transcript(transcript)

                        if (
                            not extracted_name
                            and has_asked_name
                            and is_unknown_user
                            and _looks_like_plain_name(transcript)
                        ):
                            extracted_name = transcript

                        effective_display_name = (
                            _clean_display_name(extracted_name)
                            if extracted_name
                            else known_display_name
                        )

                        conversation_history = format_history(
                            conversation_key=conversation_key,
                            max_turns=MEMORY_MAX_TURNS,
                        )

                        retrieval_query = (
                            f"{conversation_history}\n\nCurrent question: {transcript}"
                            if conversation_history
                            else transcript
                        )

                        matches = kb_search(
                            query=retrieval_query,
                            namespace=namespace,
                            top_k=settings.KB_TOP_K,
                        )

                        context = [
                            {
                                "chunk_id": match["chunk_id"],
                                "title": match["title"],
                                "text": match["text"],
                                "score": match["score"],
                            }
                            for match in matches
                        ]

                        system_prompt = _build_user_aware_system_prompt(
                            namespace=namespace,
                            user_id=user_id,
                            display_name=effective_display_name,
                            auth_mode=auth_mode,
                        )

                        answer = await llm_client.answer(
                            system_prompt=system_prompt,
                            question=transcript,
                            context_chunks=context,
                            conversation_history=conversation_history,
                        )

                        delay_seconds = _response_delay_seconds(assistant_turn_count)

                        if delay_seconds > 0:
                            await asyncio.sleep(delay_seconds)

                        continuation_fragments = drain_transcript_queue()

                        if continuation_fragments:
                            combined = " ".join(
                                [transcript, *continuation_fragments]
                            ).strip()
                            transcript = await collect_transcript(combined)
                            continue

                        if extracted_name:
                            known_display_name = effective_display_name

                        if is_unknown_user and not extracted_name:
                            has_asked_name = True

                        await websocket.send_json(
                            {
                                "type": "user_committed_transcript",
                                "text": transcript,
                            }
                        )

                        await websocket.send_json(
                            {
                                "type": "sources",
                                "sources": context,
                            }
                        )

                        add_turn(
                            conversation_key=conversation_key,
                            role="user",
                            content=transcript,
                        )
                        add_turn(
                            conversation_key=conversation_key,
                            role="assistant",
                            content=answer,
                            metadata={
                                "sources": context,
                                "namespace": namespace,
                            },
                        )

                        if current_tts_task and not current_tts_task.done():
                            current_tts_task.cancel()

                            with contextlib.suppress(asyncio.CancelledError):
                                await current_tts_task

                        current_turn_id = str(uuid.uuid4())
                        assistant_turn_count += 1

                        current_tts_task = asyncio.create_task(
                            _send_answer_audio(
                                websocket=websocket,
                                answer=answer,
                                voice_id=voice_id,
                                turn_id=current_turn_id,
                                language_code=None,
                            )
                        )
                        break

            async def elevenlabs_to_browser() -> None:
                nonlocal current_tts_task, current_turn_id, known_display_name, has_asked_name

                while True:
                    try:
                        raw = await stt_ws.recv()
                    except websockets.exceptions.ConnectionClosed:
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
                        partial_text = event.get("text", "")

                        if (
                            partial_text.strip()
                            and current_tts_task
                            and not current_tts_task.done()
                        ):
                            current_tts_task.cancel()

                            with contextlib.suppress(asyncio.CancelledError):
                                await current_tts_task

                            current_tts_task = None
                            current_turn_id = None

                        await websocket.send_json(
                            {
                                "type": "user_partial_transcript",
                                "text": partial_text,
                            }
                        )

                    elif message_type == "committed_transcript":
                        transcript = event.get("text", "").strip()

                        if not transcript:
                            continue

                        if current_tts_task and not current_tts_task.done():
                            current_tts_task.cancel()

                            with contextlib.suppress(asyncio.CancelledError):
                                await current_tts_task

                            current_tts_task = None
                            current_turn_id = None

                        await transcript_queue.put(transcript)

                    elif message_type and "error" in message_type:
                        await websocket.send_json(
                            {
                                "type": "stt_error",
                                "event": event,
                            }
                        )

            transcript_worker_task = asyncio.create_task(
                committed_transcript_worker()
            )

            try:
                await asyncio.gather(
                    browser_to_elevenlabs(),
                    elevenlabs_to_browser(),
                )
            finally:
                transcript_worker_task.cancel()

                with contextlib.suppress(asyncio.CancelledError):
                    await transcript_worker_task

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