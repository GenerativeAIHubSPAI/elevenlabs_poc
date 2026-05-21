import { FileUpload } from "../features/upload/index.js";

export default function Sidebar({ isOpen, onToggle }) {
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
              <div>
                <label className="block text-[11px] font-bold text-[#565e74] uppercase mb-1">
                  Response Tone
                </label>
                <select className="w-full bg-white border border-[#c7c4d7] rounded-lg text-sm py-2 px-3 focus:outline-none focus:ring-1 focus:ring-[#4f5f76]">
                  <option>Professional &amp; Empathetic</option>
                  <option>Direct &amp; Technical</option>
                  <option>Casual &amp; Friendly</option>
                </select>
              </div>
              <div>
                <label className="block text-[11px] font-bold text-[#565e74] uppercase mb-1">
                  Knowledge Base Sync
                </label>
                <div className="flex items-center justify-between p-3 bg-white rounded-lg border border-[#c7c4d7]">
                  <span className="text-sm font-medium text-[#191c1e]">Real-time CRM Access</span>
                  <div className="w-10 h-5 bg-[#4f5f76] rounded-full relative cursor-pointer shrink-0">
                    <div className="absolute right-0.5 top-0.5 w-4 h-4 bg-white rounded-full shadow-sm" />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Instructions / Upload */}
          <div className="px-6 pb-6 flex-1 flex flex-col">
            <h3 className="text-sm font-bold text-[#4f5f76] mb-3">Instructions</h3>
            <FileUpload />
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-[#c7c4d7] bg-[#f2f4f6]">
          <button className="w-full py-3 bg-[#4f5f76] text-white font-bold rounded-xl hover:brightness-110 transition-all shadow-lg active:scale-95 flex items-center justify-center gap-2">
            <span className="material-symbols-outlined">save</span>
            Save Changes
          </button>
        </div>
      </aside>
  );
}
