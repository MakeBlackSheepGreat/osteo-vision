import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

function runtimeBasePath(): string {
  const configured = process.env.VITE_OSTEO_THREE_D_RUNTIME_BASE?.trim();
  if (!configured || configured === "/") return "/";
  if (configured === "./") return "./";
  if (!configured.startsWith("/")) return "/";
  return configured.endsWith("/") ? configured : `${configured}/`;
}

export default defineConfig(() => {
  const port = Number(process.env.OSTEO_THREE_D_RUNTIME_PORT ?? "5175");

  return {
    base: runtimeBasePath(),
    plugins: [vue()],
    server: {
      host: "127.0.0.1",
      port,
      strictPort: true,
    },
    test: {
      environment: "jsdom",
      globals: true,
    },
  };
});
