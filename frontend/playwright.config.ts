import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(frontendRoot, "..");
const backendPort = Number(process.env.OSTEO_E2E_BACKEND_PORT ?? "18991");
const frontendPort = Number(process.env.OSTEO_E2E_FRONTEND_PORT ?? "15191");
const e2eRunId = process.env.OSTEO_E2E_RUN_ID ?? String(Date.now());
const e2eWorkspace = path.join(repoRoot, ".pytest_tmp", "playwright", e2eRunId);
const e2eArtifactRoot = path.join(e2eWorkspace, "artifacts");

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.pw.ts",
  fullyParallel: false,
  retries: 0,
  timeout: 90_000,
  expect: {
    timeout: 15_000,
  },
  outputDir: "test-results",
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer: [
    {
      command: `conda run -n osteo-vision python -m uvicorn backend.src.api.app:app --host 127.0.0.1 --port ${backendPort}`,
      cwd: repoRoot,
      env: {
        OSTEO_BACKEND_PORT: String(backendPort),
        OSTEO_FRONTEND_PORT: String(frontendPort),
        OSTEO_ARTIFACT_ROOT: e2eArtifactRoot,
        OSTEO_CASE_STORE_PATH: path.join(e2eWorkspace, "cases.sqlite"),
        OSTEO_JOB_STORE_PATH: path.join(e2eWorkspace, "jobs", "jobs.json"),
        OSTEO_ALLOWED_ORIGINS: `http://127.0.0.1:${frontendPort},http://localhost:${frontendPort}`,
      },
      url: `http://127.0.0.1:${backendPort}/ready`,
      timeout: 120_000,
      reuseExistingServer: false,
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${frontendPort}`,
      cwd: frontendRoot,
      env: {
        OSTEO_BACKEND_PORT: String(backendPort),
        OSTEO_FRONTEND_PORT: String(frontendPort),
        VITE_OSTEO_API_URL: `http://127.0.0.1:${backendPort}`,
      },
      url: `http://127.0.0.1:${frontendPort}`,
      timeout: 120_000,
      reuseExistingServer: false,
    },
  ],
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1000 } },
    },
  ],
});
