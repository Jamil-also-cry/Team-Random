import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite proxies /api/* -> http://localhost:8000 so the React dev server
// can POST to Django without touching Django's settings, CORS, or URLs.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
