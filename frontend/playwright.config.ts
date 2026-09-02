import { defineConfig, devices } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(frontendRoot, "..");
const backendPort = Number(process.env.OSTEO_E2E_BACKEND_PORT ?? "18991");
const frontendPort = Number(process.env.OSTEO_E2E_FRONTEND_PORT ?? "15191");
const threeDRuntimePort = Number(process.env.OSTEO_E2E_THREE_D_RUNTIME_PORT ?? "15192");
const threeDRuntimeRoot = path.join(frontendRoot, "three-d-runtime");
const e2eRunId = process.env.OSTEO_E2E_RUN_ID ?? String(Date.now());
process.env.OSTEO_E2E_RUN_ID = e2eRunId;
const e2eWorkspace = path.join(repoRoot, ".pytest_tmp", "playwright", e2eRunId);
const e2eArtifactRoot = path.join(e2eWorkspace, "artifacts");
const e2eOfdvdManifestPath = path.join(
  repoRoot,
  ".pytest_tmp",
  "playwright",
  "fixtures",
  "ofdvdnet_e2e_manifest.csv",
);
const d024RuntimeFixturePath = path.join(
  e2eArtifactRoot,
  "three_d_runtime",
  "references",
  "d024",
  "mandible_d024_0001.stl",
);
const e2ePhysicianToken = "playwright-physician-token-20260715";
const e2eIndependentPhysicianToken = "playwright-independent-physician-token-20260719";
const e2eInferenceConfig = path.resolve(
  repoRoot,
  process.env.OSTEO_E2E_INFERENCE_CONFIG ?? "configs/inference/osteo_vision_strict.yml",
);
const configuredPython = process.env.OSTEO_E2E_PYTHON?.trim();
const projectPython = path.join(process.env.USERPROFILE ?? "", ".conda", "envs", "osteo-vision", "python.exe");
const backendPython = configuredPython || (fs.existsSync(projectPython) ? projectPython : "python");
const quotedBackendPython = `"${backendPython.replaceAll('"', '\\"')}"`;

function writeD024RuntimeFixture(): void {
  fs.mkdirSync(path.dirname(d024RuntimeFixturePath), { recursive: true });
  fs.writeFileSync(
    d024RuntimeFixturePath,
    [
      "solid osteo_vision_e2e_d024",
      "facet normal 0 0 1",
      "outer loop",
      "vertex 0 0 0",
      "vertex 48 0 0",
      "vertex 0 32 0",
      "endloop",
      "endfacet",
      "facet normal 0 0 1",
      "outer loop",
      "vertex 48 0 0",
      "vertex 48 32 0",
      "vertex 0 32 0",
      "endloop",
      "endfacet",
      "endsolid osteo_vision_e2e_d024",
      "",
    ].join("\n"),
    "utf8",
  );
}

// The runtime API resolves D024 from the isolated artifact volume, so E2E never
// relies on an ignored local reference asset or a developer workstation state.
writeD024RuntimeFixture();

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.pw.ts",
  fullyParallel: false,
  workers: 1,
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
      command: `${quotedBackendPython} -m uvicorn backend.osteo_vision_api.api.app:app --host 127.0.0.1 --port ${backendPort}`,
      cwd: repoRoot,
      env: {
        OSTEO_BACKEND_PORT: String(backendPort),
        OSTEO_FRONTEND_PORT: String(frontendPort),
        OSTEO_THREE_D_RUNTIME_PORT: String(threeDRuntimePort),
        OSTEO_ARTIFACT_ROOT: e2eArtifactRoot,
        OSTEO_CASE_STORE_PATH: path.join(e2eWorkspace, "cases.sqlite"),
        OSTEO_ANNOTATION_STORE_PATH: path.join(e2eWorkspace, "annotations.sqlite"),
        OSTEO_JOB_STORE_PATH: path.join(e2eWorkspace, "jobs", "jobs.json"),
        OSTEO_OFDVD_MANIFEST_PATH: e2eOfdvdManifestPath,
        OSTEO_REVIEW_IDENTITIES_JSON: JSON.stringify({
          [e2ePhysicianToken]: {
            actor_id: "playwright-physician-001",
            role: "physician",
            institution: "Playwright Stomatology Test Center",
            auth_source: "verified_identity_token",
          },
          [e2eIndependentPhysicianToken]: {
            actor_id: "playwright-physician-002",
            role: "physician",
            institution: "Playwright Stomatology Test Center",
            auth_source: "verified_identity_token",
          },
        }),
        OSTEO_INFERENCE_CONFIG: e2eInferenceConfig,
        OSTEO_ALLOWED_ORIGINS: [
          `http://127.0.0.1:${frontendPort}`,
          `http://localhost:${frontendPort}`,
          `http://127.0.0.1:${threeDRuntimePort}`,
          `http://localhost:${threeDRuntimePort}`,
        ].join(","),
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
        VITE_OSTEO_THREE_D_RUNTIME_URL: `http://127.0.0.1:${threeDRuntimePort}`,
        VITE_OSTEO_EXPECT_STRICT_RUNTIME: process.env.OSTEO_E2E_EXPECT_STRICT_RUNTIME ?? "true",
        VITE_OSTEO_DEFAULT_CASE_ID: "",
      },
      url: `http://127.0.0.1:${frontendPort}`,
      timeout: 120_000,
      reuseExistingServer: false,
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${threeDRuntimePort}`,
      cwd: threeDRuntimeRoot,
      env: {
        OSTEO_BACKEND_PORT: String(backendPort),
        OSTEO_THREE_D_RUNTIME_PORT: String(threeDRuntimePort),
        VITE_OSTEO_API_URL: `http://127.0.0.1:${backendPort}`,
        VITE_OSTEO_MAIN_APP_ORIGIN: `http://127.0.0.1:${frontendPort}`,
      },
      url: `http://127.0.0.1:${threeDRuntimePort}/runtime-manifest.json`,
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
