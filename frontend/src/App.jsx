import { useState, useRef, useCallback, useEffect } from "react";
import TopAppBar from "./components/TopAppBar.jsx";
import Sidebar from "./components/Sidebar.jsx";
import { ChatLog } from "./features/chat/index.js";
import { VoiceControls, useVisualizer, useConversationStreaming } from "./features/voice/index.js";
import "./styles/main.css";

export default function App() {
  const [sidebarOpen, setSidebarOpen]               = useState(true);
  const [isTranscriptionView, setIsTranscriptionView] = useState(false);
  const [state, setState]                           = useState("idle");
  const [messages, setMessages]                     = useState([]);
  const [config, setConfig] = useState({
    idioma: "spa",
    sexo:   "hombre",
    tono:   "cercano",
  });

  const handleConfigChange = useCallback((key, value) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
  }, []);

  const canvasRef = useRef(null);
  const liveBgRef = useRef(null);
  const stateRef  = useRef(state);

  useEffect(() => { stateRef.current = state; }, [state]);

  const visualizer = useVisualizer({
    canvasRef,
    liveBgRef,
    getState: useCallback(() => stateRef.current, []),
  });

  const onMessage = useCallback((role, text) => {
    setMessages((prev) => [...prev, { role, text }]);
  }, []);

  const conversation = useConversationStreaming({
    visualizer,
    onMessage,
    onStateChange: setState,
    voiceId:      import.meta.env.VITE_ELEVENLABS_VOICE_ID,
    namespace:    import.meta.env.VITE_KB_NAMESPACE ?? "default",
    languageCode: config.idioma,
    gender:       config.sexo,
    tone:         config.tono,
  });

  useEffect(() => {
    visualizer.resizeCanvas();
    visualizer.drawIdle();
    const onResize = () => visualizer.resizeCanvas();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [visualizer]);

  // Re-size canvas when switching back to visualizer view
  useEffect(() => {
    if (!isTranscriptionView) visualizer.resizeCanvas();
  }, [isTranscriptionView, visualizer]);

  const handleToggle = useCallback(async () => {
    if (conversation.isBusy()) return;
    if (!conversation.isRunning()) {
      setMessages([]); // nueva sesión → limpiar el historial anterior
      try { await conversation.start(); }
      catch (e) { setState("idle"); }
    } else {
      conversation.stop();
    }
  }, [conversation]);

  return (
    <>
      <TopAppBar sidebarOpen={sidebarOpen} onToggleSidebar={() => setSidebarOpen((v) => !v)} />

      <main
        className={`mt-16 p-10 h-[calc(100vh-4rem)] panel-transition ${
          sidebarOpen ? "mr-80" : "mr-0"
        }`}
      >
        <div className="h-full flex flex-col">
          <section className="flex-1 rounded-[2.5rem] relative overflow-hidden flex flex-col bg-white shadow-2xl border border-[#c7c4d7]">

            {/* View toggle — top right corner */}
            <div className="absolute top-5 right-5 z-30">
              <button
                onClick={() => setIsTranscriptionView((v) => !v)}
                className="flex items-center gap-1.5 px-4 py-2 bg-white/90 backdrop-blur shadow-md rounded-full text-[#4f5f76] hover:bg-[#4f5f76] hover:text-white transition-all text-sm font-bold border border-[#4f5f76]/20"
              >
                <span className="material-symbols-outlined text-[18px]">
                  {isTranscriptionView ? "analytics" : "notes"}
                </span>
                {isTranscriptionView ? "Visualizer" : "Transcription"}
              </button>
            </div>

            {/* ── Visualization view ── */}
            <div className={`absolute inset-0 flex flex-col ${isTranscriptionView ? "hidden" : ""}`}>
              {/* Dynamic background — updated by useVisualizer */}
              <div
                ref={liveBgRef}
                className="absolute inset-0"
                style={{ background: "radial-gradient(ellipse at 50% 70%, #0d1f4a 0%, #0a0a0a 70%)" }}
              />
              {/* Ambient glow */}
              <div className="absolute inset-0 opacity-20 pointer-events-none">
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-[#4f5f76] blur-[160px] rounded-full animate-pulse" />
              </div>

              {/* Canvas */}
              <div className="flex-1 flex items-center justify-center relative z-10">
                <div className="w-full px-16 h-64 flex items-center">
                  <canvas ref={canvasRef} className="w-full h-full" />
                </div>
              </div>

              {/* Stream label */}
              <div className="absolute top-6 left-6 z-10 pointer-events-none">
                <span className="text-white font-semibold text-xl block">Active Stream</span>
                <span className="text-[#b7c8e1] opacity-70 text-sm">Monitoring Audio Input...</span>
              </div>

            </div>

            {/* ── Transcription view ── */}
            <div className={`absolute inset-0 flex flex-col bg-white ${!isTranscriptionView ? "hidden" : ""}`}>
              <div className="px-6 pt-6 pb-4 border-b border-[#c7c4d7] shrink-0">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-bold text-[#191c1e]">Real-time Transcription</h3>
                  <span className="text-xs font-bold text-[#565e74] bg-[#eceef0] px-3 py-1 rounded-full">
                    {messages.length} messages
                  </span>
                </div>
              </div>
              <ChatLog messages={messages} />
            </div>

            {/* Controls flotantes — visibles en ambas vistas */}
            <VoiceControls state={state} onClick={handleToggle} lightBg={isTranscriptionView} />


          </section>
        </div>
      </main>

      <Sidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen((v) => !v)}
        config={config}
        onConfigChange={handleConfigChange}
      />
    </>
  );
}
