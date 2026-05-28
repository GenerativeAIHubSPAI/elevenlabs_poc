# Voice Assistant — ElevenLabs + OpenAI

Voice assistant proof of concept using FastAPI, ElevenLabs STT/TTS, OpenAI Responses API, semantic knowledge-base retrieval, and realtime voice streaming.

## Documentation

| Document | Purpose |
|----------|---------|
| [`docs/BACKEND.md`](docs/BACKEND.md) | Backend setup, environment variables, endpoints, KB ingestion, LLM integration, memory, and WebSocket backend behavior |
| [`docs/FRONTEND.md`](docs/FRONTEND.md) | Frontend structure, session lifecycle, API usage, WebSocket events, audio format, and interruption handling |
| [`docs/DOCKER.md`](docs/DOCKER.md) | Docker Compose, Dev Container, ports, logs, rebuilds, and troubleshooting |

## Quick Start

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000