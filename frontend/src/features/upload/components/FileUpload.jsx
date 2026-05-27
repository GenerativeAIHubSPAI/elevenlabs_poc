import { useRef, useState } from "react";
import { uploadFile } from "../../../services/api.js";

const ACCEPTED = ".pdf";
const ACCEPTED_SET = new Set(["pdf"]);


function statusIcon(status) {
  if (status === "uploading") return "hourglass_empty";
  if (status === "success")   return "check_circle";
  if (status === "error")     return "error";
  return "upload_file";
}

function statusColor(status) {
  if (status === "success") return "text-green-500";
  if (status === "error")   return "text-red-500";
  return "text-[#565e74] group-hover:text-[#4f5f76]";
}

export default function FileUpload({ namespace = "default" }) {
  const inputRef            = useRef(null);
  const [status, setStatus] = useState("idle");
  const [message, setMessage] = useState(null);
  const [isDragging, setIsDragging] = useState(false);

  async function handleFile(file) {
    if (!file) return;

    const ext = file.name.split(".").pop().toLowerCase();
    if (!ACCEPTED_SET.has(ext)) {
      setStatus("error");
      setMessage(`Unsupported type (.${ext}). Only PDF files are accepted.`);
      return;
    }

    setStatus("uploading");
    setMessage(`Uploading ${file.name}...`);

    try {
      const result = await uploadFile(file, namespace);
      setStatus("success");
      setMessage(`${result.ingested_chunks} chunks indexed from "${result.source_name}" (${result.pages_processed} pages)`);
    } catch (e) {
      setStatus("error");
      setMessage(e.message);
    }
  }

  function onDragOver(e) {
    e.preventDefault();
    setIsDragging(true);
  }

  function onDragLeave(e) {
    if (!e.currentTarget.contains(e.relatedTarget)) setIsDragging(false);
  }

  function onDrop(e) {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }

  function onInputChange(e) {
    handleFile(e.target.files?.[0]);
    e.target.value = "";
  }

  function reset() {
    setStatus("idle");
    setMessage(null);
  }

  const isActive = isDragging || status === "uploading";

  return (
    <div
      className={`flex-1 border-2 border-dashed rounded-xl flex flex-col items-center justify-center p-6 text-center transition-colors min-h-[180px] group ${
        isActive
          ? "border-[#4f5f76] bg-[#4f5f76]/5"
          : status === "success"
          ? "border-green-400 bg-green-50"
          : status === "error"
          ? "border-red-400 bg-red-50"
          : "border-[#c7c4d7] bg-white hover:bg-[#4f5f76]/5 hover:border-[#4f5f76] cursor-pointer"
      }`}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      onClick={status === "idle" ? () => inputRef.current?.click() : undefined}
    >
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED}
        className="hidden"
        onChange={onInputChange}
      />

      <span
        className={`material-symbols-outlined text-[32px] mb-3 transition-colors ${statusColor(status)} ${status === "uploading" ? "animate-spin" : ""}`}
      >
        {statusIcon(status)}
      </span>

      {status === "idle" && (
        <>
          <p className="text-sm font-bold text-[#191c1e] mb-1">
            {isDragging ? "Drop the file here" : "Drag & drop or select a file"}
          </p>
          <p className="text-[11px] text-[#565e74] mb-4">PDF · max. 20 MB</p>
          <button
            onClick={(e) => { e.stopPropagation(); inputRef.current?.click(); }}
            className="px-6 py-2 bg-[#eceef0] text-[#565e74] hover:bg-[#4f5f76] hover:text-white rounded-lg text-sm font-bold transition-all"
          >
            Select file
          </button>
        </>
      )}

      {status === "uploading" && (
        <p className="text-sm font-medium text-[#565e74]">{message}</p>
      )}

      {(status === "success" || status === "error") && (
        <>
          <p className={`text-sm font-bold mb-1 ${status === "success" ? "text-green-700" : "text-red-700"}`}>
            {status === "success" ? "Upload complete" : "Upload failed"}
          </p>
          <p className="text-[11px] text-[#565e74] mb-4 px-2">{message}</p>
          <button
            onClick={(e) => { e.stopPropagation(); reset(); }}
            className="px-6 py-2 bg-[#eceef0] text-[#565e74] hover:bg-[#4f5f76] hover:text-white rounded-lg text-sm font-bold transition-all"
          >
            Upload another
          </button>
        </>
      )}
    </div>
  );
}
