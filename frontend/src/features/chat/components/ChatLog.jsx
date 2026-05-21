import { useEffect, useRef } from "react";

export default function ChatLog({ messages }) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (containerRef.current)
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
  }, [messages]);

  return (
    <div ref={containerRef} className="flex-1 overflow-y-auto flex flex-col gap-4 p-6 custom-scrollbar">
      {messages.map((msg, i) => (
        <div
          key={i}
          className={`flex flex-col gap-1 ${
            msg.role === "user"
              ? "items-end"
              : msg.role === "error"
              ? "items-center"
              : "items-start"
          }`}
        >
          {msg.role !== "error" && (
            <span className={`text-xs font-bold ${msg.role === "user" ? "text-[#565e74]" : "text-[#4f5f76]"}`}>
              {msg.role === "user" ? "User" : "Assistant"}
            </span>
          )}
          <p
            className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
              msg.role === "user"
                ? "bg-[#4f5f76] text-white shadow-sm"
                : msg.role === "assistant"
                ? "bg-[#eceef0] text-[#464554]"
                : "text-red-500 text-xs italic"
            }`}
          >
            {msg.text}
          </p>
        </div>
      ))}
    </div>
  );
}
