import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // IPv4 so Playwright (127.0.0.1) and Linux CI agree; "localhost" can be IPv6-only.
  server: { host: "127.0.0.1", port: 5173 },
});
