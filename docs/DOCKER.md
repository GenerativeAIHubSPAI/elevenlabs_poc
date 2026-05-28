# Docker and Dev Container Guide

This document describes how to run the voice assistant project with Docker Compose or a VS Code Dev Container.

## Requirements

- Docker Desktop running.
- A valid `.env` file in the project root.
- Optional: VS Code with the Dev Containers extension.

## Environment File

Docker Compose expects a `.env` file in the project root.

Do not commit this file.

Minimum backend variables:

```env
ELEVENLABS_API_KEY=your_elevenlabs_api_key
ELEVENLABS_VOICE_ID=your_default_voice_id
ELEVENLABS_DEFAULT_VOICE_ID=your_default_voice_id

LLM_API_KEY=your_openai_api_key
LLM_BASE_URL=https://api.openai.com/v1/responses
LLM_MODEL=gpt-4.1-mini
```

Optional embeddings variables:

```env
AWS_REGION=eu-west-3
AWS_BEARER_TOKEN_BEDROCK=your_bedrock_bearer_token
BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0
BEDROCK_EMBEDDING_DIMENSIONS=1024
```

## Docker Compose

Start the stack:

```bash
docker compose up --build
```

Stop the stack:

```bash
docker compose down
```

Rebuild without cache:

```bash
docker compose build --no-cache
docker compose up
```

Full clean restart:

```bash
docker compose down --volumes --remove-orphans
docker compose build --no-cache
docker compose up
```

## Ports

| Service | URL |
|---------|-----|
| Backend | http://localhost:8000 |
| API docs | http://localhost:8000/docs |

If a frontend service is included in `docker-compose.yml`, it will usually be exposed on:

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |

## Logs

All services:

```bash
docker compose logs -f
```

Backend only:

```bash
docker compose logs -f backend
```

Last logs:

```bash
docker compose logs --tail=100 backend
```

## Execute Commands Inside Container

Open a shell in the backend container:

```bash
docker compose exec backend bash
```

Run Python commands:

```bash
docker compose exec backend python --version
```

Run tests or scripts:

```bash
docker compose exec backend python scripts/test_voice_stream.py --help
```

## Dev Container

If the project includes a `.devcontainer` folder, the recommended workflow is:

1. Open the project in VS Code.
2. Run `Dev Containers: Reopen in Container`.
3. Wait for dependencies to install.
4. Start the backend inside the container:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

VS Code should forward port `8000` automatically.

## Common Issues

### Port already in use

Check what is using port `8000`.

Windows PowerShell:

```powershell
netstat -ano | findstr :8000
```

Stop the conflicting process or change the exposed port.

### `.env` variables not loaded

Check `.env` syntax. Every non-empty line must be either:

```env
KEY=value
```

or:

```env
# comment
```

Invalid example:

```env
BEDROCK_EMBEDDING_MODEL_ID: str = "amazon.titan-embed-text-v2:0"
```

Valid example:

```env
BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0
```

### Backend cannot reach provider

Verify:

- API key is valid.
- Provider endpoint is correct.
- Model name exists and is enabled.
- Container has outbound internet access.
- `.env` is mounted or loaded by Docker Compose.

### Uvicorn reload loops

This can happen if generated files or caches are watched. Exclude unnecessary paths where possible and avoid writing temporary files into watched source directories.

### WebSocket audio test fails

Ensure the audio is raw PCM:

```text
16 kHz
mono
16-bit signed little endian
```

Convert with FFmpeg:

```bash
ffmpeg -i ./output/input.mp3 -f s16le -acodec pcm_s16le -ac 1 -ar 16000 sample_16khz_mono.pcm
```

## Production Notes

Before production deployment:

- Do not use `.env` files with plain secrets.
- Use a secrets manager or platform-managed environment variables.
- Use persistent storage for KB chunks, embeddings, and session memory.
- Add authentication and derive `user_id` from authenticated identity.
- Configure structured logging.
- Disable debug endpoints or protect them.
- Add health checks to Docker Compose or the deployment platform.
- Use a production ASGI server setup appropriate for the hosting environment.
