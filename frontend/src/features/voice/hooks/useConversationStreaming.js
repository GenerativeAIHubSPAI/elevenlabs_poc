/**
 * useConversationStreaming
 *
 * Alternative to useConversation that uses the WebSocket endpoint /voice-stream
 * instead of the HTTP /voice/turn endpoint.
 *
 * Key differences from useConversation:
 *  - Protocol: WebSocket (persistent, bidirectional) instead of HTTP POST
 *  - VAD: done server-side by ElevenLabs realtime STT (no vad-react needed)
 *  - Audio sent: raw PCM chunks in real-time instead of a full WAV after silence
 *  - Audio received: MP3 chunks streamed back, accumulated and played at end
 *  - Supports barge-in: call interrupt() to cancel ongoing TTS
 *
 * WebSocket message protocol (server → client):
 *   stt_session_started      — ElevenLabs STT session is ready
 *   user_partial_transcript  — live partial transcript while user speaks
 *   user_committed_transcript— VAD detected end of utterance, transcript final
 *   sources                  — KB chunks used for the answer
 *   assistant_text           — LLM answer text
 *   assistant_audio_chunk    — one MP3 chunk (base64), accumulate until "done"
 *   assistant_audio_done     — all TTS chunks sent, safe to decode and play
 *   assistant_interrupted    — server cancelled TTS due to barge-in
 *   stt_error / error        — error events
 *
 * WebSocket message protocol (client → server):
 *   audio_chunk  { audio_base64 }  — 100 ms of raw PCM 16 kHz mono Int16
 *   interrupt                      — cancel ongoing TTS
 *   commit                         — force-commit current STT utterance
 *   close                          — graceful shutdown
 */

import { useRef, useCallback } from "react";

const WS_BASE_URL = "ws://localhost:8000";

function buildStreamingUrl({ voiceId, namespace, languageCode }) {
  const params = new URLSearchParams({ namespace, language_code: languageCode });
  // voice_id is optional — the server falls back to ELEVENLABS_DEFAULT_VOICE_ID
  if (voiceId) params.set("voice_id", voiceId);
  // The router is mounted at /chat in main.py, so the full path is /chat/voice-stream
  return `${WS_BASE_URL}/chat/voice-stream?${params}`;
}

