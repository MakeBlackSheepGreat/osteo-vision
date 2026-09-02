const test = require("node:test");
const assert = require("node:assert/strict");

const {
  isTrustedRendererOrigin,
  mediaPermissionAllowed,
  registerMediaPermissions,
} = require("../desktopPermissions.cjs");

test("desktop media permission is limited to the packaged file renderer", () => {
  assert.equal(isTrustedRendererOrigin("file:///C:/Program%20Files/Osteo%20Vision/index.html"), true);
  assert.equal(isTrustedRendererOrigin("http://127.0.0.1:8001"), false);
  assert.equal(mediaPermissionAllowed({ getURL: () => "file:///C:/app/index.html" }, "media", ""), true);
  assert.equal(mediaPermissionAllowed({ getURL: () => "file:///C:/app/index.html" }, "notifications", ""), false);
});

test("desktop session receives matching check and request handlers", () => {
  let checkHandler;
  let requestHandler;
  const logs = [];
  registerMediaPermissions(
    {
      setPermissionCheckHandler(handler) {
        checkHandler = handler;
      },
      setPermissionRequestHandler(handler) {
        requestHandler = handler;
      },
    },
    (message) => logs.push(message),
  );

  assert.equal(checkHandler({ getURL: () => "file:///C:/app/index.html" }, "media", "file:///C:/app/index.html"), true);
  let granted;
  requestHandler({ getURL: () => "https://unsafe.example" }, "media", (value) => { granted = value; }, {
    requestingUrl: "https://unsafe.example",
  });
  assert.equal(granted, false);
  assert.equal(logs.length, 2);
});
