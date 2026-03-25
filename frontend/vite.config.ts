import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const apiTarget =
  process.env.VITE_API_URL ||
  `http://127.0.0.1:${process.env.VITE_API_PORT || "8000"}`;

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    host: true,
    proxy: {
      "/api": apiTarget,
    },
  },
});
