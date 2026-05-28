# Frontend Guide

This document describes the frontend structure, responsibilities, and integration contract for the voice assistant backend.

The frontend is responsible for the browser-side user experience. The backend exposes HTTP and WebSocket APIs, but it does not own microphone capture, browser audio conversion, playback queues, visual state, or user interface behavior.

## Frontend Responsibilities

The frontend owns:

- User interface and conversation view.
- Microphone permission handling.
- Audio capture from the browser.
- Optional browser-side VAD.
- Audio chunk preparation for the WebSocket.
- TTS audio playback.
- Playback interruption when the user speaks again.
- Creating and reusing `session_id`.
- Passing `user_id` and `session_id` to backend calls.
- Handling backend errors and displaying useful messages.

## Frontend Project Structure

```text
frontend/
├── .dockerignore                  # Docker ignore rules for frontend build context
├── Dockerfile                     # Frontend container image definition
├── index.html                     # Vite HTML entry point
├── package.json                   # Frontend dependencies and npm scripts
├── package-lock.json              # Locked dependency versions
├── vite.config.js                 # Vite configuration
│
└── src/
    ├── App.jsx                    # Main application component
    ├── main.jsx                   # React/Vite application entry point
    │
    ├── components/
    │   ├── Sidebar.jsx            # Sidebar layout/navigation component
    │   └── TopAppBar.jsx          # Top application bar/header component
    │
    ├── features/
    │   ├── chat/
    │   │   ├── index.js           # Chat feature exports
    │   │   └── components/
    │   │       └── ChatLog.jsx    # Conversation/message log component
    │   │
    │   ├── upload/
    │   │   ├── index.js           # Upload feature exports
    │   │   └── components/
    │   │       └── FileUpload.jsx # File/PDF upload UI component
    │   │
    │   └── voice/
    │       ├── index.js           # Voice feature exports
    │       ├── components/
    │       │   └── VoiceControls.jsx # Voice recording/control UI
    │       └── hooks/
    │           ├── useConversation.js          # HTTP/simple conversation hook
    │           ├── useConversationStreaming.js # WebSocket streaming conversation hook
    │           └── useVisualizer.js            # Audio visualizer hook
    │
    ├── services/
    │   └── api.js                 # API client/helper functions
    │
    └── styles/
        └── main.css               # Global frontend styles
```

## Recommended Feature Boundaries

### `src/services/api.js`

Centralize backend calls here:

- `POST /chat/ask`
- `POST /kb/ingest-pdf`
- `POST /kb/ingest-text`
- `POST /voice/turn`
- `POST /tts/stream`
- WebSocket connection URL construction for `/chat/voice-stream`

Avoid spreading raw endpoint URLs across components.

### `src/features/chat`

Owns text conversation display and chat-specific UI.

Typical responsibilities:

- Render user and assistant messages.
- Display loading states.
- Display provider/backend errors separately from assistant answers.
- Preserve `session_id` for follow-up questions.
- Show retrieved sources if needed.

### `src/features/upload`

Owns document upload UI.

Typical responsibilities:

- Let the user select a PDF or text file.
- Send the file to `/kb/ingest-pdf` or `/kb/ingest-text`.
- Display ingestion result.
- Show the selected namespace.
- Report upload/validation errors clearly.

### `src/features/voice`

Owns voice conversation UI and browser audio flow.

Typical responsibilities:

- Request microphone permissions.
- Capture or stream microphone audio.
- Send audio chunks to the backend WebSocket.
- Handle assistant audio chunks.
- Stop playback on interruption.
- Track `turn_id` to ignore stale audio chunks.
- Track `session_id` and `user_id`.

## Session Lifecycle

The frontend should create a new UUID-style `session_id` when the user starts a new conversation.

```text
new chat → new session_id
follow-up question → reuse same session_id
same user → reuse same user_id
different user → different user_id
```

Recommended payload fields:

```json
{
  "user_id": "user_123",
  "session_id": "demo-session-001"
}
```

For anonymous/local testing, `user_id` can be a browser-generated identifier or a fixed value such as:

