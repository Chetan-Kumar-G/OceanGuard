import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Proxy API calls to the FastAPI backend during dev so the browser
    // never has to know the backend's host/port (and CORS is a non-issue).
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/events": "http://127.0.0.1:8000",
      "/f1": "http://127.0.0.1:8000",
      "/f2": "http://127.0.0.1:8000",
      "/f5": "http://127.0.0.1:8000",
      "/f6": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
      "/auth": "http://127.0.0.1:8000",
      "/admin": "http://127.0.0.1:8000",
      "/appeals": "http://127.0.0.1:8000",
      "/media": "http://127.0.0.1:8000",
    },
  },
});
