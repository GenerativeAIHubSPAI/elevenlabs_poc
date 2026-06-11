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
 *   stt_session_started       — ElevenLabs STT session is ready
 *   user_partial_transcript   — live partial transcript while user speaks
 *   user_committed_transcript — VAD detected end of utterance, transcript final
 *   sources                   — KB chunks used for the answer
 *   assistant_text            — LLM answer text
 *   assistant_audio_chunk     — one MP3 chunk (base64), accumulate until done
 *   assistant_audio_done      — all TTS chunks sent, safe to decode and play
 *   assistant_interrupted     — server cancelled TTS due to barge-in
 *   stt_error / error         — error events
 *
 * WebSocket message protocol (client → server):
 *   audio_chunk  { audio_base64 } — 100 ms of raw PCM 16 kHz mono Int16
 *   interrupt                     — cancel ongoing TTS
 *   commit                        — force-commit current STT utterance
 *   close                         — graceful shutdown
 */

import { useRef, useCallback } from "react";

const API_PREFIX = (import.meta.env.VITE_API_PREFIX ?? "").replace(/\/+$/, "");
const WS_BASE_URL =
  (location.protocol === "https:" ? "wss" : "ws") +
  "://" +
  location.host +
  API_PREFIX;

function buildStreamingUrl({
  voiceId,
  namespace,
  languageCode,
  gender,
  tone,
  userId,
  userName,
  authMode,
  authToken,
  sessionId,
}) {
  const params = new URLSearchParams({
    namespace,
    language_code: languageCode,
    user_id: userId,
    session_id: sessionId,
  });

  if (voiceId) params.set("voice_id", voiceId);
  if (gender) params.set("gender", gender);
  if (tone) params.set("tone", tone);
  if (userName) params.set("user_name", userName);
  if (authMode) params.set("auth_mode", authMode);
  if (authToken) params.set("token", authToken);

  return `${WS_BASE_URL}/chat/voice-stream?${params}`;
}

