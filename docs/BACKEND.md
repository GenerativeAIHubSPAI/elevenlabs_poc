# Backend Guide

FastAPI backend for the ElevenLabs voice assistant proof of concept. The backend provides speech-to-text, text-to-speech, knowledge-base ingestion and retrieval, LLM-grounded answers, session-aware chat, single-turn voice orchestration, and realtime WebSocket voice streaming.

## Backend Responsibilities

The backend owns:

- API routing with FastAPI.
- ElevenLabs STT and TTS integration.
- Knowledge-base ingestion from text and PDFs.
- Semantic retrieval over KB chunks.
- LLM answer generation through the OpenAI Responses API.
- In-memory session history using `user_id` and `session_id`.
- Single-turn voice orchestration.
- Realtime voice WebSocket orchestration.
- Provider error handling.

The backend does not own frontend microphone capture, browser VAD, UI state, or audio playback.

## Architecture

```text
FastAPI Backend
│
├── /health
├── /models
├── /voices
├── /meta
│
├── /stt/transcribe
│     └── ElevenLabs Speech-to-Text
│
├── /tts/speak
├── /tts/stream
│     └── ElevenLabs Text-to-Speech
│
├── /kb/ingest-text
├── /kb/ingest-pdf
├── /kb/search
│     └── Semantic Knowledge Base
│
├── /chat/ask
│     ├── user_id + session_id memory
│     ├── KB retrieval
│     └── OpenAI Responses API
│
├── /voice/turn
│     └── Audio → STT → KB → LLM → TTS
│
└── /chat/voice-stream
      └── Realtime WebSocket voice pipeline
```

## Project Structure

```text
.
├── main.py                         # FastAPI application entry point
├── requirements.txt                # Python dependencies
├── docker-compose.yml              # Optional local container orchestration
├── Dockerfile.backend              # Backend container image definition
├── .env                            # Environment variables; do not commit
│
├── app/
│   ├── __init__.py                 # Backend package metadata
│   │
│   ├── clients/
│   │   ├── __init__.py             # Client package marker
│   │   ├── bedrock.py              # Optional Bedrock helper/client logic
│   │   └── openai.py               # Optional OpenAI-compatible helper client
│   │
│   ├── core/
│   │   ├── __init__.py             # Core package exports
│   │   └── config.py               # Pydantic settings loaded from .env
│   │
│   ├── routers/
│   │   ├── __init__.py             # Router package marker
│   │   ├── health.py               # Health checks and ElevenLabs models/voices
│   │   ├── meta.py                 # Runtime metadata for debugging
│   │   ├── stt.py                  # File-based speech-to-text endpoint
│   │   ├── tts.py                  # Text-to-speech and streaming TTS endpoints
│   │   ├── kb.py                   # Knowledge-base ingestion and search endpoints
│   │   ├── chat.py                 # Session-aware chat endpoint with KB context
│   │   ├── voice.py                # Realtime WebSocket voice pipeline
│   │   └── voice_turn.py           # Single-turn voice pipeline: STT → KB → LLM → TTS
│   │
│   ├── schemas/
│   │   ├── __init__.py             # Schema package marker
│   │   └── requests.py             # Pydantic request/response models
│   │
│   └── services/
│       ├── __init__.py             # Service package marker
│       ├── elevenlabs.py           # ElevenLabs API wrapper for STT, TTS, voices and models
│       ├── kb.py                   # In-memory semantic KB retrieval with embeddings
│       ├── llm.py                  # OpenAI Responses API client for grounded answers
│       ├── memory.py               # In-memory user/session conversation history
│       └── pdf_parser.py           # PDF text extraction with page metadata
│
└── scripts/
    └── test_voice_stream.py        # WebSocket test script for PCM audio and interruption
```

## Requirements

Recommended Python version:

```text
Python 3.11+
```

Install dependencies:

```bash
pip install -r requirements.txt
```

If `requirements.txt` is not available yet:

```bash
pip install fastapi uvicorn httpx pydantic-settings python-multipart websockets pymupdf numpy boto3
```

## Environment Variables

Create a `.env` file in the project root.

```env
# ==============================================================================
# ElevenLabs
# ==============================================================================

ELEVENLABS_API_KEY=your_elevenlabs_api_key
ELEVENLABS_BASE_URL=https://api.elevenlabs.io

ELEVENLABS_VOICE_ID=your_default_voice_id
ELEVENLABS_DEFAULT_VOICE_ID=your_default_voice_id
ELEVENLABS_AGENT_ID=optional_agent_id

ELEVENLABS_TTS_MODEL=eleven_flash_v2_5
ELEVENLABS_STT_MODEL=scribe_v2
ELEVENLABS_REALTIME_STT_MODEL=scribe_v2_realtime

ELEVENLABS_TTS_OUTPUT_FORMAT=mp3_44100_128
ELEVENLABS_STT_AUDIO_FORMAT=pcm_16000
ELEVENLABS_STT_SAMPLE_RATE=16000

# ==============================================================================
# LLM - OpenAI Responses API
# ==============================================================================

LLM_API_KEY=your_openai_api_key
LLM_BASE_URL=https://api.openai.com/v1/responses
LLM_MODEL=gpt-4.1-mini
LLM_MAX_OUTPUT_TOKENS=700
LLM_TEMPERATURE=0.2

# ==============================================================================
# Optional Bedrock Embeddings
# ==============================================================================

AWS_REGION=eu-west-3
AWS_BEARER_TOKEN_BEDROCK=your_bedrock_bearer_token
BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0
BEDROCK_EMBEDDING_DIMENSIONS=1024

# ==============================================================================
# Application
# ==============================================================================

OUTPUT_DIR=../output/
KB_DEFAULT_NAMESPACE=default
KB_CHUNK_SIZE=500
KB_CHUNK_OVERLAP=80
KB_TOP_K=7
```

