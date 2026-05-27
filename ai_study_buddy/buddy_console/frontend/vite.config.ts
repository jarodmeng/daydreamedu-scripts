import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // Bind IPv4 explicitly so README/deep-link URLs using 127.0.0.1 work on macOS
    // (default "localhost" can be IPv6-only, which rejects 127.0.0.1).
    host: "127.0.0.1",
    port: 5178,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8010",
        timeout: 300_000,
      },
      "/review-workspace-static": "http://127.0.0.1:8010",
    },
  },
  preview: {
    host: "127.0.0.1",
    port: 5178,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8010",
        timeout: 300_000,
      },
      "/review-workspace-static": "http://127.0.0.1:8010",
    },
  },
});