export function useConversationStreaming({
  visualizer,
  onMessage,
  onStateChange,
  voiceId,
  namespace = "default",
  languageCode = "es",
  gender = "hombre",
  tone = "cercano",
  userId = "guest:anonymous",
  userName = "Guest user",
  authMode = "guest",
  authToken,
  sessionId,
}) {
  const wsRef = useRef(null);
  const isActiveRef = useRef(false);
  const isReplyingRef = useRef(false);
  const mutedRef = useRef(false);

  const captureCtxRef = useRef(null);
  const processorRef = useRef(null);

  const playbackCtxRef = useRef(null);
  const currentSrcRef = useRef(null);
  const audioChunksRef = useRef([]);

  const stopPlayback = useCallback(() => {
    if (currentSrcRef.current) {
      try {
        currentSrcRef.current.stop();
      } catch (_) {
        // Ignore already-stopped audio source.
      }

      currentSrcRef.current = null;
    }

    visualizer.detachReplySource();
    audioChunksRef.current = [];
    isReplyingRef.current = false;
  }, [visualizer]);

  const playAccumulatedChunks = useCallback(async () => {
    const chunks = audioChunksRef.current;
    audioChunksRef.current = [];

    if (chunks.length === 0) {
      return;
    }

    if (playbackCtxRef.current) {
      playbackCtxRef.current.close();
      playbackCtxRef.current = null;
    }

    const totalBytes = chunks.reduce((n, chunk) => n + chunk.byteLength, 0);
    const combined = new Uint8Array(totalBytes);

    let offset = 0;

    for (const chunk of chunks) {
      combined.set(chunk, offset);
      offset += chunk.byteLength;
    }

    const actx = new AudioContext();
    playbackCtxRef.current = actx;

    let audioBuffer;

    try {
      audioBuffer = await actx.decodeAudioData(combined.buffer);
    } catch (err) {
      onMessage("error", `Audio decode error: ${err.message}`);
      return;
    }

    const src = actx.createBufferSource();
    src.buffer = audioBuffer;

    visualizer.attachReplySource(actx, src);

    src.connect(actx.destination);
    currentSrcRef.current = src;

    src.onended = () => {
      visualizer.detachReplySource();
      currentSrcRef.current = null;
      isReplyingRef.current = false;

      if (isActiveRef.current) {
        onStateChange("active");
      }
    };

    src.start();
  }, [visualizer, onMessage, onStateChange]);

  const handleServerMessage = useCallback(
    async (msg) => {
      switch (msg.type) {
        case "stt_session_started":
          onStateChange("active");
          break;

        case "user_partial_transcript":
          break;

        case "user_committed_transcript":
          onMessage("user", msg.text);
          onStateChange("processing");
          break;

        case "sources":
          break;

        case "assistant_text":
          onMessage("assistant", msg.text);
          onStateChange("replying");
          isReplyingRef.current = true;
          audioChunksRef.current = [];
          break;

        case "assistant_audio_chunk": {
          const binary = atob(msg.audio_base64);
          const bytes = new Uint8Array(binary.length);

          for (let i = 0; i < binary.length; i += 1) {
            bytes[i] = binary.charCodeAt(i);
          }

          audioChunksRef.current.push(bytes);
          break;
        }

        case "assistant_audio_done":
          await playAccumulatedChunks();
          break;

        case "assistant_interrupted":
          stopPlayback();

          if (isActiveRef.current) {
            onStateChange("active");
          }

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
    },
    [onMessage, onStateChange, playAccumulatedChunks, stopPlayback],
  );

  const startCapture = useCallback((stream) => {
    const ctx = new AudioContext({ sampleRate: 16000 });
    captureCtxRef.current = ctx;

    const source = ctx.createMediaStreamSource(stream);
    const processor = ctx.createScriptProcessor(2048, 1, 1);

    processorRef.current = processor;

    processor.onaudioprocess = (event) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        return;
      }

      if (mutedRef.current) {
        return;
      }

      const float32 = event.inputBuffer.getChannelData(0);
      const int16 = new Int16Array(float32.length);

      for (let i = 0; i < float32.length; i += 1) {
        int16[i] = Math.max(-1, Math.min(1, float32[i])) * 0x7fff;
      }

      const bytes = new Uint8Array(int16.buffer);
      let binary = "";

      for (let i = 0; i < bytes.length; i += 1) {
        binary += String.fromCharCode(bytes[i]);
      }

      wsRef.current.send(
        JSON.stringify({
          type: "audio_chunk",
          audio_base64: btoa(binary),
        }),
      );
    };

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

  const start = useCallback(async () => {
    if (!sessionId) {
      throw new Error("Missing sessionId.");
    }

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    visualizer.start(stream);

    const ws = new WebSocket(
      buildStreamingUrl({
        voiceId,
        namespace,
        languageCode,
        gender,
        tone,
        userId,
        userName,
        authMode,
        authToken,
        sessionId,
      }),
    );

    wsRef.current = ws;

    ws.onopen = () => {
      startCapture(stream);
      isActiveRef.current = true;
      onStateChange("processing");
    };

    ws.onmessage = (event) => handleServerMessage(JSON.parse(event.data));

    ws.onerror = (event) => {
      console.error("WebSocket error:", event);
      onMessage(
        "error",
        "WebSocket connection error. Check DevTools → Network → WS.",
      );
    };

    ws.onclose = () => {
      if (isActiveRef.current) {
        isActiveRef.current = false;
        onStateChange("idle");
      }
    };
  }, [
    visualizer,
    voiceId,
    namespace,
    languageCode,
    gender,
    tone,
    userId,
    userName,
    authMode,
    authToken,
    sessionId,
    startCapture,
    handleServerMessage,
    onMessage,
    onStateChange,
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

  const interrupt = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN && isReplyingRef.current) {
      wsRef.current.send(JSON.stringify({ type: "interrupt" }));
      stopPlayback();
    }
  }, [stopPlayback]);

  const isRunning = useCallback(() => isActiveRef.current, []);
  const isBusy = useCallback(() => isReplyingRef.current, []);

  const toggleMute = useCallback(() => {
    mutedRef.current = !mutedRef.current;

    return mutedRef.current;
  }, []);

  const isMuted = useCallback(() => mutedRef.current, []);

  return {
    start,
    stop,
    interrupt,
    isRunning,
    isBusy,
    toggleMute,
    isMuted,
  };
}