Do not commit `.env`.

## Run Locally

Create and activate a virtual environment.

Windows:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the server:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend URL:

```text
http://localhost:8000
```

Swagger UI:

```text
http://localhost:8000/docs
```

## Main Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/` | Basic backend information and available routes |
| GET | `/health` | Service health check |
| GET | `/models` | Available ElevenLabs models |
| GET | `/voices` | Available ElevenLabs voices |
| GET | `/meta` | Non-sensitive runtime metadata |
| POST | `/stt/transcribe` | Audio transcription with ElevenLabs |
| POST | `/tts/speak` | Full text-to-speech response |
| POST | `/tts/stream` | Streaming text-to-speech response |
| POST | `/kb/ingest-text` | Ingest text into the knowledge base |
| POST | `/kb/ingest-pdf` | Ingest PDF into the knowledge base |
| POST | `/kb/search` | Semantic search over the knowledge base |
| POST | `/chat/ask` | Session-aware LLM answer with KB context |
| POST | `/voice/turn` | Full voice turn: audio → STT → KB → LLM → TTS |
| WS | `/chat/voice-stream` | Realtime voice conversation with interruption support |

## Knowledge Base

The KB supports text and PDF ingestion.

```text
POST /kb/ingest-text
POST /kb/ingest-pdf
POST /kb/search
```

PDF ingestion extracts text page by page and keeps metadata such as title, source name, page number, and chunk index.

Current limitations:

- KB storage is in memory.
- KB data is lost when the server restarts.
- Scanned PDFs require OCR, which is not implemented.
- Tables may be extracted imperfectly depending on PDF layout.

## Chat Sessions

`POST /chat/ask` uses `user_id` and `session_id`.

The frontend or API caller should create a new `session_id` when a new conversation starts and reuse it for follow-up questions.

Example:

```json
{
  "user_id": "user_123",
  "session_id": "demo-session-001",
  "namespace": "products",
  "question": "¿Qué tipos de gachapones tenéis?",
  "top_k": 7,
  "system_prompt": "Eres un asistente de atención al cliente. Responde en español de forma clara y útil."
}
```

Follow-up:

```json
{
  "user_id": "user_123",
  "session_id": "demo-session-001",
  "namespace": "products",
  "question": "¿Y cuánto cuesta el segundo?",
  "top_k": 7,
  "system_prompt": "Eres un asistente de atención al cliente. Responde en español de forma clara y útil."
}
```

The backend stores memory under:

```text
user_id + session_id
```

Current conversation memory is in memory and resets when the server restarts.

## Voice Turn

`POST /voice/turn` performs a complete single request flow:

```text
audio input
→ ElevenLabs STT
→ KB retrieval
→ OpenAI answer
→ ElevenLabs TTS
→ audio response
```

This is the simplest endpoint for validating the complete voice assistant flow.

## Realtime WebSocket

`WS /chat/voice-stream` supports realtime audio streaming, committed transcripts, assistant text, audio chunks, and interruption.

Client messages:

```json
{ "type": "audio_chunk", "audio_base64": "..." }
```

```json
{ "type": "commit" }
```

```json
{ "type": "interrupt" }
```

```json
{ "type": "close" }
```

Backend messages include:

```json
{ "type": "user_committed_transcript", "text": "..." }
```

```json
{ "type": "assistant_text", "turn_id": "...", "text": "..." }
```

```json
{
  "type": "assistant_audio_chunk",
  "turn_id": "...",
  "audio_base64": "...",
  "format": "mp3_44100_128"
}
```

```json
{ "type": "assistant_interrupted", "turn_id": "..." }
```

## WebSocket Test Script

Realtime STT test audio should be:

```text
PCM 16 kHz, mono, 16-bit little endian
```

Convert with FFmpeg:

```bash
ffmpeg -i ./output/input.mp3 -f s16le -acodec pcm_s16le -ac 1 -ar 16000 sample_16khz_mono.pcm
```

Run test:

```bash
python scripts/test_voice_stream.py --voice-id YOUR_VOICE_ID --audio sample_16khz_mono.pcm
```

Run interruption test:

```bash
python scripts/test_voice_stream.py --voice-id YOUR_VOICE_ID --audio sample_16khz_mono.pcm --interrupt-after 0.5
```

## Error Handling

Provider or infrastructure failures should be returned as HTTP errors, not as successful assistant answers.

Recommended behavior:

| Situation | Backend Status |
|----------|----------------|
| Missing backend config | 500 |
| Provider authentication failure | 502 |
| Provider network failure | 502 |
| Invalid request body | 422 |
| Unsupported file type | 400 |

## Development Notes

- Default answer language is Spanish.
- Audio files are written to `OUTPUT_DIR` when applicable.
- KB and session memory are currently temporary.
- Move KB, embeddings, and session history to persistent storage before production.
- Avoid logging full audio, transcripts, prompts, API keys, or provider payloads in production.
- Protect any endpoint that exposes session history or sensitive data.
