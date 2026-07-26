const { EventEmitter } = require("node:events");
const test = require("node:test");
const assert = require("node:assert/strict");

const { registerDesktopLifecycle } = require("../desktopLifecycle.cjs");

class FakeApp extends EventEmitter {
  quit() {
    const event = { prevented: false, preventDefault() { this.prevented = true; } };
    this.emit("before-quit", event);
    this.quitEvents = (this.quitEvents || 0) + 1;
    return event;
  }
}

test("closing the final desktop window shuts down the backend before application exit", async () => {
  const app = new FakeApp();
  let shutdownCalls = 0;
  registerDesktopLifecycle({
    app,
    shutdown: async () => {
      shutdownCalls += 1;
    },
  });

  app.emit("window-all-closed");
  await new Promise((resolve) => setImmediate(resolve));
  await new Promise((resolve) => setImmediate(resolve));

  assert.equal(shutdownCalls, 1);
  assert.equal(app.quitEvents, 2);
});
