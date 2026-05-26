import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5178,
    proxy: {
      "/api": "http://localhost:8010",
      "/review-workspace-static": "http://localhost:8010",
    },
  },
});
