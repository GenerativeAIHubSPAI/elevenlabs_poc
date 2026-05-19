const LABELS = {
  idle:       "Iniciar",
  active:     "Escuchando",
  speaking:   "Hablando",
  processing: "Procesando",
  replying:   "Respondiendo",
};

export function createToggleButton({ btnEl, labelEl, statusEl, liveLabelEl }) {
  function setState(state) {
    btnEl.className      = state;
    labelEl.textContent  = LABELS[state] ?? "Iniciar";
    const text = {
      idle:       "Pulsa para comenzar",
      active:     "Escuchando...",
      speaking:   "Te escucho...",
      processing: "Pensando...",
      replying:   "Respondiendo...",
    }[state] ?? "";
    statusEl.textContent    = text;
    liveLabelEl.textContent = text.toLowerCase();
  }

  function onPress(handler) {
    btnEl.addEventListener("click", handler);
  }

  return { setState, onPress };
}