export function useConversationStreaming({
  visualizer,
  onMessage,
  onStateChange,
  voiceId,
  namespace     = "default",
  languageCode  = "spa",
}) {
  const wsRef            = useRef(null);
  const isActiveRef      = useRef(false);
  const isReplyingRef    = useRef(false);

  // Capture pipeline (16 kHz AudioContext + ScriptProcessor)
  const captureCtxRef    = useRef(null);
  const processorRef     = useRef(null);

  // Playback pipeline
  const playbackCtxRef   = useRef(null);
  const currentSrcRef    = useRef(null); // AudioBufferSourceNode in flight
  const audioChunksRef   = useRef([]);   // accumulates Uint8Array MP3 chunks

  // ─── Playback helpers ────────────────────────────────────────────────────

  const stopPlayback = useCallback(() => {
    if (currentSrcRef.current) {
      try { currentSrcRef.current.stop(); } catch (_) {}
      currentSrcRef.current = null;
    }
    visualizer.detachReplySource();
    audioChunksRef.current = [];
    isReplyingRef.current  = false;
  }, [visualizer]);

  const playAccumulatedChunks = useCallback(async () => {
    const chunks = audioChunksRef.current;
    audioChunksRef.current = [];
    if (chunks.length === 0) return;

    // Close any previous playback context before creating a new one
    if (playbackCtxRef.current) {
      playbackCtxRef.current.close();
      playbackCtxRef.current = null;
    }

    // Concatenate all binary chunks into a single ArrayBuffer
    const totalBytes = chunks.reduce((n, c) => n + c.byteLength, 0);
    const combined   = new Uint8Array(totalBytes);
    let offset = 0;
    for (const chunk of chunks) { combined.set(chunk, offset); offset += chunk.byteLength; }

    // Decode the MP3 and play it back through Web Audio
    const actx = new AudioContext();
    playbackCtxRef.current = actx;

    let audioBuffer;
    try {
      // decodeAudioData takes ownership of the ArrayBuffer (it's transferred)
      audioBuffer = await actx.decodeAudioData(combined.buffer);
    } catch (err) {
      onMessage("error", `Audio decode error: ${err.message}`);
      return;
    }

    const src    = actx.createBufferSource();
    src.buffer   = audioBuffer;
    visualizer.attachReplySource(actx, src);
    src.connect(actx.destination);
    currentSrcRef.current = src;

    src.onended = () => {
      visualizer.detachReplySource();
      currentSrcRef.current = null;
      isReplyingRef.current = false;
      if (isActiveRef.current) onStateChange("active");
    };

    src.start();
  }, [visualizer, onMessage, onStateChange]);

  // ─── Incoming WebSocket messages ─────────────────────────────────────────

  const handleServerMessage = useCallback(async (msg) => {
    switch (msg.type) {

      case "stt_session_started":
        // ElevenLabs STT handshake complete — audio is flowing and VAD is active
        onStateChange("active");
        break;

      case "user_partial_transcript":
        // Fires continuously while the user is speaking (updates fast)
        // Uncomment to display live "ghost" text in the chat UI:
        // onMessage("user_partial", msg.text);
        break;

      case "user_committed_transcript":
        // Server-side VAD detected end-of-utterance → transcript is final
        onMessage("user", msg.text);
        onStateChange("processing");
        break;

      case "sources":
        // Knowledge base chunks used to answer — available for display if needed
        // msg.sources: Array<{ chunk_id, title, text, score }>
        break;

      case "assistant_text":
        // LLM answer text arrives before TTS chunks
        onMessage("assistant", msg.text);
        onStateChange("replying");
        isReplyingRef.current  = true;
        audioChunksRef.current = []; // reset buffer before accumulating new reply
        break;

      case "assistant_audio_chunk": {
        // One MP3 chunk — decode base64 to binary and accumulate
        const binary = atob(msg.audio_base64);
        const bytes  = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
        audioChunksRef.current.push(bytes);
        break;
      }

      case "assistant_audio_done":
        // All TTS chunks received — concatenate, decode MP3, and play
        await playAccumulatedChunks();
        break;

      case "assistant_interrupted":
        // Server cancelled TTS mid-stream (barge-in from the user)
        stopPlayback();
        if (isActiveRef.current) onStateChange("active");
        break;

      case "stt_error":
        onMessage("error", `STT error: ${JSON.stringify(msg.event)}`);
        break;

      case "error":
        onMessage("error", msg.message ?? "Unknown server error");
        break;

      default:
        break;
    }
  }, [onMessage, onStateChange, playAccumulatedChunks, stopPlayback]);

  // ─── Mic capture → WebSocket ─────────────────────────────────────────────

  const startCapture = useCallback((stream) => {
    // Dedicated AudioContext fixed at 16 kHz — matches ELEVENLABS_STT_SAMPLE_RATE.
    // We need a separate context from the visualizer's because the visualizer runs
    // at the browser's default rate (usually 48 kHz) while ElevenLabs STT wants 16 kHz.
    const ctx = new AudioContext({ sampleRate: 16000 });
    captureCtxRef.current = ctx;

    const source    = ctx.createMediaStreamSource(stream);

    // ScriptProcessor (deprecated but universally supported).
    // Buffer size must be a power of 2. 2048 @ 16 kHz = 128 ms per callback.
    // Modern alternative: AudioWorkletNode (more performant, runs off the main thread).
    const processor = ctx.createScriptProcessor(2048, 1, 1);
    processorRef.current = processor;

    processor.onaudioprocess = (e) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

      // Convert Float32 [-1, 1] samples to signed Int16 PCM
      const float32 = e.inputBuffer.getChannelData(0);
      const int16   = new Int16Array(float32.length);
      for (let i = 0; i < float32.length; i++) {
        int16[i] = Math.max(-1, Math.min(1, float32[i])) * 0x7fff;
      }

      // Base64-encode the raw PCM bytes
      const bytes = new Uint8Array(int16.buffer);
      let binary  = "";
      for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);

      wsRef.current.send(JSON.stringify({
        type:         "audio_chunk",
        audio_base64: btoa(binary),
      }));
    };

    // ScriptProcessor requires a path to destination to fire onaudioprocess.
    // We route through a GainNode at 0 to avoid sending raw mic audio to speakers.
    const silentGain = ctx.createGain();
    silentGain.gain.value = 0;
    source.connect(processor);
    processor.connect(silentGain);
    silentGain.connect(ctx.destination);
  }, []);

  const stopCapture = useCallback(() => {
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }
    if (captureCtxRef.current) {
      captureCtxRef.current.close();
      captureCtxRef.current = null;
    }
  }, []);

  // ─── Public API ────────────────────────────────────────────────────────────

  const start = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    visualizer.start(stream);

    const ws = new WebSocket(buildStreamingUrl({ voiceId, namespace, languageCode }));
    wsRef.current = ws;

    ws.onopen = () => {
      // WebSocket open — start pumping PCM. State becomes "active" once the
      // server confirms the ElevenLabs STT session (stt_session_started).
      startCapture(stream);
      isActiveRef.current = true;
      onStateChange("processing"); // transitional: "connecting to STT..."
    };

    ws.onmessage = (e) => handleServerMessage(JSON.parse(e.data));

    ws.onerror = () => onMessage("error", "WebSocket connection error");

    ws.onclose = () => {
      if (isActiveRef.current) {
        isActiveRef.current = false;
        onStateChange("idle");
      }
    };
  }, [
    visualizer, voiceId, namespace, languageCode,
    startCapture, handleServerMessage, onMessage, onStateChange,
  ]);

  const stop = useCallback(() => {
    isActiveRef.current = false;

    stopCapture();
    stopPlayback();

    if (wsRef.current) {
      if (wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "close" }));
      }
      wsRef.current = null;
    }

    if (playbackCtxRef.current) {
      playbackCtxRef.current.close();
      playbackCtxRef.current = null;
    }

    visualizer.stop();
    onStateChange("idle");
  }, [visualizer, stopCapture, stopPlayback, onStateChange]);

  /**
   * Cancel the assistant's ongoing TTS and resume listening (barge-in).
   * Only has effect while the assistant is replying.
   */
  const interrupt = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN && isReplyingRef.current) {
      wsRef.current.send(JSON.stringify({ type: "interrupt" }));
      stopPlayback();
    }
  }, [stopPlayback]);

  const isRunning = useCallback(() => isActiveRef.current, []);
  const isBusy    = useCallback(() => isReplyingRef.current, []);

  return { start, stop, interrupt, isRunning, isBusy };
}
