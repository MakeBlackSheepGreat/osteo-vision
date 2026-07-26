const { EventEmitter } = require("node:events");
const test = require("node:test");
const assert = require("node:assert/strict");

const { terminateProcessTree, waitForBackendReady } = require("../runtimeSupervisor.cjs");

test("terminates a managed backend gracefully before forcing the process tree", async () => {
  const child = new EventEmitter();
  child.pid = 4321;
  child.exitCode = null;
  child.kill = () => {
    child.exitCode = 0;
    child.emit("exit", 0, "SIGTERM");
    return true;
  };
  let taskkillCalled = false;

  const result = await terminateProcessTree(child, {
    graceMs: 10,
    execFileImpl: () => {
      taskkillCalled = true;
    },
  });

  assert.deepEqual(result, { attempted: true, forced: false });
  assert.equal(taskkillCalled, false);
});

test("forces the Windows process tree after the graceful shutdown timeout", async () => {
  const child = new EventEmitter();
  child.pid = 4322;
  child.exitCode = null;
  child.kill = () => true;
  let taskkillArgs = null;

  const result = await terminateProcessTree(child, {
    graceMs: 1,
    execFileImpl: (_command, args, _options, callback) => {
      taskkillArgs = args;
      child.exitCode = 1;
      child.emit("exit", 1, "SIGKILL");
      callback(null);
    },
  });

  assert.deepEqual(result, { attempted: true, forced: true });
  assert.deepEqual(taskkillArgs, ["/PID", "4322", "/T", "/F"]);
});

test("waits until the backend readiness endpoint returns success", async () => {
  let calls = 0;
  await waitForBackendReady({
    url: "http://127.0.0.1:8001/ready",
    timeoutMs: 100,
    intervalMs: 1,
    fetchImpl: async () => {
      calls += 1;
      return { ok: calls === 2, status: calls === 2 ? 200 : 503 };
    },
  });
  assert.equal(calls, 2);
});
