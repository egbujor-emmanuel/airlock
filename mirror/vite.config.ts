import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, /api goes to the Python Mirror API (uv run airlock-mirror).
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8787" } },
});
