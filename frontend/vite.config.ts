import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig(() => {
  const port = Number(process.env.OSTEO_FRONTEND_PORT ?? "5174");
  const backendPort = Number(process.env.OSTEO_BACKEND_PORT ?? "8001");
  const desktopBuild = process.env.VITE_OSTEO_DESKTOP === "true";

  return {
    base: desktopBuild ? "./" : "/",
    plugins: [vue()],
    server: {
      host: "127.0.0.1",
      port,
      strictPort: true,
      proxy: {
        "/api": {
          target: `http://127.0.0.1:${backendPort}`,
          changeOrigin: true,
        },
      },
    },
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
    test: {
      environment: "jsdom",
      globals: true,
      include: ["tests/**/*.test.ts"],
      exclude: ["**/three-d-runtime/**"],
    },
  };
});
