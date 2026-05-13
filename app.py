import chainlit as cl
import numpy as np
import audioop
import io
import wave
import asyncio
from uuid import uuid4
from pathlib import Path
from chainlit import user_session as session
from speech_to_text import ElevenLabsSTT, OpenAISTT
from text_to_speech import ElevenLabsTTS
from agents.base_agent import BaseAgent

LANGUAGE = "es"
SILENCE_THRESHOLD = 1500 # Adjust based on your audio level (e.g., lower for quieter audio)
SILENCE_TIMEOUT = 1700 # Seconds of silence to consider the turn finished
AUDIO_DIR = Path(__file__).resolve().parent / "audio"
GREETING_AUDIOS = {
    "es": "greeting_air_en.wav",
    "en": "greeting_air_es.wav",
}

GREETING_MESSAGES = {
    "es": "Hola, bienvenido al servicio al cliente de la aerolínea, ¿en qué puedo ayudarte?",
    "en": "Hello, welcome to the airline customer support. How can I help you?",
}

async def greeting():
    await asyncio.sleep(1)
    await play_audio(GREETING_AUDIOS[LANGUAGE])

@cl.on_audio_start
async def on_audio_start():
    # create clients
    session.set("stt_client", OpenAISTT())
    session.set("tts_client", ElevenLabsTTS())


    agent = BaseAgent(initial_agent='airline', language=LANGUAGE)
    session.set("agent", agent)

    asyncio.create_task(greeting())
    agent.add_message("assistant", GREETING_MESSAGES[LANGUAGE])

    session.set("silent_duration_ms", 0)
    session.set("is_speaking", False)
    session.set("audio_chunks", [])
    return True


@cl.on_audio_chunk
async def on_audio_chunk(chunk: cl.InputAudioChunk):
    audio_chunks = session.get("audio_chunks")

    if audio_chunks is not None:
        audio_chunk = np.frombuffer(chunk.data, dtype=np.int16)
        audio_chunks.append(audio_chunk)

    # If this is the first chunk, initialize timers and state
    if chunk.isStart:
        session.set("last_elapsed_time", chunk.elapsedTime)
        session.set("is_speaking", False)
        return

    audio_chunks = session.get("audio_chunks")
    last_elapsed_time = session.get("last_elapsed_time")
    silent_duration_ms = session.get("silent_duration_ms")
    is_speaking = session.get("is_speaking")

    # Calculate the time difference between this chunk and the previous one
    time_diff_ms = chunk.elapsedTime - last_elapsed_time
    session.set("last_elapsed_time", chunk.elapsedTime)

    # Compute the RMS (root mean square) energy of the audio chunk
    audio_energy = audioop.rms(
        chunk.data, 2
    )  # Assumes 16-bit audio (2 bytes per sample)
    if audio_energy < SILENCE_THRESHOLD:
        # Audio is considered silent
        silent_duration_ms += time_diff_ms
        session.set("silent_duration_ms", silent_duration_ms)
        if silent_duration_ms >= SILENCE_TIMEOUT and is_speaking:
            session.set("is_speaking", False)
            await process_audio()
    else:
        # Audio is not silent, reset silence timer and mark as speaking
        session.set("silent_duration_ms", 0)
        await cl.context.emitter.send_audio_interrupt()

        if not is_speaking:
            session.set("is_speaking", True)

async def play_audio(filename:str) -> None:
    wav_path = AUDIO_DIR / filename

    if not wav_path.exists():
        raise FileNotFoundError(f"No se encontró {wav_path}")

    with wave.open(str(wav_path), "rb") as wav_file:
        output_audio = wav_file.readframes(wav_file.getnframes())

    await cl.context.emitter.send_audio_chunk(cl.OutputAudioChunk(mimeType="pcm16", data=output_audio, track=str(uuid4())))

async def process_audio():
    # Get the audio buffer from the session
    if audio_chunks := session.get("audio_chunks"):
        # Concatenate all chunks
        concatenated = np.concatenate(list(audio_chunks))

        # Create an in-memory binary stream
        wav_buffer = io.BytesIO()

        # Create WAV file with proper parameters
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)  # mono
            wav_file.setsampwidth(2)  # 2 bytes per sample (16-bit)
            wav_file.setframerate(24000)  # sample rate (24kHz PCM)
            wav_file.writeframes(concatenated.tobytes())

        # Reset buffer position
        wav_buffer.seek(0)
        wav_buffer.name = "audio.wav"
        session.set("audio_chunks", [])

    stt_client = session.get("stt_client")
    transcription = stt_client.generate_transcription(wav_buffer, {"language": LANGUAGE})
    print('='*80)
    print(transcription.text)
    print('='*80)

    answer_gen = session.get("agent").generate_response(transcription.text)

    tts_client = session.get("tts_client")
    for answer in answer_gen:
        text, audio_info = answer # audio_info es o el voice_id o el idioma que se está usando para el transfer
            
        if text in ("transfer_agent", "transition"):
            await play_audio(audio_info)
            print("Played " + audio_info)
            continue   

        print('='*80)
        print(text)
        print('='*80)
        output_audio = tts_client.generate_audio_response(text, options={"voice_id": audio_info})

        # Send audio to chainlit
        await cl.context.emitter.send_audio_chunk(cl.OutputAudioChunk(mimeType="pcm16", data=output_audio, track=str(uuid4())))
