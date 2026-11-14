import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import { fileURLToPath } from "node:url";

const rootEnv = fileURLToPath(new URL("../", import.meta.url));

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, rootEnv, "");
  const authUrl = env.VITE_NEON_AUTH_URL || env.NEON_AUTH_BASE_URL || "";
  return {
    plugins: [react()],
    define: { "import.meta.env.VITE_NEON_AUTH_URL": JSON.stringify(authUrl) },
    server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
  };
});