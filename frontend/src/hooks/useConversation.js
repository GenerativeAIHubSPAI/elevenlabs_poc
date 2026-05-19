import { sendAudio, hexDecode } from "../services/api.js";
import { createVAD } from "./useVAD.js";

export function createConversation({ visualizer, onMessage, onStateChange }) {
  let vadInstance  = null;
  let isActive     = false;
  let isProcessing = false;

  function setState(state) {
    onStateChange(state);
  }

  async function handleSpeechEnd(audio) {
    if (isProcessing) return;
    isProcessing = true;
    setState("processing");

    try {
      const res        = await sendAudio(audio, 16000);
      const transcript = hexDecode(res.headers.get("X-Transcript"));
      const replyText  = hexDecode(res.headers.get("X-Reply-Text"));

      if (transcript) onMessage("user", transcript);
      if (replyText)  onMessage("assistant", replyText);

      await playReply(res);
    } catch (e) {
      onMessage("error", `Error: ${e.message}`);
      console.error(e);
    } finally {
      isProcessing = false;
      setState("active");
    }
  }

  async function playReply(response) {
    const micCtx = visualizer.getMicContext();
    const actx   = micCtx || new AudioContext();
    const src    = actx.createBufferSource();
    src.buffer   = await actx.decodeAudioData(await response.arrayBuffer());

    visualizer.attachReplySource(actx, src);
    src.connect(actx.destination);
    setState("replying");

    return new Promise(resolve => {
      src.onended = () => {
        visualizer.detachReplySource();
        resolve();
      };
      src.start();
    });
  }

  async function start() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    visualizer.start(stream);

    vadInstance = await createVAD({
      stream,
      onSpeechStart: () => {
        if (isProcessing) return;
        setState("speaking");
      },
      onSpeechEnd: handleSpeechEnd,
    });

    vadInstance.start();
    isActive = true;
    setState("active");
  }

  function stop() {
    if (vadInstance) vadInstance.pause();
    visualizer.stop();
    isActive = false;
    setState("idle");
  }

  function isRunning() { return isActive; }
  function isBusy()    { return isProcessing; }

  return { start, stop, isRunning, isBusy };
}
