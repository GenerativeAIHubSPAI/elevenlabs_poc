const IS_IDLE = (s) => s === "idle";
const IS_BUSY = (s) => s === "processing" || s === "replying";

const PTT_LABEL = {
  idle:       "Push to Talk",
  active:     "Listening",
  speaking:   "Listening",
  processing: "Processing",
  replying:   "Replying",
};

export default function VoiceControls({ state, onClick, lightBg = false }) {
  const secondaryBtn = lightBg
    ? "bg-[#eceef0] border border-[#c7c4d7] text-[#4f5f76] hover:bg-[#4f5f76] hover:text-white hover:border-[#4f5f76]"
    : "bg-white/10 backdrop-blur-xl border border-white/20 text-white hover:bg-white/20";

  return (
    <div className="absolute bottom-10 left-1/2 -translate-x-1/2 flex items-center gap-6 z-20">
      {/* Mute — placeholder, invisible when idle */}
      <button
        className={`w-14 h-14 rounded-full transition-all flex items-center justify-center ${secondaryBtn} ${
          IS_IDLE(state) ? "invisible" : ""
        }`}
      >
        <span className="material-symbols-outlined text-[28px]">mic</span>
      </button>

      {/* Main push-to-talk */}
      <div className="relative">
        {!IS_IDLE(state) && !IS_BUSY(state) && (
          <div className="absolute inset-0 bg-[#4f5f76]/40 rounded-full animate-pulse-ring" />
        )}
        <button
          onClick={onClick}
          disabled={IS_BUSY(state)}
          className="relative w-24 h-24 rounded-full bg-[#4f5f76] text-white shadow-2xl flex flex-col items-center justify-center hover:scale-105 active:scale-95 transition-all disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:scale-100"
        >
          <span
            className="material-symbols-outlined text-[40px]"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            {IS_BUSY(state) ? "hourglass_empty" : "keyboard_voice"}
          </span>
          <span className="text-[10px] font-bold uppercase tracking-tighter mt-0.5">
            {PTT_LABEL[state] ?? "Push to Talk"}
          </span>
        </button>
      </div>

      {/* End call — visible e interactivo siempre que no esté idle */}
      <button
        onClick={!IS_IDLE(state) ? onClick : undefined}
        className={`w-14 h-14 rounded-full bg-red-600 text-white hover:brightness-110 shadow-lg transition-all flex items-center justify-center ${
          IS_IDLE(state) ? "invisible" : ""
        }`}
      >
        <span className="material-symbols-outlined text-[28px]">call_end</span>
      </button>
    </div>
  );
}
