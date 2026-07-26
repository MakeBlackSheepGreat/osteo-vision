const { execFile, spawn } = require("node:child_process");

function startManagedBackend({ executable, args = [], env, cwd, spawnImpl = spawn }) {
  return spawnImpl(executable, args, {
    cwd,
    env,
    shell: false,
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });
}

async function waitForBackendReady({ url, timeoutMs = 30000, intervalMs = 250, fetchImpl = fetch }) {
  const deadline = Date.now() + timeoutMs;
  let lastError = "backend did not respond";
  while (Date.now() < deadline) {
    try {
      const response = await fetchImpl(url);
      if (response.ok) {
        return;
      }
      lastError = `backend returned HTTP ${response.status}`;
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
    }
    await delay(intervalMs);
  }
  throw new Error(`Backend readiness timed out: ${lastError}`);
}

async function terminateProcessTree(child, { graceMs = 5000, execFileImpl = execFile } = {}) {
  if (!child || !child.pid || child.exitCode !== null) {
    return { attempted: false, forced: false };
  }

  try {
    child.kill("SIGTERM");
  } catch {
    // The child may have exited between the state check and signal delivery.
  }
  if (await waitForExit(child, graceMs)) {
    return { attempted: true, forced: false };
  }

  await runTaskkill(child.pid, execFileImpl);
  await waitForExit(child, 2000);
  return { attempted: true, forced: true };
}

function runTaskkill(pid, execFileImpl) {
  return new Promise((resolve) => {
    execFileImpl("taskkill.exe", ["/PID", String(pid), "/T", "/F"], { windowsHide: true }, () => resolve());
  });
}

function waitForExit(child, timeoutMs) {
  if (child.exitCode !== null) {
    return Promise.resolve(true);
  }
  return new Promise((resolve) => {
    const finish = () => {
      clearTimeout(timer);
      child.removeListener("exit", finish);
      child.removeListener("error", finish);
      resolve(true);
    };
    const timer = setTimeout(() => {
      child.removeListener("exit", finish);
      child.removeListener("error", finish);
      resolve(child.exitCode !== null);
    }, timeoutMs);
    child.once("exit", finish);
    child.once("error", finish);
  });
}

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

module.exports = {
  startManagedBackend,
  terminateProcessTree,
  waitForBackendReady,
};
