const IS_IDLE = (s) => s === "idle";
const IS_BUSY = (s) => s === "processing" || s === "replying";

const PTT_LABEL = {
  idle: "Start",
  active: "Listening",
  speaking: "Listening",
  processing: "Thinking",
  replying: "Replying",
};

const PTT_ICON = {
  idle: "keyboard_voice",
  active: "graphic_eq",
  speaking: "graphic_eq",
  processing: "hourglass_empty",
  replying: "campaign",
};

export default function VoiceControls({
  state,
  onClick,
  onMuteToggle,
  muted = false,
  lightBg = false,
}) {
  const isIdle = IS_IDLE(state);
  const isBusy = IS_BUSY(state);
  const label = PTT_LABEL[state] ?? "Start";
  const icon = PTT_ICON[state] ?? "keyboard_voice";

  const dockClass = lightBg
    ? "bg-white/90 border border-[#c7c4d7]/40 shadow-2xl"
    : "bg-black/30 border border-white/20 shadow-2xl backdrop-blur-xl";

  const sideButtonClass = lightBg
    ? "bg-[#eceef0] text-[#4f5f76] hover:bg-[#4f5f76] hover:text-white"
    : "bg-white/10 text-white hover:bg-white/20";

  const mutedButtonClass = lightBg
    ? "bg-amber-100 text-amber-600 hover:bg-amber-500 hover:text-white"
    : "bg-amber-500/30 text-amber-300 hover:bg-amber-500/50";

  const mainButtonClass = isBusy
    ? "bg-[#4f5f76]/70 cursor-not-allowed"
    : isIdle
      ? "bg-[#4f5f76] hover:scale-105 active:scale-95"
      : "bg-[#4f5f76] hover:scale-105 active:scale-95";

  return (
    <div className="absolute bottom-10 left-1/2 -translate-x-1/2 z-20">
      <div
        className={`flex items-center gap-4 rounded-full px-4 py-3 ${dockClass}`}
      >
        {/* Mute */}
        <button
          type="button"
          onClick={!isIdle ? onMuteToggle : undefined}
          disabled={isIdle}
          title={muted ? "Activar micrófono" : "Silenciar micrófono"}
          aria-label={muted ? "Activar micrófono" : "Silenciar micrófono"}
          className={`flex h-12 w-12 items-center justify-center rounded-full transition-all disabled:opacity-30 disabled:cursor-not-allowed ${
            muted ? mutedButtonClass : sideButtonClass
          }`}
        >
          <span className="material-symbols-outlined text-[26px]">
            {muted ? "mic_off" : "mic"}
          </span>
        </button>

        {/* Main action */}
        <div className="relative">
          {!isIdle && !isBusy && !muted && (
            <div className="absolute inset-0 rounded-full bg-[#4f5f76]/40 animate-pulse-ring" />
          )}

          <button
            type="button"
            onClick={onClick}
            disabled={isBusy}
            aria-label={label}
            className={`relative flex h-24 w-24 flex-col items-center justify-center rounded-full text-white shadow-2xl transition-all disabled:opacity-70 disabled:hover:scale-100 ${mainButtonClass}`}
          >
            <span
              className="material-symbols-outlined text-[40px]"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              {icon}
            </span>

            <span className="mt-0.5 text-[10px] font-bold uppercase tracking-tighter">
              {label}
            </span>
          </button>
        </div>

        {/* End call */}
        <button
          type="button"
          onClick={!isIdle ? onClick : undefined}
          disabled={isIdle}
          title="Finalizar sesión"
          aria-label="Finalizar sesión"
          className="flex h-12 w-12 items-center justify-center rounded-full bg-red-600 text-white shadow-lg transition-all hover:brightness-110 disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <span className="material-symbols-outlined text-[26px]">
            call_end
          </span>
        </button>
      </div>
    </div>
  );
}