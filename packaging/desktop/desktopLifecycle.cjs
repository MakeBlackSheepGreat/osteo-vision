function registerDesktopLifecycle({ app, shutdown, log = () => {} }) {
  let allowQuit = false;
  let shutdownPromise = null;

  const stopRuntime = () => {
    if (!shutdownPromise) {
      shutdownPromise = Promise.resolve()
        .then(shutdown)
        .catch((error) => log(`Runtime shutdown failed: ${error instanceof Error ? error.message : String(error)}`));
    }
    return shutdownPromise;
  };

  app.on("window-all-closed", () => app.quit());
  app.on("before-quit", (event) => {
    if (allowQuit) {
      return;
    }
    event.preventDefault();
    void stopRuntime().finally(() => {
      allowQuit = true;
      app.quit();
    });
  });

  return { stopRuntime };
}

module.exports = { registerDesktopLifecycle };
