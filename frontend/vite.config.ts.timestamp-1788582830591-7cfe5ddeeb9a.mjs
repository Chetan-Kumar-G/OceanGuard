// vite.config.ts
import { defineConfig } from "file:///sessions/rcw-01jwuseokrfduob4adglb5ce/mnt/final%20prototype/frontend/node_modules/vite/dist/node/index.js";
import react from "file:///sessions/rcw-01jwuseokrfduob4adglb5ce/mnt/final%20prototype/frontend/node_modules/@vitejs/plugin-react/dist/index.js";
var vite_config_default = defineConfig({
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
      "/media": "http://127.0.0.1:8000"
    }
  }
});
export {
  vite_config_default as default
};
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcudHMiXSwKICAic291cmNlc0NvbnRlbnQiOiBbImNvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9kaXJuYW1lID0gXCIvc2Vzc2lvbnMvcmN3LTAxand1c2Vva3JmZHVvYjRhZGdsYjVjZS9tbnQvZmluYWwgcHJvdG90eXBlL2Zyb250ZW5kXCI7Y29uc3QgX192aXRlX2luamVjdGVkX29yaWdpbmFsX2ZpbGVuYW1lID0gXCIvc2Vzc2lvbnMvcmN3LTAxand1c2Vva3JmZHVvYjRhZGdsYjVjZS9tbnQvZmluYWwgcHJvdG90eXBlL2Zyb250ZW5kL3ZpdGUuY29uZmlnLnRzXCI7Y29uc3QgX192aXRlX2luamVjdGVkX29yaWdpbmFsX2ltcG9ydF9tZXRhX3VybCA9IFwiZmlsZTovLy9zZXNzaW9ucy9yY3ctMDFqd3VzZW9rcmZkdW9iNGFkZ2xiNWNlL21udC9maW5hbCUyMHByb3RvdHlwZS9mcm9udGVuZC92aXRlLmNvbmZpZy50c1wiO2ltcG9ydCB7IGRlZmluZUNvbmZpZyB9IGZyb20gXCJ2aXRlXCI7XG5pbXBvcnQgcmVhY3QgZnJvbSBcIkB2aXRlanMvcGx1Z2luLXJlYWN0XCI7XG5cbi8vIGh0dHBzOi8vdml0ZS5kZXYvY29uZmlnL1xuZXhwb3J0IGRlZmF1bHQgZGVmaW5lQ29uZmlnKHtcbiAgcGx1Z2luczogW3JlYWN0KCldLFxuICBzZXJ2ZXI6IHtcbiAgICBwb3J0OiA1MTczLFxuICAgIC8vIFByb3h5IEFQSSBjYWxscyB0byB0aGUgRmFzdEFQSSBiYWNrZW5kIGR1cmluZyBkZXYgc28gdGhlIGJyb3dzZXJcbiAgICAvLyBuZXZlciBoYXMgdG8ga25vdyB0aGUgYmFja2VuZCdzIGhvc3QvcG9ydCAoYW5kIENPUlMgaXMgYSBub24taXNzdWUpLlxuICAgIHByb3h5OiB7XG4gICAgICBcIi9hcGlcIjogXCJodHRwOi8vMTI3LjAuMC4xOjgwMDBcIixcbiAgICAgIFwiL2V2ZW50c1wiOiBcImh0dHA6Ly8xMjcuMC4wLjE6ODAwMFwiLFxuICAgICAgXCIvZjFcIjogXCJodHRwOi8vMTI3LjAuMC4xOjgwMDBcIixcbiAgICAgIFwiL2YyXCI6IFwiaHR0cDovLzEyNy4wLjAuMTo4MDAwXCIsXG4gICAgICBcIi9mNVwiOiBcImh0dHA6Ly8xMjcuMC4wLjE6ODAwMFwiLFxuICAgICAgXCIvZjZcIjogXCJodHRwOi8vMTI3LjAuMC4xOjgwMDBcIixcbiAgICAgIFwiL2hlYWx0aFwiOiBcImh0dHA6Ly8xMjcuMC4wLjE6ODAwMFwiLFxuICAgICAgXCIvYXV0aFwiOiBcImh0dHA6Ly8xMjcuMC4wLjE6ODAwMFwiLFxuICAgICAgXCIvYWRtaW5cIjogXCJodHRwOi8vMTI3LjAuMC4xOjgwMDBcIixcbiAgICAgIFwiL2FwcGVhbHNcIjogXCJodHRwOi8vMTI3LjAuMC4xOjgwMDBcIixcbiAgICAgIFwiL21lZGlhXCI6IFwiaHR0cDovLzEyNy4wLjAuMTo4MDAwXCIsXG4gICAgfSxcbiAgfSxcbn0pO1xuIl0sCiAgIm1hcHBpbmdzIjogIjtBQUE2WCxTQUFTLG9CQUFvQjtBQUMxWixPQUFPLFdBQVc7QUFHbEIsSUFBTyxzQkFBUSxhQUFhO0FBQUEsRUFDMUIsU0FBUyxDQUFDLE1BQU0sQ0FBQztBQUFBLEVBQ2pCLFFBQVE7QUFBQSxJQUNOLE1BQU07QUFBQTtBQUFBO0FBQUEsSUFHTixPQUFPO0FBQUEsTUFDTCxRQUFRO0FBQUEsTUFDUixXQUFXO0FBQUEsTUFDWCxPQUFPO0FBQUEsTUFDUCxPQUFPO0FBQUEsTUFDUCxPQUFPO0FBQUEsTUFDUCxPQUFPO0FBQUEsTUFDUCxXQUFXO0FBQUEsTUFDWCxTQUFTO0FBQUEsTUFDVCxVQUFVO0FBQUEsTUFDVixZQUFZO0FBQUEsTUFDWixVQUFVO0FBQUEsSUFDWjtBQUFBLEVBQ0Y7QUFDRixDQUFDOyIsCiAgIm5hbWVzIjogW10KfQo=
