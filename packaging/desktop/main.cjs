const { app, BrowserWindow, dialog, session } = require("electron");
const { appendFileSync, existsSync, mkdirSync } = require("node:fs");
const { join } = require("node:path");

const { registerDesktopLifecycle } = require("./desktopLifecycle.cjs");
const { registerMediaPermissions } = require("./desktopPermissions.cjs");
const { startManagedBackend, terminateProcessTree, waitForBackendReady } = require("./runtimeSupervisor.cjs");
const { startRuntimeServer, stopRuntimeServer } = require("./runtimeServer.cjs");

const BACKEND_PORT = 8001;
const THREE_D_RUNTIME_PORT = 5175;
let backendChild = null;
let threeDRuntimeServer = null;
let logFile = "";

function writeLog(message) {
  const line = `${new Date().toISOString()} ${message}\n`;
  if (logFile) {
    appendFileSync(logFile, line, { encoding: "utf8" });
  }
}

function packagedResourcesRoot() {
  return app.isPackaged ? process.resourcesPath : join(__dirname, "development-resources");
}

function backendExecutable(resourcesRoot) {
  return join(resourcesRoot, "backend", "osteo-vision-api.exe");
}

function backendEnvironment(resourcesRoot) {
  const runtimeAssets = join(resourcesRoot, "runtime_assets");
  const runtimeTools = join(runtimeAssets, "runtime_tools");
  const userArtifacts = join(app.getPath("userData"), "artifacts");
  return {
    ...process.env,
    Path: `${runtimeTools};${process.env.Path || ""}`,
    OSTEO_PROJECT_ROOT: runtimeAssets,
    OSTEO_ARTIFACT_ROOT: userArtifacts,
    OSTEO_CASE_STORE_PATH: join(userArtifacts, "cases.sqlite"),
    OSTEO_ANNOTATION_STORE_PATH: join(userArtifacts, "manual_annotations", "annotations.sqlite"),
    OSTEO_PROMOTION_APPROVAL_STORE_PATH: join(userArtifacts, "promotion_approvals", "approvals.sqlite"),
    OSTEO_JOB_STORE_PATH: join(userArtifacts, "jobs", "jobs.json"),
    OSTEO_INFERENCE_CONFIG: join(runtimeAssets, "configs", "inference", "osteo_vision_competition_strict.yml"),
    OSTEO_VIDEO_MANIFEST_PATH: join(runtimeAssets, "demo_data", "ofdvdnet", "ofdvdnet_demo_manifest.csv"),
    OSTEO_OFDVD_MANIFEST_PATH: join(runtimeAssets, "demo_data", "ofdvdnet", "ofdvdnet_demo_manifest.csv"),
    OSTEO_BACKEND_PORT: String(BACKEND_PORT),
    OSTEO_FRONTEND_PORT: "0",
    OSTEO_ALLOWED_ORIGINS: "file://,null,http://127.0.0.1:5175,http://localhost:5175",
  };
}

async function shutdownBackend() {
  const result = await terminateProcessTree(backendChild);
  writeLog(`Backend shutdown attempted=${result.attempted} forced=${result.forced}`);
  backendChild = null;
  if (threeDRuntimeServer) {
    const server = threeDRuntimeServer;
    threeDRuntimeServer = null;
    await stopRuntimeServer(server);
    writeLog("Three-dimensional runtime server stopped");
  }
}

async function startApplication() {
  const logsDir = app.getPath("logs");
  mkdirSync(logsDir, { recursive: true });
  logFile = join(logsDir, "desktop-runtime.log");
  registerMediaPermissions(session.defaultSession, writeLog);
  const resourcesRoot = packagedResourcesRoot();
  const executable = backendExecutable(resourcesRoot);
  if (!existsSync(executable)) {
    throw new Error(`Packaged backend executable is missing: ${executable}`);
  }

  backendChild = startManagedBackend({
    executable,
    cwd: join(resourcesRoot, "runtime_assets"),
    env: backendEnvironment(resourcesRoot),
  });
  backendChild.stdout.on("data", (chunk) => writeLog(`[backend] ${String(chunk).trim()}`));
  backendChild.stderr.on("data", (chunk) => writeLog(`[backend] ${String(chunk).trim()}`));
  backendChild.on("exit", (code, signal) => writeLog(`Backend exited code=${code} signal=${signal}`));

  await waitForBackendReady({ url: `http://127.0.0.1:${BACKEND_PORT}/ready` });
  const threeDRuntimeRoot = join(resourcesRoot, "three_d_runtime");
  threeDRuntimeServer = startRuntimeServer({ root: threeDRuntimeRoot, port: THREE_D_RUNTIME_PORT });
  writeLog(`Three-dimensional runtime server started at http://127.0.0.1:${THREE_D_RUNTIME_PORT}`);
  const window = new BrowserWindow({
    width: 1500,
    height: 980,
    minWidth: 1180,
    minHeight: 760,
    // Show immediately; waiting solely for ready-to-show can leave the packaged
    // window invisible on machines where the renderer delays that event.
    show: true,
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  window.webContents.on("render-process-gone", (_event, details) => {
    writeLog(`Renderer exited: ${details.reason}`);
    app.quit();
  });
  await window.loadFile(join(resourcesRoot, "frontend", "index.html"));
  window.show();
}

registerDesktopLifecycle({ app, shutdown: shutdownBackend, log: writeLog });

app.whenReady().then(startApplication).catch(async (error) => {
  writeLog(`Startup failed: ${error instanceof Error ? error.stack || error.message : String(error)}`);
  await shutdownBackend();
  dialog.showErrorBox("Osteo Vision startup failed", error instanceof Error ? error.message : String(error));
  app.exit(1);
});
