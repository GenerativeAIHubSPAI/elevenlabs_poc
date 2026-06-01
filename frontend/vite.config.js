import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { viteStaticCopy } from "vite-plugin-static-copy";

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
    headers: {
      "Cross-Origin-Opener-Policy": "same-origin",
      "Cross-Origin-Embedder-Policy": "require-corp",
    },
  },
});
