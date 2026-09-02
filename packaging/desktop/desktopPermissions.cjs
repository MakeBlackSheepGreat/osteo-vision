function isTrustedRendererOrigin(origin) {
  if (typeof origin !== "string" || !origin) return false;
  try {
    return new URL(origin).protocol === "file:";
  } catch {
    return false;
  }
}

function mediaPermissionAllowed(webContents, permission, requestingOrigin) {
  if (permission !== "media") return false;
  const origin = requestingOrigin || webContents?.getURL?.() || "";
  return isTrustedRendererOrigin(origin);
}

function registerMediaPermissions(desktopSession, log = () => {}) {
  if (!desktopSession) throw new Error("Electron default session is unavailable.");
  desktopSession.setPermissionCheckHandler((webContents, permission, requestingOrigin) => {
    const allowed = mediaPermissionAllowed(webContents, permission, requestingOrigin);
    log(`Permission check permission=${permission} allowed=${allowed}`);
    return allowed;
  });
  desktopSession.setPermissionRequestHandler((webContents, permission, callback, details) => {
    const origin = details?.requestingUrl || webContents?.getURL?.() || "";
    const allowed = mediaPermissionAllowed(webContents, permission, origin);
    log(`Permission request permission=${permission} allowed=${allowed}`);
    callback(allowed);
  });
}

module.exports = { isTrustedRendererOrigin, mediaPermissionAllowed, registerMediaPermissions };
