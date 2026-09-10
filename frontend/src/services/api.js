const API_PREFIX = (import.meta.env.VITE_API_PREFIX ?? "").replace(/\/+$/, "");
const VOICE_TURN_URL = `${API_PREFIX}/voice/turn`;
const KB_INGEST_FILE_URL = `${API_PREFIX}/kb/ingest-pdf`;

function encodeWav(samples, sr) {
  const buf = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buf);
  const s = (o, v) => {
    for (let i = 0; i < v.length; i++) view.setUint8(o + i, v.charCodeAt(i));
  };
  const pcm = new Int16Array(samples.length);
  for (let i = 0; i < samples.length; i++)
    pcm[i] = Math.max(-1, Math.min(1, samples[i])) * 0x7fff;
  s(0, "RIFF");
  view.setUint32(4, 36 + pcm.byteLength, true);
  s(8, "WAVE");
  s(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sr, true);
  view.setUint32(28, sr * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  s(36, "data");
  view.setUint32(40, pcm.byteLength, true);
  new Int16Array(buf, 44).set(pcm);
  return buf;
}

// The backend raises HTTPException with either a plain string detail or a
// structured one ({ code, provider, message }). Passing the object straight to
// Error() renders "[object Object]" in the UI, hiding the actual cause.
function describeError(payload, status) {
  const detail = payload?.detail;

  if (typeof detail === "string" && detail) return detail;
  if (typeof detail?.message === "string" && detail.message) return detail.message;

  return `Error ${status}`;
}

export async function uploadFile(file, namespace = "default") {
  const form = new FormData();
  form.append("file", file);
  form.append("namespace", namespace);
  const res = await fetch(KB_INGEST_FILE_URL, { method: "POST", body: form });
  if (!res.ok) {
    const payload = await res.json().catch(() => null);
    throw new Error(describeError(payload, res.status));
  }
  return res.json();
}

export async function sendAudio(samples, sr) {
  const form = new FormData();
  form.append(
    "file",
    new Blob([encodeWav(samples, sr)], { type: "audio/wav" }),
    "speech.wav"
  );
  const res = await fetch(VOICE_TURN_URL, { method: "POST", body: form });
  if (!res.ok) throw new Error(`Error ${res.status}: ${await res.text()}`);
  return res;
}

export async function fetchStaticKnowledgeSources() {
  const url = `${API_PREFIX}/kb/static-sources`;
  const res = await fetch(url);

  if (!res.ok) {
    const detail = (await res.text().catch(() => "")).slice(0, 200);
    throw new Error(`GET ${url} -> ${res.status}. ${detail}`);
  }

  // res.ok is not enough: when the deployed path prefix does not match the one
  // baked into this bundle, nginx/CloudFront answers the SPA's index.html with a
  // 200 and the request never reaches the backend. Say so instead of surfacing an
  // opaque JSON parse error.
  const body = await res.text();

  try {
    return JSON.parse(body);
  } catch {
    const contentType = res.headers.get("content-type") ?? "an unknown content type";
    throw new Error(
      `GET ${url} returned ${contentType} instead of JSON, so it never reached the ` +
        `backend. Check that the runtime path prefix matches the build. ` +
        `Body starts with: ${body.slice(0, 60)}`
    );
  }
}