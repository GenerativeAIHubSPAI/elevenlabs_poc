# Voice Assistant — ElevenLabs + AWS Bedrock / Azure OpenAI

Asistente de voz conversacional con detección de actividad de voz (VAD) en el navegador, transcripción en tiempo real (STT), respuesta de LLM con base de conocimiento (RAG) y síntesis de voz (TTS) mediante la API de ElevenLabs.

## Arquitectura

```
Frontend (React + Vite)          Backend (FastAPI + Uvicorn)
┌─────────────────────┐          ┌──────────────────────────┐
│  VAD (silero-vad)   │◄─WS/HTTP►│  /voice/turn             │
│  Grabación de audio │          │  /stt/transcribe          │
│  Reproducción TTS   │          │  /tts/stream              │
└─────────────────────┘          │  /chat/ask                │
                                 │  /kb/ingest-text          │
                                 │  /kb/search               │
                                 └──────────────────────────┘
                                          │
                          ┌───────────────┼───────────────┐
                     ElevenLabs API   AWS Bedrock    Azure OpenAI
                     (STT / TTS)      (Nova Pro)    (GPT via Responses API)
```

## Requisitos previos

- Python 3.11+
- Node.js 20+ (ver [.nvmrc](.nvmrc))
- Cuenta en [ElevenLabs](https://elevenlabs.io) con API key
- **LLM provider** (elige uno):
  - AWS con acceso a Bedrock (modelo `amazon.nova-pro-v1:0`)
  - Azure OpenAI / OpenAI con acceso a la Responses API

## Variables de entorno

Crea un archivo `.env` en la raíz del proyecto. Estas son las variables disponibles:

```env
# --- ElevenLabs (obligatorio) ---
ELEVENLABS_API_KEY=sk-...
ELEVENLABS_VOICE_ID=<voice-id>           # voz por defecto para TTS
ELEVENLABS_AGENT_ID=<agent-id>           # opcional, para modo agente

# --- Proveedor LLM: "bedrock" (por defecto) o "openai" ---
LLM_PROVIDER=bedrock

# --- AWS Bedrock (si LLM_PROVIDER=bedrock) ---
AWS_REGION=eu-west-1
AWS_BEARER_TOKEN_BEDROCK=<token>         # o usa credenciales AWS estándar (~/.aws/credentials)
BEDROCK_MODEL_ID=amazon.nova-pro-v1:0

# --- Azure / OpenAI (si LLM_PROVIDER=openai) ---
LLM_API_KEY=<api-key>
LLM_BASE_URL=https://<recurso>.cognitiveservices.azure.com/openai/responses?api-version=2025-04-01-preview
LLM_MODEL=gpt-4o-mini

# --- Opcionales ---
ELEVENLABS_TTS_MODEL=eleven_flash_v2_5
ELEVENLABS_STT_MODEL=scribe_v2
BEDROCK_MAX_TOKENS=700
LLM_MAX_OUTPUT_TOKENS=700
KB_TOP_K=4
```

## Lanzar con Dev Container (recomendado para desarrollo y debug)

El Dev Container levanta un único contenedor con Python 3.13 + Node.js 20 y monta el proyecto en vivo, por lo que cualquier cambio en el código se refleja al instante sin reconstruir la imagen.

### Requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) corriendo
- VS Code con la extensión [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

### Pasos

1. Abre la carpeta del proyecto en VS Code.
2. Cuando aparezca la notificación _"Reopen in Container"_, acéptala.  
   O bien: `Cmd+Shift+P` → **Dev Containers: Reopen in Container**.
3. VS Code construye la imagen (solo la primera vez) e instala automáticamente las dependencias Python y Node (`postCreateCommand`).
4. Abre dos terminales integradas dentro del contenedor y arranca cada servicio:

**Terminal 1 — Backend** (con recarga automática al guardar):
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — Frontend** (con HMR):
```bash
cd frontend && npm run dev
```

VS Code redirige automáticamente los puertos 3000 y 8000 al host y muestra una notificación para abrirlos en el navegador.

---

## Lanzar en local (desarrollo)

### 1. Backend

```bash
# Crear y activar entorno virtual
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Arrancar el servidor
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

El backend queda disponible en `http://localhost:8000`.  
Documentación interactiva: `http://localhost:8000/docs`

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

La aplicación abre en `http://localhost:3000`.

## Lanzar con Docker Compose

La forma más sencilla de arrancar todo el stack de una vez:

```bash
# Asegúrate de tener el archivo .env en la raíz
docker compose up --build
```

| Servicio  | URL                    |
|-----------|------------------------|
| Frontend  | http://localhost:3000  |
| Backend   | http://localhost:8000  |
| API docs  | http://localhost:8000/docs |

Para detener:

```bash
docker compose down
```

## Estructura del proyecto

```
.
├── main.py                  # Entrada FastAPI
├── requirements.txt
├── docker-compose.yml
├── Dockerfile.backend
├── .env                     # Variables de entorno (no subir a git)
│
├── app/
│   ├── core/
│   │   └── config.py        # Settings (Pydantic)
│   ├── routers/
│   │   ├── voice_turn.py    # Endpoint principal: STT → LLM → TTS en un turno
│   │   ├── stt.py           # Transcripción de audio
│   │   ├── tts.py           # Síntesis de voz
│   │   ├── chat.py          # Chat con historial
│   │   ├── kb.py            # Base de conocimiento (RAG)
│   │   ├── voice.py         # Streaming de voz
│   │   └── health.py
│   ├── services/
│   │   └── llm.py           # Clientes LLM (Bedrock / Azure OpenAI)
│   └── clients/
│       ├── bedrock.py       # Cliente embeddings Bedrock
│       └── openai.py
│
└── frontend/
    ├── src/
    │   ├── App.jsx           # Componente principal
    │   └── main.jsx
    ├── package.json
    └── vite.config.js
```

## Endpoints principales

| Método | Ruta                  | Descripción                                      |
|--------|-----------------------|--------------------------------------------------|
| POST   | `/voice/turn`         | Turno completo: audio → texto → respuesta → TTS  |
| POST   | `/stt/transcribe`     | Transcripción de audio a texto                   |
| POST   | `/tts/stream`         | Síntesis de voz en streaming                     |
| POST   | `/chat/ask`           | Pregunta al LLM con contexto KB                  |
| POST   | `/kb/ingest-text`     | Ingestar texto en la base de conocimiento        |
| POST   | `/kb/search`          | Búsqueda semántica en la KB                      |
| GET    | `/health`             | Health check                                     |

## Notas

- El frontend usa [silero-vad](https://github.com/snakers4/silero-vad) vía WebAssembly para detectar cuándo el usuario termina de hablar, sin necesidad de pulsar ningún botón.
- El idioma de respuesta por defecto es **español**; el usuario puede cambiarlo explícitamente en la conversación.
- Los archivos de audio generados se guardan en la carpeta `output/`.
