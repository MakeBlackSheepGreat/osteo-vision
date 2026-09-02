const { createReadStream, existsSync, statSync } = require("node:fs");
const { createServer } = require("node:http");
const { extname, join, normalize, relative, resolve } = require("node:path");

const CONTENT_TYPES = {
  ".css": "text/css; charset=utf-8",
  ".gif": "image/gif",
  ".html": "text/html; charset=utf-8",
  ".ico": "image/x-icon",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".map": "application/json; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
};

function startRuntimeServer({ root, host = "127.0.0.1", port = 5175, serverFactory = createServer } = {}) {
  const runtimeRoot = resolve(String(root || ""));
  if (!existsSync(runtimeRoot) || !statSync(runtimeRoot).isDirectory()) {
    throw new Error(`Three-dimensional runtime assets are missing: ${runtimeRoot}`);
  }

  const server = serverFactory((request, response) => {
    void serveRequest(request, response, runtimeRoot);
  });
  server.on("error", () => undefined);
  server.listen(port, host);
  return server;
}

async function serveRequest(request, response, runtimeRoot) {
  try {
    const requestUrl = new URL(request.url || "/", "http://runtime.local");
    const pathname = decodeURIComponent(requestUrl.pathname);
    const requested = normalize(join(runtimeRoot, pathname.replace(/^[/\\]+/, "")));
    const relativePath = relative(runtimeRoot, requested);
    if (relativePath.startsWith("..") || relativePath.includes(`..${require("node:path").sep}`)) {
      response.writeHead(403);
      response.end("Forbidden");
      return;
    }

    let filePath = requested;
    if (!existsSync(filePath) || !statSync(filePath).isFile()) {
      filePath = join(runtimeRoot, "index.html");
    }
    if (!existsSync(filePath) || !statSync(filePath).isFile()) {
      response.writeHead(404);
      response.end("Not found");
      return;
    }
    response.writeHead(200, {
      "Cache-Control": "no-store",
      "Content-Type": CONTENT_TYPES[extname(filePath).toLowerCase()] || "application/octet-stream",
    });
    createReadStream(filePath).pipe(response);
  } catch {
    response.writeHead(400);
    response.end("Bad request");
  }
}

function stopRuntimeServer(server) {
  if (!server) return Promise.resolve();
  return new Promise((resolveClose) => {
    server.close(() => resolveClose());
  });
}

module.exports = { startRuntimeServer, stopRuntimeServer };
