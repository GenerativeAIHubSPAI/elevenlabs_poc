const ORCHESTRATOR_URL = "http://localhost:8000/orchestrate";

export const hexDecode = (hex) => hex
  ? new TextDecoder().decode(new Uint8Array(hex.match(/.{1,2}/g).map(b => parseInt(b, 16))))
  : null;

function encodeWav(samples, sr) {
  const buf  = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buf);
  const s    = (o, v) => { for (let i = 0; i < v.length; i++) view.setUint8(o + i, v.charCodeAt(i)); };
  const pcm  = new Int16Array(samples.length);
  for (let i = 0; i < samples.length; i++) pcm[i] = Math.max(-1, Math.min(1, samples[i])) * 0x7fff;
  s(0,"RIFF"); view.setUint32(4,36+pcm.byteLength,true); s(8,"WAVE"); s(12,"fmt ");
  view.setUint32(16,16,true); view.setUint16(20,1,true); view.setUint16(22,1,true);
  view.setUint32(24,sr,true); view.setUint32(28,sr*2,true);
  view.setUint16(32,2,true); view.setUint16(34,16,true);
  s(36,"data"); view.setUint32(40,pcm.byteLength,true);
  new Int16Array(buf,44).set(pcm);
  return buf;
}

export async function sendAudio(samples, sr) {
  const form = new FormData();
  form.append("audio", new Blob([encodeWav(samples, sr)], { type: "audio/wav" }), "speech.wav");
  const res = await fetch(ORCHESTRATOR_URL, { method: "POST", body: form });
  if (!res.ok) throw new Error(`Error ${res.status}: ${await res.text()}`);
  return res;
}
