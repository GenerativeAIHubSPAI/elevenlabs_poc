import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { viteStaticCopy } from "vite-plugin-static-copy";

const BACKEND_URL = process.env.VITE_BACKEND_URL || "http://localhost:8000";

export default defineConfig({
  base: (process.env.VITE_API_PREFIX || "").replace(/\/+$/, "") + "/",
  plugins: [
    tailwindcss(),
    react(),
    viteStaticCopy({
      targets: [
        {
          src: "node_modules/onnxruntime-web/dist/*.wasm",
          dest: ".",
        },
        {
          src: "node_modules/@ricky0123/vad-react/node_modules/@ricky0123/vad-web/dist/silero_vad.onnx",
          dest: ".",
        },
        {
          src: "node_modules/@ricky0123/vad-react/node_modules/@ricky0123/vad-web/dist/vad.worklet.bundle.min.js",
          dest: ".",
        },
      ],
    }),
  ],
  optimizeDeps: {
    exclude: ["onnxruntime-web"],
  },
  server: {
    port: 3000,
    host: true,
    proxy: {
      // Backend routers: /chat (incl. WS /chat/voice-stream), /voice, /kb, /tts, /stt.
      // Only needed in dev; in deployment both sit behind the same origin via VITE_API_PREFIX.
      "/chat": { target: BACKEND_URL, changeOrigin: true, ws: true },
      "/voice": { target: BACKEND_URL, changeOrigin: true },
      "/kb": { target: BACKEND_URL, changeOrigin: true },
      "/tts": { target: BACKEND_URL, changeOrigin: true },
      "/stt": { target: BACKEND_URL, changeOrigin: true },
      "/health": { target: BACKEND_URL, changeOrigin: true },
    },
    headers: {
      "Cross-Origin-Opener-Policy": "same-origin",
      "Cross-Origin-Embedder-Policy": "require-corp",
    },
  },
});
