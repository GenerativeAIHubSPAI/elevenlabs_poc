import { useState, useRef, useCallback, useEffect } from "react";
import TopAppBar from "./components/TopAppBar.jsx";
import Sidebar from "./components/Sidebar.jsx";
import { ChatLog } from "./features/chat/index.js";
import {
  VoiceControls,
  useVisualizer,
  useConversationStreaming,
} from "./features/voice/index.js";
import "./styles/main.css";
import { fetchStaticKnowledgeSources } from "./services/api";


export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isTranscriptionView, setIsTranscriptionView] = useState(false);
  const [state, setState] = useState("idle");
  const [messages, setMessages] = useState([]);
  const [muted, setMuted] = useState(false);

  const userId = "portal:user";
  const userName = "Portal user";
  const authMode = "authenticated";

  const [sessionId] = useState(() => crypto.randomUUID());

  const [config, setConfig] = useState({
    idioma: "es",
    sexo: "hombre",
    tono: "cercano",
    knowledgeSource: "gachapon_distribution",
  });

  const [knowledgeSources, setKnowledgeSources] = useState([
    { value: "cache", label: "Uploaded PDFs" },
  ]);

  const activeNamespace =
    config.knowledgeSource === "cache"
      ? `cache:${sessionId}`
      : config.knowledgeSource;

  const uploadNamespace = `cache:${sessionId}`;

  const canvasRef = useRef(null);
  const liveBgRef = useRef(null);
  const stateRef = useRef(state);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  const visualizer = useVisualizer({
    canvasRef,
    liveBgRef,
    getState: useCallback(() => stateRef.current, []),
  });

  const onMessage = useCallback((role, text) => {
    setMessages((prev) => [...prev, { role, text }]);
  }, []);

  const handleConfigChange = useCallback((key, value) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
  }, []);

  const conversation = useConversationStreaming({
    visualizer,
    onMessage,
    onStateChange: setState,
    voiceId: import.meta.env.VITE_ELEVENLABS_VOICE_ID,
    namespace: activeNamespace,
    languageCode: config.idioma,
    gender: config.sexo,
    tone: config.tono,
    userId,
    userName,
    authMode,
    authToken: null,
    sessionId,
  });


  useEffect(() => {
    visualizer.resizeCanvas();
    visualizer.drawIdle();

    const onResize = () => visualizer.resizeCanvas();

    window.addEventListener("resize", onResize);

    return () => window.removeEventListener("resize", onResize);
  }, [visualizer]);

  useEffect(() => {
    if (!isTranscriptionView) {
      visualizer.resizeCanvas();
    }
  }, [isTranscriptionView, visualizer]);

  useEffect(() => {
    let cancelled = false;

    async function loadKnowledgeSources() {
      try {
        const data = await fetchStaticKnowledgeSources();
        const staticSources = data.sources ?? [];

        if (cancelled) return;

        setKnowledgeSources([
          ...staticSources,
          { value: "cache", label: "Uploaded PDFs" },
        ]);

        setConfig((prev) => {
          const currentSourceExists =
            staticSources.some(
              (source) => source.value === prev.knowledgeSource
            ) || prev.knowledgeSource === "cache";

          if (currentSourceExists) {
            return prev;
          }

          return {
            ...prev,
            knowledgeSource: staticSources[0]?.value ?? "cache",
          };
        });
      } catch (err) {
        console.error("Failed to load static KB sources", err);
      }
    }

    loadKnowledgeSources();

    return () => {
      cancelled = true;
    };
  }, []);


  const handleLogout = useCallback(() => {
    setMuted(false);
    conversation.stop();
    setMessages([]);
    setState("idle");
  }, [conversation]);

  const handleMuteToggle = useCallback(() => {
    const nowMuted = conversation.toggleMute();
    setMuted(nowMuted);
  }, [conversation]);

  const handleToggle = useCallback(async () => {
    if (!conversation.isRunning()) {
      if (conversation.isBusy()) return;

      setMessages([]);

      try {
        await conversation.start();
      } catch (e) {
        console.error("Failed to start conversation:", e);
        onMessage("error", e?.message ?? "Failed to start conversation.");
        setState("idle");
      }

      return;
    }

    setMuted(false);
    conversation.stop();
  }, [conversation, onMessage]);

  return (
    <>
      <TopAppBar
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen((v) => !v)}
        userName={userName}
      />

      <main
        className={`mt-16 p-10 h-[calc(100vh-4rem)] panel-transition ${
          sidebarOpen ? "mr-80" : "mr-0"
        }`}
      >
        <div className="h-full flex flex-col">
          <section className="flex-1 rounded-[2.5rem] relative overflow-hidden flex flex-col bg-white shadow-2xl border border-[#c7c4d7]">
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

            <div
              className={`absolute inset-0 flex flex-col ${
                isTranscriptionView ? "hidden" : ""
              }`}
            >
              <div
                ref={liveBgRef}
                className="absolute inset-0"
                style={{
                  background:
                    "radial-gradient(ellipse at 50% 70%, #0d1f4a 0%, #0a0a0a 70%)",
                }}
              />

              <div className="absolute inset-0 opacity-20 pointer-events-none">
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-[#4f5f76] blur-[160px] rounded-full animate-pulse" />
              </div>

              <div className="flex-1 flex items-center justify-center relative z-10">
                <div className="w-full px-16 h-64 flex items-center">
                  <canvas ref={canvasRef} className="w-full h-full" />
                </div>
              </div>

              <div className="absolute top-6 left-6 z-10 pointer-events-none">
                <span className="text-white font-semibold text-xl block">
                  Active Stream
                </span>
                <span className="text-[#b7c8e1] opacity-70 text-sm">
                  Monitoring Audio Input...
                </span>
              </div>
            </div>

            <div
              className={`absolute inset-0 flex flex-col bg-white ${
                !isTranscriptionView ? "hidden" : ""
              }`}
            >
              <div className="px-6 pt-6 pb-4 border-b border-[#c7c4d7] shrink-0">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-bold text-[#191c1e]">
                    Real-time Transcription
                  </h3>
                  <span className="text-xs font-bold text-[#565e74] bg-[#eceef0] px-3 py-1 rounded-full">
                    {messages.length} messages
                  </span>
                </div>
              </div>

              <ChatLog messages={messages} />
            </div>

            <VoiceControls
              state={state}
              onClick={handleToggle}
              onMuteToggle={handleMuteToggle}
              muted={muted}
              lightBg={isTranscriptionView}
            />
          </section>
        </div>
      </main>

      <Sidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen((v) => !v)}
        config={config}
        onConfigChange={handleConfigChange}
        knowledgeSources={knowledgeSources}
        sessionId={sessionId}
        uploadNamespace={uploadNamespace}
      />
    </>
  );
}