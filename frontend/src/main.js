import { createTabs }         from "./components/Tabs.js";
import { createChatLog }      from "./components/ChatLog.js";
import { createToggleButton } from "./components/ToggleButton.js";
import { createVisualizer }   from "./hooks/useVisualizer.js";
import { createConversation } from "./hooks/useConversation.js";

const waveCanvas  = document.getElementById("wave-canvas");
const liveBg      = document.getElementById("live-bg");
const chatLogEl   = document.getElementById("chat-log");
const toggleBtnEl = document.getElementById("toggle-btn");
const btnLabelEl  = document.getElementById("btn-label");
const statusEl    = document.getElementById("status-text");
const liveLabelEl = document.getElementById("live-label");

let currentState = "idle";

const visualizer = createVisualizer({
  canvas: waveCanvas,
  liveBg,
  getState: () => currentState,
});

const chatLog = createChatLog(chatLogEl);

const button = createToggleButton({
  btnEl:       toggleBtnEl,
  labelEl:     btnLabelEl,
  statusEl,
  liveLabelEl,
});

const conversation = createConversation({
  visualizer,
  onMessage: (role, text) => chatLog.append(role, text),
  onStateChange: (state) => {
    currentState = state;
    button.setState(state);
  },
});

createTabs((tab) => {
  if (tab === "live") visualizer.resizeCanvas();
});

button.onPress(async () => {
  if (conversation.isBusy()) return;

  if (!conversation.isRunning()) {
    try {
      await conversation.start();
    } catch (e) {
      button.setState("idle");
      statusEl.textContent = "Sin acceso al micrófono";
      console.error(e);
    }
  } else {
    conversation.stop();
  }
});

// Estado inicial
visualizer.resizeCanvas();
visualizer.drawIdle();
window.addEventListener("resize", () => visualizer.resizeCanvas());