```text
anonymous
```

In production, `user_id` should come from authentication rather than being trusted from the request body.

## HTTP Chat Flow

Endpoint:

```text
POST /chat/ask
```

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

## Simple Voice Turn Flow

Endpoint:

```text
POST /voice/turn
```

This endpoint is the easiest full voice flow:

```text
record user audio
→ send audio file/blob to backend
→ backend transcribes
→ backend retrieves KB context
→ backend generates answer
→ backend returns spoken audio
→ frontend plays audio
```

Expected form fields:

```text
file
voice_id
namespace
language_code
top_k
```

The response is audio. Metadata may be returned in headers:

```text
X-Transcript
X-Reply-Text
X-Sources-Count
```

The frontend should read these headers if it needs to display transcript and answer text.

## Realtime WebSocket Flow

Endpoint:

```text
WS /chat/voice-stream
```

Example URL:

```text
ws://localhost:8000/chat/voice-stream?voice_id=YOUR_VOICE_ID&namespace=products&language_code=spa&user_id=user_123&session_id=session_001
```

The frontend sends audio chunks and control events. The backend returns transcript events, assistant text, assistant audio chunks, and interruption acknowledgements.

## Client-to-Backend Events

Audio chunk:

```json
{
  "type": "audio_chunk",
  "audio_base64": "..."
}
```

Commit current speech turn:

```json
{
  "type": "commit"
}
```

Interrupt current assistant speech:

```json
{
  "type": "interrupt"
}
```

Close connection:

```json
{
  "type": "close"
}
```

## Backend-to-Client Events

STT session started:

```json
{
  "type": "stt_session_started",
  "config": {}
}
```

Partial transcript:

```json
{
  "type": "user_partial_transcript",
  "text": "..."
}
```

Committed transcript:

```json
{
  "type": "user_committed_transcript",
  "text": "..."
}
```

Sources retrieved from the KB:

```json
{
  "type": "sources",
  "sources": []
}
```

Assistant text:

```json
{
  "type": "assistant_text",
  "turn_id": "...",
  "text": "..."
}
```

Assistant audio chunk:

```json
{
  "type": "assistant_audio_chunk",
  "turn_id": "...",
  "audio_base64": "...",
  "format": "mp3_44100_128"
}
```

Assistant audio done:

```json
{
  "type": "assistant_audio_done",
  "turn_id": "..."
}
```

Assistant interrupted:

```json
{
  "type": "assistant_interrupted",
  "turn_id": "..."
}
```

Interrupt acknowledgement:

```json
{
  "type": "interrupt_ack",
  "turn_id": "..."
}
```

Error:

```json
{
  "type": "error",
  "message": "..."
}
```

## Audio Format

The backend realtime STT path expects audio chunks compatible with the configured realtime ElevenLabs STT settings.

Current expected backend audio format:

```text
pcm_16000
16 kHz
mono
16-bit signed little endian
```

The frontend must ensure that browser microphone audio is converted/resampled before sending it to the WebSocket.

## Interruption Behavior

The expected interruption behavior is:

```text
assistant is speaking
→ user starts speaking again
→ frontend stops local playback immediately
→ frontend sends { "type": "interrupt" }
→ backend cancels active TTS task
→ frontend ignores old chunks for the interrupted turn_id
→ new user turn starts
```

The frontend should track `turn_id` on assistant audio chunks. If an interruption occurs, discard late chunks for the old `turn_id`.

## Error Handling

Frontend should handle:

- HTTP validation errors.
- Provider errors from the backend.
- WebSocket disconnects.
- Microphone permission denial.
- Audio format/conversion errors.
- Empty transcript responses.
- Interrupted turns.
- Network timeouts.

Provider or backend errors are not valid assistant answers and should be displayed separately from chat messages.

## Development Notes

- Keep one active `session_id` per visible conversation.
- Create a new `session_id` for a new chat.
- Do not expose API keys in frontend code.
- Do not send provider credentials from the browser.
- Do not assume `/tts/stream` returns JSON; it returns audio.
- Treat transcripts and audio as sensitive user data.
