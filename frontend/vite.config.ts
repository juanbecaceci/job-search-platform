import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// Dev server proxies /api → the FastAPI backend so the SPA talks to it without
// CORS fuss. SSE endpoints (/api/jobs/{id}/events, chat) stream through the
// proxy too. Override the target with API_PROXY_TARGET (and the port with
// VITE_DEV_PORT) to point a dev server at a second backend — e.g. one running
// on a throwaway copy of the DB — without editing this file.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    port: Number(process.env.VITE_DEV_PORT ?? 5173),
    proxy: {
      "/api": {
        target: process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
