import { FileUpload } from "../features/upload/index.js";

const CONFIG_OPTIONS = {
  idioma: [
    { value: "spa", label: "Spanish" },
    { value: "eng", label: "English" },
  ],
  sexo: [
    { value: "hombre", label: "Male"   },
    { value: "mujer",  label: "Female" },
  ],
  tono: [
    { value: "cercano",  label: "Friendly"  },
    { value: "energico", label: "Energetic" },
    { value: "serio",    label: "Formal"    },
  ],
};

export default function Sidebar({ isOpen, onToggle, config, onConfigChange }) {
  return (
    <aside
        className={`h-full w-80 fixed right-0 top-0 z-50 flex flex-col shadow-sm bg-white border-l border-[#c7c4d7] panel-transition ${
          !isOpen ? "translate-x-full" : ""
        }`}
      >
        {/* Brand header */}
        <div className="p-6 flex items-center gap-3 border-b border-[#c7c4d7]">
          <div className="w-10 h-10 rounded-lg bg-[#4f5f76] flex items-center justify-center text-white shrink-0">
            <span className="material-symbols-outlined">settings_voice</span>
          </div>
          <div className="flex-1">
            <h1 className="text-[18px] font-bold text-[#4f5f76]">VoiceCopilot AI</h1>
            <p className="text-[10px] text-[#565e74] uppercase tracking-wider">POC Monitoring Agent</p>
          </div>
          <button
            onClick={onToggle}
            className="w-8 h-8 rounded-full flex items-center justify-center text-[#565e74] hover:bg-[#f2f4f6] hover:text-[#191c1e] transition-all shrink-0"
          >
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 flex flex-col overflow-y-auto custom-scrollbar">
          {/* Configuration */}
          <div className="p-6 space-y-4">
            <h3 className="text-sm font-bold text-[#4f5f76]">Configuration</h3>
            <div className="space-y-4 bg-white p-3 rounded-xl border border-[#c7c4d7]/40">

              {/* Language */}
              <div>
                <label className="block text-[11px] font-bold text-[#565e74] uppercase mb-1">
                  Language
                </label>
                <select
                  value={config.idioma}
                  onChange={(e) => onConfigChange("idioma", e.target.value)}
                  className="w-full bg-white border border-[#c7c4d7] rounded-lg text-sm py-2 px-3 focus:outline-none focus:ring-1 focus:ring-[#4f5f76]"
                >
                  {CONFIG_OPTIONS.idioma.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>

              {/* Gender */}
              <div>
                <label className="block text-[11px] font-bold text-[#565e74] uppercase mb-1">
                  Gender
                </label>
                <select
                  value={config.sexo}
                  onChange={(e) => onConfigChange("sexo", e.target.value)}
                  className="w-full bg-white border border-[#c7c4d7] rounded-lg text-sm py-2 px-3 focus:outline-none focus:ring-1 focus:ring-[#4f5f76]"
                >
                  {CONFIG_OPTIONS.sexo.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>

              {/* Tone */}
              <div>
                <label className="block text-[11px] font-bold text-[#565e74] uppercase mb-1">
                  Tone
                </label>
                <select
                  value={config.tono}
                  onChange={(e) => onConfigChange("tono", e.target.value)}
                  className="w-full bg-white border border-[#c7c4d7] rounded-lg text-sm py-2 px-3 focus:outline-none focus:ring-1 focus:ring-[#4f5f76]"
                >
                  {CONFIG_OPTIONS.tono.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>

            </div>
          </div>

          {/* Instructions / Upload */}
          <div className="px-6 pb-6 flex-1 flex flex-col">
            <h3 className="text-sm font-bold text-[#4f5f76] mb-3">Instructions</h3>
            <FileUpload />
          </div>
        </div>

      </aside>
  );
}
