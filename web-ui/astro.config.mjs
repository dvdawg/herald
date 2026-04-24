import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";

const apiTarget = process.env.HERALD_API_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  server: {
    port: Number(process.env.HERALD_WEB_UI_PORT ?? 4321),
    host: true
  },
  vite: {
    plugins: [tailwindcss()],
    server: {
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true
        }
      }
    }
  }
});
