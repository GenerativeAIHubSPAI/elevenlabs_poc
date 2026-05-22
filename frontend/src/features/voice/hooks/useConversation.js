import { useRef, useCallback } from "react";
import { useMicVAD } from "@ricky0123/vad-react";
import { sendAudio } from "../../../services/api.js";

export function useConversation({ visualizer, onMessage, onStateChange }) {
  const isActiveRef     = useRef(false);
  const isProcessingRef = useRef(false);

  const playReply = useCallback(
    async (response) => {
      const micCtx = visualizer.getMicContext();
      const actx   = micCtx || new AudioContext();
      const src    = actx.createBufferSource();
      src.buffer   = await actx.decodeAudioData(await response.arrayBuffer());

      visualizer.attachReplySource(actx, src);
      src.connect(actx.destination);
      onStateChange("replying");

      return new Promise((resolve) => {
        src.onended = () => {
          visualizer.detachReplySource();
          resolve();
        };
        src.start();
      });
    },
    [visualizer, onStateChange]
  );

  const handleSpeechEnd = useCallback(
    async (audio) => {
      if (!isActiveRef.current || isProcessingRef.current) return;
      isProcessingRef.current = true;
      onStateChange("processing");

      try {
        const res        = await sendAudio(audio, 16000);
        const transcript = decodeURIComponent(res.headers.get("X-Transcript") ?? "");
        const replyText  = decodeURIComponent(res.headers.get("X-Reply-Text") ?? "");

        if (transcript) onMessage("user", transcript);
        if (replyText)  onMessage("assistant", replyText);

        await playReply(res);
      } catch (e) {
        onMessage("error", `Error: ${e.message}`);
      } finally {
        isProcessingRef.current = false;
        if (isActiveRef.current) onStateChange("active");
      }
    },
    [onStateChange, onMessage, playReply]
  );

  const onSpeechStart = useCallback(() => {
    if (!isActiveRef.current || isProcessingRef.current) return;
    onStateChange("speaking");
  }, [onStateChange]);

  const vad = useMicVAD({
    startOnLoad: false,
    workletURL: "/vad.worklet.bundle.min.js",
    modelURL: "/silero_vad.onnx",
    ortConfig: (ort) => { ort.env.wasm.wasmPaths = "/"; },
    onSpeechStart,
    onSpeechEnd: handleSpeechEnd,
  });

  const start = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    visualizer.start(stream);
    vad.start();
    isActiveRef.current = true;
    onStateChange("active");
  }, [visualizer, vad, onStateChange]);

  const stop = useCallback(() => {
    vad.pause();
    visualizer.stop();
    isActiveRef.current = false;
    onStateChange("idle");
  }, [visualizer, vad, onStateChange]);

  const isRunning = useCallback(() => isActiveRef.current, []);
  const isBusy    = useCallback(() => isProcessingRef.current, []);

  return { start, stop, isRunning, isBusy };
}
