# Voice Assistant — ElevenLabs + OpenAI

Voice assistant proof of concept using FastAPI, ElevenLabs STT/TTS, OpenAI Responses API, semantic knowledge-base retrieval, PDF ingestion, session-aware chat, and realtime voice streaming.

The project is structured so backend, frontend, and Docker/runtime documentation are separated into focused guides.

## Documentation

| Document | Purpose |
|----------|---------|
| [`docs/BACKEND.md`](docs/BACKEND.md) | Backend setup, environment variables, endpoints, KB ingestion, LLM integration, memory, and WebSocket backend behavior |
| [`docs/FRONTEND.md`](docs/FRONTEND.md) | Frontend structure, session lifecycle, API usage, WebSocket events, audio format, and interruption handling |
| [`docs/DOCKER.md`](docs/DOCKER.md) | Docker Compose, Dev Container, ports, logs, rebuilds, and troubleshooting |

## Architecture Overview

```text
Frontend
  ├── Text chat
  ├── File upload
  ├── Voice controls
  └── WebSocket audio streaming

Backend FastAPI
  ├── ElevenLabs STT/TTS
  ├── Knowledge-base ingestion and retrieval
  ├── PDF text extraction
  ├── OpenAI Responses API
  ├── Session memory
  ├── Single-turn voice pipeline
  └── Realtime voice WebSocket
```

## Main Capabilities

- Speech-to-text transcription with ElevenLabs.
- Text-to-speech synthesis with ElevenLabs.
- Streaming TTS responses.
- PDF and text ingestion into a knowledge base.
- Semantic search over knowledge-base chunks.
- Chat responses grounded in KB context.
- Session-aware follow-up questions using `user_id` and `session_id`.
- Single-turn voice endpoint: audio → STT → KB → LLM → TTS.
- Realtime WebSocket voice conversation.
- Assistant interruption support during streaming voice responses.

## Quick Start

Create a `.env` file in the project root. See [`docs/BACKEND.md`](docs/BACKEND.md) for the full list of required variables.

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the backend:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open the API docs:

```text
http://localhost:8000/docs
```

## Docker Start

```bash
docker compose up --build
```

See [`docs/DOCKER.md`](docs/DOCKER.md) for rebuild, logging, Dev Container, and troubleshooting instructions.

## Project Structure

```text
.
├── main.py
├── requirements.txt
├── docker-compose.yml
├── Dockerfile.backend
├── .env
│
├── app/
│   ├── clients/
│   ├── core/
│   ├── routers/
│   ├── schemas/
│   └── services/
│
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.js
│
├── scripts/
│   └── test_voice_stream.py
│
└── docs/
    ├── BACKEND.md
    ├── FRONTEND.md
    └── DOCKER.md
```

## Important Notes

- Do not commit `.env` or API keys.
- Knowledge-base storage is currently in memory.
- Conversation/session memory is currently in memory.
- OCR for scanned PDFs is not implemented.
- Authentication and production user identity are not implemented yet.
- Before production, move KB, embeddings, and session memory to persistent storage.

## Development Status

This is a proof of concept intended for rapid iteration and validation of the voice assistant architecture.

Recommended next production steps:

1. Add persistent storage for KB chunks and embeddings.
2. Add persistent session memory.
3. Add authentication and derive `user_id` from the authenticated identity.
4. Add structured logging and metrics.
5. Add automated tests for API endpoints and WebSocket flows.
6. Add OCR support if scanned PDFs are required.
7. Harden secrets management and deployment configuration.
