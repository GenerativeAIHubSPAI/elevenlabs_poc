import { useState } from "react";

const HELP_STEPS = [
  {
    icon: "keyboard_voice",
    title: "Iniciar conversación",
    desc: "Pulsa el botón central para comenzar. El sistema detectará tu voz automáticamente.",
  },
  {
    icon: "hearing",
    title: "Habla con naturalidad",
    desc: "No hace falta mantener pulsado nada. Cuando dejes de hablar, el asistente procesará tu mensaje.",
  },
  {
    icon: "call_end",
    title: "Finalizar llamada",
    desc: "Usa el botón rojo para terminar la sesión en cualquier momento.",
  },
  {
    icon: "notes",
    title: "Ver transcripción",
    desc: "Pulsa el botón superior derecho del panel para alternar entre el visualizador y el historial de mensajes.",
  },
  {
    icon: "settings",
    title: "Configuración",
    desc: "Abre el panel lateral con el icono de ajustes para cambiar el tono de respuesta y subir documentos de contexto.",
  },
];

export default function TopAppBar({ sidebarOpen, onToggleSidebar }) {
  const [helpOpen, setHelpOpen] = useState(false);

  return (
    <>
      <header
        className={`fixed top-0 left-0 h-16 z-40 flex justify-between items-center px-6 bg-white/80 backdrop-blur-md shadow-sm border-b border-[#c7c4d7]/30 panel-transition ${
          sidebarOpen ? "right-80" : "right-0"
        }`}
      >
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-extrabold text-[#4f5f76]">Workspace Monitoring</h2>
          <span className="px-3 py-1 bg-[#eceef0] text-[#565e74] rounded-full text-xs font-bold uppercase tracking-wider">
            Live View
          </span>
        </div>

        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-green-500" />
            <span className="text-sm font-medium text-[#565e74]">Available</span>
          </div>

          <div className="flex items-center gap-3 border-x border-[#c7c4d7] px-6">
            <button
              onClick={() => setHelpOpen(true)}
              className="material-symbols-outlined text-[#565e74] hover:text-[#4f5f76] transition-colors"
            >
              help_outline
            </button>
            <button
              onClick={onToggleSidebar}
              className={`material-symbols-outlined transition-colors ${
                sidebarOpen ? "text-[#4f5f76]" : "text-[#565e74] hover:text-[#4f5f76]"
              }`}
            >
              settings
            </button>
          </div>

          <div className="w-10 h-10 rounded-full bg-[#4f5f76] flex items-center justify-center text-white font-bold text-sm shrink-0">
            AG
          </div>
        </div>
      </header>

      {/* Help modal */}
      {helpOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm"
          onClick={() => setHelpOpen(false)}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6 flex flex-col gap-5"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-[#191c1e]">Cómo usar VoiceCopilot AI</h2>
              <button
                onClick={() => setHelpOpen(false)}
                className="w-8 h-8 rounded-full flex items-center justify-center text-[#565e74] hover:bg-[#f2f4f6] transition-colors"
              >
                <span className="material-symbols-outlined text-[20px]">close</span>
              </button>
            </div>

            <ol className="flex flex-col gap-4">
              {HELP_STEPS.map((step, i) => (
                <li key={i} className="flex items-start gap-4">
                  <div className="w-9 h-9 rounded-xl bg-[#eceef0] flex items-center justify-center shrink-0">
                    <span
                      className="material-symbols-outlined text-[20px] text-[#4f5f76]"
                      style={{ fontVariationSettings: "'FILL' 1" }}
                    >
                      {step.icon}
                    </span>
                  </div>
                  <div>
                    <p className="text-sm font-bold text-[#191c1e]">{step.title}</p>
                    <p className="text-sm text-[#565e74] leading-relaxed">{step.desc}</p>
                  </div>
                </li>
              ))}
            </ol>

            <button
              onClick={() => setHelpOpen(false)}
              className="w-full py-2.5 bg-[#4f5f76] text-white font-bold rounded-xl hover:brightness-110 transition-all active:scale-95"
            >
              Entendido
            </button>
          </div>
        </div>
      )}
    </>
  );
}
