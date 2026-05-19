export function createChatLog(containerEl) {
  function append(role, text) {
    const div = document.createElement("div");
    div.className = `msg ${role}`;
    div.textContent = text;
    containerEl.appendChild(div);
    containerEl.scrollTop = containerEl.scrollHeight;
  }

  return { append };
}
