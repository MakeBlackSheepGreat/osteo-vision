import { _electron as electron } from "playwright";
import fs from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { execFile, execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(frontendRoot, "..", "..");
const outputRoot = path.join(repoRoot, "output", "playwright", "desktop-real-test");
const defaultCompetitionRoot = path.join(repoRoot, "artifacts", "release", "competition-disc");
const physicianToken = "playwright-physician-token-20260715";

const options = parseOptions(process.argv.slice(2));
const packageRoot = resolvePackageRoot(options.packageRoot);
const executablePath = path.join(packageRoot, "Osteo Vision Platform.exe");
const runId = `${timestamp()}-${process.pid}`;
const runRoot = path.join(outputRoot, runId);
const userDataDir = path.join(runRoot, "user-data");
const screenshotDir = path.join(runRoot, "screenshots");
const resultPath = path.join(runRoot, "result.json");
const logPath = path.join(runRoot, "desktop-real-test.log");

fs.mkdirSync(screenshotDir, { recursive: true });
const checks = [];
const buttonAudit = [];
const uiStabilityAudit = [];
let auditSequence = 0;
const browserErrors = [];
const failedResponses = [];
let app = null;
let mainPid = null;
let backendPid = null;
let failure = null;

function parseOptions(args) {
  const parsed = {
    packageRoot: process.env.OSTEO_DESKTOP_PACKAGE_ROOT || "",
    skipCamera: process.env.OSTEO_REAL_TEST_SKIP_CAMERA === "true",
    disableGpu: process.env.OSTEO_REAL_TEST_DISABLE_GPU === "true",
    skipButtonAudit: process.env.OSTEO_REAL_TEST_SKIP_BUTTON_AUDIT === "true",
    timeoutMs: Number(process.env.OSTEO_REAL_TEST_TIMEOUT_MS || 300_000),
  };
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--package-root") parsed.packageRoot = args[++index] || "";
    else if (arg === "--skip-camera") parsed.skipCamera = true;
    else if (arg === "--disable-gpu") parsed.disableGpu = true;
    else if (arg === "--skip-button-audit") parsed.skipButtonAudit = true;
    else if (arg === "--timeout-ms") parsed.timeoutMs = Number(args[++index] || parsed.timeoutMs);
    else if (arg === "--help" || arg === "-h") {
      console.log("用法：node frontend/e2e/desktop.real.mjs [--package-root <目录>] [--skip-camera] [--disable-gpu] [--skip-button-audit] [--timeout-ms <毫秒>]");
      process.exit(0);
    }
  }
  if (!Number.isFinite(parsed.timeoutMs) || parsed.timeoutMs < 30_000) {
    throw new Error("--timeout-ms 必须是至少 30000 的数字。");
  }
  return parsed;
}

function resolvePackageRoot(explicitRoot) {
  const candidates = [];
  if (explicitRoot) candidates.push(path.resolve(explicitRoot));
  const desktopRoot = path.join(repoRoot, "artifacts", "release", "desktop", "Osteo Vision Platform-win32-x64");
  candidates.push(desktopRoot);
  if (fs.existsSync(defaultCompetitionRoot)) {
    for (const name of fs.readdirSync(defaultCompetitionRoot)) {
      const candidate = path.join(defaultCompetitionRoot, name);
      if (fs.existsSync(path.join(candidate, "Osteo Vision Platform.exe"))) candidates.push(candidate);
    }
  }
  const resolved = candidates.find((candidate) => fs.existsSync(path.join(candidate, "Osteo Vision Platform.exe")));
  if (!resolved) {
    throw new Error(`找不到桌面运行包入口，请先构建运行包，或通过 --package-root 指定目录。检查过：${candidates.join("；")}`);
  }
  return resolved;
}

function timestamp() {
  return new Date().toISOString().replaceAll(/[-:.TZ]/g, "").slice(0, 14);
}

function log(message) {
  const line = `${new Date().toISOString()} ${message}`;
  fs.appendFileSync(logPath, `${line}\n`, "utf8");
  console.log(line);
}

function check(name, passed, detail = "") {
  checks.push({ name, passed, detail });
  const compactDetail = detail.length > 1200 ? `${detail.slice(0, 1200)}…` : detail;
  log(`${passed ? "PASS" : "FAIL"} ${name}${compactDetail ? `: ${compactDetail}` : ""}`);
  if (!passed) throw new Error(`${name}${detail ? `：${detail}` : ""}`);
}

async function main() {
  log(`packageRoot=${packageRoot}`);
  log(`executable=${executablePath}`);
  check("桌面入口存在", fs.existsSync(executablePath), executablePath);
  await waitForPortClosed(8001, 5_000);

  const launchArgs = [
    `--user-data-dir=${userDataDir}`,
    "--use-fake-device-for-media-stream",
    "--use-fake-ui-for-media-stream",
    "--autoplay-policy=no-user-gesture-required",
  ];
  if (options.disableGpu) launchArgs.push("--disable-gpu");
  app = await electron.launch({
    executablePath,
    args: launchArgs,
    timeout: options.timeoutMs,
    env: { ...process.env, ELECTRON_ENABLE_LOGGING: "1" },
  });
  mainPid = app.process().pid ?? null;
  log(`electronPid=${mainPid ?? "unknown"}`);
  const page = await app.firstWindow();
  await page.waitForLoadState("domcontentloaded", { timeout: options.timeoutMs });
  page.on("console", (message) => {
    if (message.type() === "error" && !isExpectedRuntimeNoise(message.text())) {
      browserErrors.push(`console: ${message.text()}`);
    }
  });
  page.on("pageerror", (error) => browserErrors.push(`pageerror: ${error.message}`));
  page.on("response", (response) => {
    if (response.status() >= 400) {
      failedResponses.push({ status: response.status(), url: response.url() });
    }
  });
  page.on("requestfailed", (request) => {
    const failureText = request.failure()?.errorText || "unknown";
    if (!isExpectedRuntimeNoise(failureText)) {
      browserErrors.push(`requestfailed: ${request.method()} ${request.url()} (${failureText})`);
    }
  });

  await waitForPort(8001, options.timeoutMs);
  backendPid = getPortOwnerPid(8001);
  check("后端 ready 接口可用", (await fetchJson("http://127.0.0.1:8001/ready")).status === "ok");
  check("桌面窗口已显示", await page.locator("body").isVisible());
  await waitForText(page, "病例工作台", 30_000);
  check("全局运行状态横幅已移除", (await page.locator(".runtime-status").count()) === 0);
  await screenshot(page, "01-startup.png");

  const standardCase = await postJson("http://127.0.0.1:8001/platform/standard-demo-case");
  check("标准 OFDVDnet 演示病例可创建", Boolean(standardCase.case_id), String(standardCase.case_id || ""));
  await navigateHash(page, `#/case?caseId=${encodeURIComponent(standardCase.case_id)}`);
  await waitForText(page, "合成三视图拆分与分析", options.timeoutMs);
  await waitForSelectorCount(page, ".multichannel-grid video", 3, 60_000);
  check("内置 OFDVDnet 三视图视频已加载", (await page.locator(".multichannel-grid video").count()) >= 3);
  const synchronizedTimes = await page.locator(".multichannel-grid video").evaluateAll(async (elements) => {
    const videos = elements;
    for (const video of videos) video.muted = true;
    await videos[0].play();
    await new Promise((resolve) => setTimeout(resolve, 500));
    videos[0].pause();
    return videos.map((video) => video.currentTime);
  });
  check(
    "三视图播放时间保持同步",
    synchronizedTimes[0] > 0 && synchronizedTimes.slice(1).every((time) => Math.abs(time - synchronizedTimes[0]) < 0.12),
    JSON.stringify(synchronizedTimes),
  );
  await screenshot(page, "02-ofdvdnet-three-view.png");

  const dualButton = page.getByRole("button", { name: "开启双通道实时分析", exact: true });
  await waitForLocatorEnabled(dualButton, options.timeoutMs);
  await dualButton.click();
  await waitForAnyText(page, ["双通道实时分析已开启", "双通道融合分析完成"], options.timeoutMs);
  await page.waitForFunction(
    () => Array.from(document.querySelectorAll('img[alt*="实时配准融合"]')).some((image) => Boolean(image.getAttribute("src"))),
    undefined,
    { timeout: options.timeoutMs },
  );
  check("文件输入双通道实时分析可启动", true);
  check(
    "文件输入双通道融合结果已生成",
    await page.locator('img[alt*="实时配准融合"]').evaluateAll((images) => images.some((image) => Boolean(image.getAttribute("src")))),
  );
  await screenshot(page, "03-dual-channel-analysis.png");

  await navigateHash(page, "#/annotations");
  await waitForText(page, "病灶人工标注与医生复核", 30_000);
  const tokenInput = page.getByLabel("复核访问令牌");
  if (await tokenInput.count()) {
    await tokenInput.fill(physicianToken);
    await page.getByRole("button", { name: "核验身份" }).click();
    await waitForText(page, "医生复核", 20_000);
  }
  const sourceRows = page.locator(".source-row");
  await waitForSelectorCount(page, ".source-row", 1, 30_000);
  await sourceRows.first().click();
  await waitForSelectorCount(page, 'canvas[aria-label="病灶人工标注层"]', 1, 20_000);
  check("内置关键帧进入人工标注来源", (await sourceRows.count()) >= 1);
  await screenshot(page, "04-manual-annotation.png");

  const d024Snapshot = await fetchJson("http://127.0.0.1:8001/three-d-runtime/v1/references/d024/snapshot");
  check("D024 三维参考快照可读取", d024Snapshot.model_asset?.format === "stl", JSON.stringify(d024Snapshot));
  const d024Asset = await fetch("http://127.0.0.1:8001/three-d-runtime/v1/references/d024/assets/model");
  check("D024 STL 资产可读取", d024Asset.status === 200 && (d024Asset.headers.get("content-type") || "").includes("model/stl"));
  await navigateHash(page, "#/navigation");
  await waitForText(page, "病例三维导航工作台", 30_000);
  await waitForSelectorCount(page, ".three-d-runtime-embed", 1, 20_000);
  try {
    await page.waitForSelector('.three-d-runtime-embed[data-state="ready"]', { timeout: options.timeoutMs });
  } catch (error) {
    const debugFrame = page.frames().find((frame) => frame.url().includes(":5175"));
    const runtimeDebug = debugFrame
      ? await debugFrame.locator("body").innerText().catch(() => "<runtime body unavailable>")
      : "<runtime frame missing>";
    log(`三维运行时调试 URL=${debugFrame?.url() || "<none>"} BODY=${runtimeDebug.slice(0, 1200)}`);
    throw error;
  }
  const runtimeFrame = page.frames().find((frame) => frame.url().includes(":5175"));
  if (!runtimeFrame) throw new Error("三维运行时 iframe 未建立。");
  try {
    await runtimeFrame.waitForSelector('.three-d-viewport[data-state="ready"]', { timeout: options.timeoutMs });
  } catch (error) {
    const runtimeDebug = await runtimeFrame.locator("body").innerText().catch(() => "<runtime body unavailable>");
    log(`三维视口调试 URL=${runtimeFrame.url()} BODY=${runtimeDebug.slice(0, 1200)}`);
    throw error;
  }
  check("独立三维运行时确认就绪", true);
  check("三维视口模型已完成渲染", (await runtimeFrame.locator('.three-d-viewport[data-state="ready"]').count()) === 1);
  check("三维导航工作台保留二维安全路径", (await page.locator("body").innerText()).includes("安全") || (await page.locator("body").innerText()).includes("L0"));
  const modelingExample = await fetchJson("http://127.0.0.1:8001/three-d/modeling-examples/d036-toothfairy2");
  check("D036 示例建模路径可读取", String(modelingExample.source_path || "").includes("ToothFairy2F_001_0000.mha"), JSON.stringify(modelingExample));
  await screenshot(page, "05-d024-navigation.png");

  const videoCase = await postJson("http://127.0.0.1:8001/cases", {
    title: `桌面真实测试视频病例 ${Date.now()}`,
    description: "自动化真实桌面测试",
  });
  check("视频测试病例可创建", Boolean(videoCase.case_id), String(videoCase.case_id || ""));
  await navigateHash(page, `#/case?caseId=${encodeURIComponent(videoCase.case_id)}`);
  await waitForText(page, "术中荧光辅助平台", 30_000);
  await page.getByRole("tab", { name: "单路视频", exact: true }).click();
  const bundledVideo = path.join(packageRoot, "resources", "runtime_assets", "demo_data", "ofdvdnet", "video", "OFDVDNET_001.mp4");
  check("内置 MP4 文件存在", fs.existsSync(bundledVideo), bundledVideo);
  await page.getByTestId("single-video-file-input").setInputFiles(bundledVideo);
  await waitForText(page, "MP4 视频已导入病例", options.timeoutMs);
  check("内置 MP4 可导入病例", true);
  const videoElement = page.locator("video.video-stream-player");
  await waitForSelectorCount(page, "video.video-stream-player", 1, 30_000);
  await videoElement.evaluate(async (video) => {
    video.muted = true;
    await video.play();
    await new Promise((resolve) => setTimeout(resolve, 350));
    video.pause();
  });
  check("MP4 播放区域可播放", (await videoElement.evaluate((video) => video.currentTime > 0)) === true);
  await screenshot(page, "06-mp4-import-playback.png");

  if (options.skipCamera) {
    checks.push({ name: "摄像头实时分割", passed: true, skipped: true, detail: "命令行显式跳过" });
    log("SKIP 摄像头实时分割: 命令行显式跳过");
  } else {
    await navigateHash(page, `#/case?caseId=${encodeURIComponent(videoCase.case_id)}`);
    await page.getByRole("tab", { name: "浏览器摄像头", exact: true }).click();
    const cameraButton = page.getByRole("button", { name: "开始实时分割", exact: true });
    await waitForLocatorEnabled(cameraButton, 30_000);
    await cameraButton.click();
    await waitForAnyText(page, ["实时分割已启动", "连续分析运行中", "正在刷新实时分割", "摄像头开启失败", "实时分割启动失败"], 60_000);
    const cameraBody = await page.locator("body").innerText();
    const cameraStarted = ["实时分割已启动", "连续分析运行中", "正在刷新实时分割"].some((marker) => cameraBody.includes(marker));
    check("摄像头开始实时分割可执行", cameraStarted, cameraBody.slice(-600));
    await screenshot(page, "07-camera-live-segmentation.png");
  }

  if (!options.skipButtonAudit) {
    await runExhaustiveButtonAudit(page, {
      standardCaseId: standardCase.case_id,
      videoCaseId: videoCase.case_id,
      bundledVideo: path.join(packageRoot, "resources", "runtime_assets", "demo_data", "ofdvdnet", "video", "OFDVDNET_001.mp4"),
      bundledJpeg: path.join(packageRoot, "resources", "runtime_assets", "demo_data", "ofdvdnet", "previews", "OFDVDNET_001_reference.jpg"),
    });
  } else {
    log("SKIP 逐按钮真实点击审计: 命令行显式跳过");
  }

  const buttonAuditFailures = buttonAudit.filter((item) => item.outcome === "failed");
  check(
    "逐按钮真实点击审计完成",
    options.skipButtonAudit || (buttonAudit.length > 0 && buttonAuditFailures.length === 0),
    options.skipButtonAudit
      ? "命令行显式跳过"
      : `记录 ${buttonAudit.length} 项，失败 ${buttonAuditFailures.length} 项`,
  );

  const unexpectedResponses = failedResponses.filter(({ status, url }) => !isExpectedResponse(status, url));
  const unexpectedBrowserErrors = browserErrors.filter((message) => !isExpectedConsoleNoise(message));
  const unstableButtonUi = uiStabilityAudit.filter(
    (item) => Number(item.layout_shift_px || 0) > 48 || Number(item.scroll_delta_px || 0) > 48,
  );
  const visibleRuntimeErrors = uiStabilityAudit.flatMap((item) => item.error_messages || [])
    .filter((message) => /状态码\s*409|version conflict|未检测到第二路可用摄像头|状态码\s*(?:429|503)|服务正在限流|实时分割失败，保留最近一次/.test(message));
  check(
    "按钮交互无并发或限流报错",
    visibleRuntimeErrors.length === 0,
    visibleRuntimeErrors.slice(0, 12).join(" | "),
  );
  check(
    "按钮交互布局位移受控",
    unstableButtonUi.length === 0,
    unstableButtonUi
      .slice(0, 8)
      .map((item) => `${item.page}/${item.label}: ${item.layout_shift_px}px`)
      .join(" | "),
  );
  check(
    "浏览器无运行时错误",
    unexpectedBrowserErrors.length === 0 && unexpectedResponses.length === 0,
    [
      ...unexpectedBrowserErrors,
      ...unexpectedResponses.map(({ status, url }) => `HTTP ${status}: ${url}`),
    ].join(" | "),
  );
  return { page, status: "passed" };
}

async function cleanup() {
  if (app) {
    try {
      await app.close();
      log("Electron app.close completed");
    } catch (error) {
      log(`Electron close failed: ${error instanceof Error ? error.message : String(error)}`);
      if (mainPid) killProcess(mainPid);
    }
  }
  try {
    await waitForPortClosed(8001, 20_000);
    checks.push({ name: "关闭桌面窗口后 8001 端口已释放", passed: true });
    log("PASS 关闭桌面窗口后 8001 端口已释放");
  } catch (error) {
    checks.push({ name: "关闭桌面窗口后 8001 端口已释放", passed: false, detail: error.message });
    log(`FAIL 关闭桌面窗口后 8001 端口已释放: ${error.message}`);
    if (backendPid) killProcess(backendPid);
  }
  if (mainPid) {
    const exited = await waitForProcessExit(mainPid, 5_000);
    checks.push({ name: "Electron 主进程已退出", passed: exited });
    log(`${exited ? "PASS" : "FAIL"} Electron 主进程已退出: pid=${mainPid}`);
  }
  if (backendPid) {
    const exited = await waitForProcessExit(backendPid, 5_000);
    checks.push({ name: "后端进程树已退出", passed: exited });
    log(`${exited ? "PASS" : "FAIL"} 后端进程树已退出: pid=${backendPid}`);
  }
}

async function run() {
  try {
    await main();
  } catch (error) {
    failure = error instanceof Error ? error : new Error(String(error));
    log(`FAILURE ${failure.stack || failure.message}`);
    if (app) {
      try {
        const page = await app.firstWindow();
        await screenshot(page, "failure.png");
      } catch (screenshotError) {
        log(`Failure screenshot unavailable: ${screenshotError instanceof Error ? screenshotError.message : String(screenshotError)}`);
      }
    }
  } finally {
    await cleanup();
  const result = {
      status: failure || checks.some((item) => item.passed === false) ? "failed" : "passed",
      package_root: packageRoot,
      executable: executablePath,
      run_id: runId,
      run_root: runRoot,
      backend_pid: backendPid,
      electron_pid: mainPid,
      checks,
      button_audit: buttonAudit,
      ui_stability_audit: uiStabilityAudit,
      browser_errors: browserErrors.filter((message) => !isExpectedConsoleNoise(message)),
      expected_browser_errors: browserErrors.filter((message) => isExpectedConsoleNoise(message)),
      failed_responses: failedResponses,
      unexpected_responses: failedResponses.filter(({ status, url }) => !isExpectedResponse(status, url)),
      failure: failure?.message || null,
      host: { platform: process.platform, arch: process.arch, node: process.version, hostname: os.hostname() },
      completed_at: new Date().toISOString(),
    };
    fs.writeFileSync(resultPath, `${JSON.stringify(result, null, 2)}\n`, "utf8");
    console.log(`结果文件：${resultPath}`);
    process.exitCode = result.status === "passed" ? 0 : 1;
  }
}

async function navigateHash(page, hash) {
  await page.evaluate((nextHash) => {
    window.location.hash = nextHash;
  }, hash);
  await page.waitForFunction((nextHash) => window.location.hash === nextHash, hash, { timeout: 20_000 });
}

async function waitForText(page, text, timeoutMs) {
  await page.waitForFunction((expected) => document.body?.innerText.includes(expected), text, { timeout: timeoutMs });
}

async function waitForAnyText(page, texts, timeoutMs) {
  await page.waitForFunction((expected) => expected.some((text) => document.body?.innerText.includes(text)), texts, {
    timeout: timeoutMs,
  });
}

async function waitForSelectorCount(page, selector, minimum, timeoutMs) {
  await page.waitForFunction(
    ({ selector: css, minimum: count }) => document.querySelectorAll(css).length >= count,
    { selector, minimum },
    { timeout: timeoutMs },
  );
}

async function waitForLocatorEnabled(locator, timeoutMs) {
  await locator.waitFor({ state: "visible", timeout: timeoutMs });
  await locator.click({ trial: true, timeout: timeoutMs });
}

async function screenshot(page, name, { fullPage = true } = {}) {
  const screenshotPath = path.join(screenshotDir, name);
  fs.mkdirSync(path.dirname(screenshotPath), { recursive: true });
  await page.screenshot({ path: screenshotPath, fullPage, animations: "disabled", caret: "hide", timeout: 2_500 });
  return screenshotPath;
}

function normalizeButtonText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

async function openAllDetails(scope) {
  await scope
    .evaluate(() => {
      document.querySelectorAll("details").forEach((details) => {
        details.open = true;
      });
    })
    .catch(() => undefined);
}

async function collectVisibleButtonDescriptors(scope) {
  return scope.locator("button").evaluateAll((nodes) => {
    const isVisible = (node) => {
      const element = node;
      const style = window.getComputedStyle(element);
      return style.visibility !== "hidden" && style.display !== "none" && Boolean(element.offsetWidth || element.offsetHeight || element.getClientRects().length);
    };
    const visibleButtons = nodes.filter(isVisible);
    const occurrences = new Map();
    return visibleButtons.map((button, visibleIndex) => {
      const text = (button.innerText || button.textContent || "").replace(/\s+/g, " ").trim();
      const aria = button.getAttribute("aria-label") || "";
      const title = button.getAttribute("title") || "";
      const testid = button.getAttribute("data-testid") || "";
      const className = typeof button.className === "string" ? button.className : "";
      const parentLabel = button.closest("[aria-label]")?.getAttribute("aria-label") || "";
      const identity = [testid, aria, title, text, className, parentLabel].join("\u001f");
      const occurrence = occurrences.get(identity) || 0;
      occurrences.set(identity, occurrence + 1);
      return {
        visibleIndex,
        text,
        aria,
        title,
        testid,
        className,
        parentLabel,
        fullscreen: Boolean(button.closest(".analysis-fullscreen")),
        occurrence,
        disabled: Boolean(button.disabled),
        role: button.getAttribute("role") || "",
      };
    });
  });
}

function buttonDescriptorKey(scopeLabel, descriptor) {
  return [
    scopeLabel,
    descriptor.testid,
    descriptor.aria,
    descriptor.title,
    descriptor.text,
    descriptor.className,
    descriptor.parentLabel,
    descriptor.fullscreen,
    descriptor.occurrence,
  ].join("\u001f");
}

function buttonDescriptorLabel(descriptor) {
  return descriptor.aria || descriptor.text || descriptor.title || descriptor.testid || `未命名按钮 #${descriptor.visibleIndex + 1}`;
}

function descriptorMayOpenFileChooser(descriptor) {
  const label = `${descriptor.text} ${descriptor.aria} ${descriptor.title}`;
  return /选择|更换/.test(label) && /文件|JPEG|MP4|CBCT|STL|GLB|示例/.test(label);
}

async function markButtonForClick(scope, descriptor, marker) {
  return scope.evaluate(
    ({ descriptor: expected, marker: markerValue }) => {
      const isVisible = (node) => {
        const element = node;
        const style = window.getComputedStyle(element);
        return style.visibility !== "hidden" && style.display !== "none" && Boolean(element.offsetWidth || element.offsetHeight || element.getClientRects().length);
      };
      const visibleButtons = Array.from(document.querySelectorAll("button")).filter(isVisible);
      const matches = visibleButtons.filter((button) => {
        const text = (button.innerText || button.textContent || "").replace(/\s+/g, " ").trim();
        const aria = button.getAttribute("aria-label") || "";
        const title = button.getAttribute("title") || "";
        const testid = button.getAttribute("data-testid") || "";
        const className = typeof button.className === "string" ? button.className : "";
        const parentLabel = button.closest("[aria-label]")?.getAttribute("aria-label") || "";
        return (
          text === expected.text &&
          aria === expected.aria &&
          title === expected.title &&
          testid === expected.testid &&
          className === expected.className &&
          parentLabel === expected.parentLabel
        );
      });
      const target = matches[expected.occurrence] || visibleButtons[expected.visibleIndex];
      if (!target) return false;
      target.setAttribute("data-ov-real-audit-id", markerValue);
      return true;
    },
    { descriptor, marker },
  );
}

async function removeButtonMarker(scope, marker) {
  await scope
    .evaluate((markerValue) => {
      document.querySelector(`[data-ov-real-audit-id="${markerValue}"]`)?.removeAttribute("data-ov-real-audit-id");
    }, marker)
    .catch(() => undefined);
}

async function clickAuditedButton(page, scope, scopeLabel, descriptor, auditLabel) {
  const sequence = ++auditSequence;
  const marker = `ov-real-audit-${sequence}`;
  const label = buttonDescriptorLabel(descriptor);
  const entry = {
    sequence,
    page: auditLabel,
    scope: scopeLabel,
    label,
    text: descriptor.text,
    aria: descriptor.aria,
    title: descriptor.title,
    testid: descriptor.testid,
    fullscreen: Boolean(descriptor.fullscreen),
    disabled: descriptor.disabled,
    outcome: "failed",
    detail: "",
    screenshot: "",
    ui: {
      error_messages: [],
      layout_shift_px: 0,
      scroll_delta_px: 0,
      stable_anchor_count: 0,
    },
  };
  const screenshotName = path.join("buttons", `${String(sequence).padStart(4, "0")}-${safeFileName(auditLabel)}-${safeFileName(label)}.png`);
  try {
    await prepareForAuditedButton(page, scope, scopeLabel, descriptor);
    const marked = await markButtonForClick(scope, descriptor, marker);
    if (!marked) {
      entry.outcome = "skipped";
      entry.detail = "控件在状态切换后已不可见，已记录为状态变化。";
      buttonAudit.push(entry);
      log(`SKIP BUTTON ${auditLabel} / ${scopeLabel} / ${label}: ${entry.detail}`);
      return entry;
    }
    const target = scope.locator(`[data-ov-real-audit-id="${marker}"]`);
    const liveDisabled = await target.isDisabled().catch(() => descriptor.disabled);
    const liveAriaDisabled = (await target.getAttribute("aria-disabled").catch(() => null)) === "true";
    entry.disabled = liveDisabled || liveAriaDisabled;
    if (entry.disabled) {
      entry.outcome = "disabled";
      entry.detail = descriptor.title || "控件当前处于禁用状态";
      entry.screenshot = await captureButtonScreenshot(page, screenshotName, entry);
      buttonAudit.push(entry);
      log(`SKIP BUTTON ${auditLabel} / ${scopeLabel} / ${label}: disabled${entry.detail ? ` (${entry.detail})` : ""}`);
      return entry;
    }

    let chooserPromise = null;
    if (descriptorMayOpenFileChooser(descriptor)) {
      chooserPromise = page.waitForEvent("filechooser", { timeout: 2_000 }).catch(() => null);
    }
    await target.scrollIntoViewIfNeeded({ timeout: 8_000 });
    const beforeUi = await captureUiState(scope);
    await target.click({ timeout: 8_000, noWaitAfter: true });
    const chooser = chooserPromise ? await chooserPromise : null;
    if (chooser) {
      try {
        await chooser.setFiles([]);
        entry.detail = "已捕获原生文件选择器并取消选择。";
      } catch (error) {
        entry.detail = `已触发原生文件选择器，但清空选择失败：${error instanceof Error ? error.message : String(error)}`;
      }
    }
    await delay(450);
    const afterUi = await captureUiState(scope);
    entry.ui = compareUiState(beforeUi, afterUi);
    uiStabilityAudit.push({
      page: auditLabel,
      scope: scopeLabel,
      label,
      ...entry.ui,
    });
    if (entry.ui.error_messages.length || entry.ui.layout_shift_px > 2 || entry.ui.scroll_delta_px > 2) {
      log(
        `UI AUDIT ${auditLabel} / ${scopeLabel} / ${label}: `
        + `errors=${JSON.stringify(entry.ui.error_messages)} `
        + `layoutShift=${entry.ui.layout_shift_px}px scrollDelta=${entry.ui.scroll_delta_px}px`,
      );
    }
    entry.outcome = "clicked";
    entry.screenshot = await captureButtonScreenshot(page, screenshotName, entry);
    buttonAudit.push(entry);
    log(`PASS BUTTON ${auditLabel} / ${scopeLabel} / ${label}${entry.detail ? `: ${entry.detail}` : ""}`);
    await settleAfterAuditedButton(page, label);
    return entry;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const targetCount = await scope.locator(`[data-ov-real-audit-id="${marker}"]`).count().catch(() => 0);
    if (!targetCount || /detached|not attached|not visible|no element/i.test(message)) {
      entry.outcome = "skipped";
      entry.detail = `状态切换后控件已消失：${message}`;
    } else {
      entry.outcome = "failed";
      entry.detail = message;
    }
    entry.screenshot = await captureButtonScreenshot(page, screenshotName, entry);
    buttonAudit.push(entry);
    log(`${entry.outcome === "failed" ? "FAIL" : "SKIP"} BUTTON ${auditLabel} / ${scopeLabel} / ${label}: ${entry.detail}`);
    return entry;
  } finally {
    await removeButtonMarker(scope, marker);
  }
}

async function captureUiState(scope) {
  return scope.evaluate(() => {
    const visible = (node) => {
      if (!(node instanceof HTMLElement)) return false;
      const style = window.getComputedStyle(node);
      return style.display !== "none"
        && style.visibility !== "hidden"
        && Number.parseFloat(style.opacity || "1") > 0
        && Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
    };
    const errorMessages = Array.from(document.querySelectorAll(
      '[role="alert"], .state-message.error, .operation-message.error, .job-panel-copy .job-error',
    ))
      .filter(visible)
      .map((node) => (node.textContent || "").replace(/\\s+/g, " ").trim())
      .filter(Boolean)
      .filter((message, index, values) => values.indexOf(message) === index)
      .slice(0, 12);
    const anchors = {};
    // Only compare the persistent shell. Mode panels, result cards and status
    // messages are intentionally replaced after a button action and may have
    // different heights; including them reports expected content changes as a
    // page-level layout jump.
    for (const selector of [
      ".workspace-header",
      ".workspace-grid",
      ".workspace-sidebar",
      ".analysis-column",
      ".analysis-card",
      ".analysis-header",
    ]) {
      const element = document.querySelector(selector);
      if (!element || !visible(element)) continue;
      const rect = element.getBoundingClientRect();
      anchors[selector] = {
        top: rect.top,
        left: rect.left,
        width: rect.width,
        height: rect.height,
      };
    }
    return {
      scroll_y: window.scrollY,
      document_height: document.documentElement.scrollHeight,
      anchors,
      error_messages: errorMessages,
    };
  }).catch(() => ({ scroll_y: 0, document_height: 0, anchors: {}, error_messages: [] }));
}

function compareUiState(before, after) {
  const anchorKeys = new Set([...Object.keys(before?.anchors || {}), ...Object.keys(after?.anchors || {})]);
  let layoutShift = 0;
  let stableAnchorCount = 0;
  for (const key of anchorKeys) {
    const left = before?.anchors?.[key];
    const right = after?.anchors?.[key];
    if (!left || !right) {
      layoutShift = Math.max(layoutShift, Math.abs((right?.top ?? 0) - (left?.top ?? 0)), Math.abs((right?.height ?? 0) - (left?.height ?? 0)));
      continue;
    }
    const delta = Math.max(
      Math.abs(right.top - left.top),
      Math.abs(right.left - left.left),
      Math.abs(right.width - left.width),
      Math.abs(right.height - left.height),
    );
    layoutShift = Math.max(layoutShift, Math.round(delta * 100) / 100);
    if (delta <= 2) stableAnchorCount += 1;
  }
  return {
    error_messages: after?.error_messages || [],
    layout_shift_px: layoutShift,
    scroll_delta_px: Math.round(Math.abs((after?.scroll_y || 0) - (before?.scroll_y || 0)) * 100) / 100,
    stable_anchor_count: stableAnchorCount,
  };
}

async function captureButtonScreenshot(page, screenshotName, entry) {
  try {
    return await screenshot(page, screenshotName, { fullPage: false });
  } catch (error) {
    const detail = `截图未完成：${error instanceof Error ? error.message : String(error)}`;
    entry.detail = entry.detail ? `${entry.detail}；${detail}` : detail;
    return "";
  }
}

async function prepareForAuditedButton(page, scope, scopeLabel, descriptor) {
  const label = buttonDescriptorLabel(descriptor);
  const isRuntimeButton = scopeLabel.startsWith("三维运行时");
  const isFullscreenButton = Boolean(descriptor.fullscreen) || /全屏分析视图/.test(label);
  if (!isRuntimeButton && !isFullscreenButton) {
    await closeAnalysisOverlay(page);
  }
  if (!isRuntimeButton && !isFullscreenButton && !/停止实时分割|开始实时分割|开启摄像头|关闭摄像头|连接荧光摄像头|请求摄像头/.test(label)) {
    await stopActiveCameraAnalysis(page);
  }
  await pauseRenderedVideos(page);
}

async function settleAfterAuditedButton(page, label) {
  await delay(300);
  if (/停止实时分割|关闭摄像头/.test(label)) {
    await delay(250);
  }
  if (/开始实时分割/.test(label)) {
    await delay(800);
    await stopActiveCameraAnalysis(page);
  }
}

async function pauseRenderedVideos(page) {
  await page
    .evaluate(() => {
      document.querySelectorAll("video").forEach((video) => {
        if (!video.classList.contains("camera-live-player")) video.pause();
      });
    })
    .catch(() => undefined);
}

async function closeAnalysisOverlay(page) {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const overlay = page.locator('.analysis-fullscreen[role="dialog"], [role="dialog"][aria-label="全屏分析视图"]').last();
    if (!(await overlay.count().catch(() => 0))) return;
    const close = overlay.getByRole("button", { name: /关闭全屏分析视图|关闭/ }).first();
    if (await close.count().catch(() => 0)) {
      await close.click({ force: true, timeout: 2_000 }).catch(() => undefined);
    } else {
      await page.keyboard.press("Escape").catch(() => undefined);
    }
    await delay(120);
  }
}

async function stopActiveCameraAnalysis(page) {
  const stop = page.getByRole("button", { name: "停止实时分割", exact: true });
  if (!(await stop.count().catch(() => 0))) return;
  if (!(await stop.isVisible().catch(() => false))) return;
  if (await stop.isDisabled().catch(() => true)) return;
  await stop.click({ force: true, timeout: 3_000, noWaitAfter: true }).catch(() => undefined);
  await delay(250);
}

async function resetAuditPage(page) {
  await closeAnalysisOverlay(page);
  await stopActiveCameraAnalysis(page);
  await pauseRenderedVideos(page);
  await page.reload({ waitUntil: "domcontentloaded", timeout: options.timeoutMs }).catch(() => undefined);
  await page.waitForSelector("body", { state: "visible", timeout: options.timeoutMs });
  await delay(350);
}

function safeFileName(value) {
  return normalizeButtonText(value).replace(/[^\p{L}\p{N}_-]+/gu, "_").slice(0, 80) || "button";
}

async function auditVisibleButtons(page, auditLabel, { maxRounds = 3, includeRuntime = true } = {}) {
  const seen = new Set();
  let rounds = 0;
  for (; rounds < maxRounds; rounds += 1) {
    await openAllDetails(page);
    const scopes = [{ scope: page, label: "主窗口" }];
    if (includeRuntime) {
      for (const frame of page.frames()) {
        if (frame === page.mainFrame()) continue;
        const hasRuntime = await frame.locator(".runtime-shell").count().catch(() => 0);
        if (hasRuntime) scopes.push({ scope: frame, label: `三维运行时 ${frame.url()}` });
      }
    }
    let freshCount = 0;
    for (const { scope, label: scopeLabel } of scopes) {
      await openAllDetails(scope);
      const descriptors = await collectVisibleButtonDescriptors(scope).catch(() => []);
      descriptors.sort((left, right) => buttonAuditPriority(right) - buttonAuditPriority(left));
      for (const descriptor of descriptors) {
        const key = buttonDescriptorKey(scopeLabel, descriptor);
        if (seen.has(key)) continue;
        seen.add(key);
        freshCount += 1;
        await clickAuditedButton(page, scope, scopeLabel, descriptor, auditLabel);
      }
    }
    if (!freshCount) break;
    await delay(250);
  }
  log(`BUTTON AUDIT ${auditLabel}: ${buttonAudit.filter((item) => item.page === auditLabel).length} 项，${rounds + 1} 轮`);
}

function buttonAuditPriority(descriptor) {
  const label = buttonDescriptorLabel(descriptor);
  if (descriptor.fullscreen && !/关闭全屏分析视图/.test(label)) return 120;
  if (descriptor.fullscreen && /关闭全屏分析视图/.test(label)) return 80;
  if (/停止实时分割|关闭摄像头/.test(label)) return 100;
  if (/关闭|停止/.test(label)) return 90;
  if (/开始实时分割|开启摄像头|连接荧光摄像头/.test(label)) return 80;
  return 0;
}

async function runExhaustiveButtonAudit(page, context) {
  log("开始逐页逐状态按钮真实点击审计");
  const auditPhase = async (label, action) => {
    try {
      await resetAuditPage(page);
      await action();
      await auditVisibleButtons(page, label, { maxRounds: 3 });
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      buttonAudit.push({ sequence: ++auditSequence, page: label, scope: "phase", label, outcome: "failed", detail, screenshot: "" });
      log(`FAIL BUTTON PHASE ${label}: ${detail}`);
      try {
        await screenshot(page, path.join("buttons", `${String(auditSequence).padStart(4, "0")}-${safeFileName(label)}-phase-failure.png`), { fullPage: false });
      } catch {
        // 页面可能已关闭；最终结果仍保留失败原因。
      }
    }
  };

  await auditPhase("病例工作台-合成三视图", async () => {
    await navigateHash(page, `#/case?caseId=${encodeURIComponent(context.standardCaseId)}`);
    await waitForText(page, "术中影像工作台", options.timeoutMs);
    await waitForSelectorCount(page, ".multichannel-grid video", 3, 60_000);
  });

  await auditPhase("病例工作台-单路MP4分析", async () => {
    await navigateHash(page, `#/case?caseId=${encodeURIComponent(context.videoCaseId)}`);
    await waitForText(page, "术中影像工作台", options.timeoutMs);
    await page.getByRole("tab", { name: "MP4 视频", exact: true }).click();
    await page.getByRole("tab", { name: "单路视频", exact: true }).click();
    if (!(await page.locator("video.video-stream-player").count())) {
      await page.getByTestId("single-video-file-input").setInputFiles(context.bundledVideo);
      await waitForSelectorCount(page, "video.video-stream-player", 1, 30_000);
    }
    const analyze = page.getByRole("button", { name: "启动离线关键帧分析", exact: true });
    if (await analyze.count() && !(await analyze.isDisabled())) {
      await analyze.click();
      await waitForAnyText(page, ["分析完成", "关键帧分析完成", "运行中", "分析失败"], options.timeoutMs).catch(() => undefined);
      await delay(800);
    }
  });

  await auditPhase("病例工作台-双通道MP4", async () => {
    await navigateHash(page, `#/case?caseId=${encodeURIComponent(context.videoCaseId)}`);
    await waitForText(page, "术中影像工作台", options.timeoutMs);
    await page.getByRole("tab", { name: "MP4 视频", exact: true }).click();
    await page.getByRole("tab", { name: "双通道视频", exact: true }).click();
    const whiteInput = page.getByTestId("white-light-video-file-input");
    const fluorescenceInput = page.getByTestId("fluorescence-video-file-input");
    if (await whiteInput.count()) await whiteInput.setInputFiles(context.bundledVideo);
    if (await fluorescenceInput.count()) await fluorescenceInput.setInputFiles(context.bundledVideo);
    await delay(1_000);
    const prepare = page.getByRole("button", { name: /准备同步预览|重试同步预览/, exact: false });
    if (await prepare.count() && !(await prepare.first().isDisabled())) {
      await prepare.first().click();
      await waitForAnyText(page, ["同步会话已准备", "同步会话", "准备失败"], options.timeoutMs).catch(() => undefined);
    }
  });

  await auditPhase("病例工作台-JPEG图像", async () => {
    await navigateHash(page, `#/case?caseId=${encodeURIComponent(context.videoCaseId)}`);
    await waitForText(page, "术中影像工作台", options.timeoutMs);
    await page.getByRole("tab", { name: "文件输入", exact: true }).click();
    await page.getByRole("tab", { name: "JPEG 图像", exact: true }).click();
    const imageInputs = page.locator('input[type="file"][accept*="image/jpeg"]');
    const count = await imageInputs.count();
    if (count >= 2) {
      await imageInputs.nth(0).setInputFiles(context.bundledJpeg);
      await imageInputs.nth(1).setInputFiles(context.bundledJpeg);
      if (count >= 3) await imageInputs.nth(2).setInputFiles(context.bundledJpeg);
      await delay(1_000);
    }
    const analyze = page.getByRole("button", { name: "开始图像融合分析", exact: true });
    if (await analyze.count() && !(await analyze.isDisabled())) {
      await analyze.click();
      await waitForAnyText(page, ["图像融合分析完成", "分析完成", "分析失败"], options.timeoutMs).catch(() => undefined);
    }
  });

  await auditPhase("病例工作台-摄像头", async () => {
    await navigateHash(page, `#/case?caseId=${encodeURIComponent(context.videoCaseId)}`);
    await waitForText(page, "术中影像工作台", options.timeoutMs);
    await page.getByRole("tab", { name: "浏览器摄像头", exact: true }).click();
    const start = page.getByRole("button", { name: "开始实时分割", exact: true });
    if (await start.count() && !(await start.isDisabled())) {
      await start.click();
      await waitForAnyText(page, ["实时分割已启动", "实时分割启动失败", "摄像头开启失败"], 60_000).catch(() => undefined);
    }
    const connect = page.getByRole("button", { name: "连接荧光摄像头", exact: true });
    if (await connect.count() && !(await connect.isDisabled())) {
      await connect.click();
      await waitForAnyText(page, ["双通道摄像头已连接", "荧光摄像头已连接", "荧光摄像头连接失败"], 30_000).catch(() => undefined);
    }
  });

  await auditPhase("人工标注-已载入来源", async () => {
    await navigateHash(page, `#/annotations?caseId=${encodeURIComponent(context.standardCaseId)}`);
    await waitForText(page, "病灶人工标注与医生复核", options.timeoutMs);
    const tokenInput = page.getByLabel("复核访问令牌");
    if (await tokenInput.count()) {
      await tokenInput.fill(physicianToken);
      const auth = page.getByRole("button", { name: "核验身份", exact: true });
      if (await auth.count()) await auth.click();
    }
    await waitForSelectorCount(page, ".source-row", 1, 30_000);
    await page.locator(".source-row").first().click();
    await waitForSelectorCount(page, 'canvas[aria-label="病灶人工标注层"]', 1, 20_000);
  });

  await auditPhase("三维导航-病例与运行时", async () => {
    await navigateHash(page, `#/navigation?caseId=${encodeURIComponent(context.standardCaseId)}`);
    await waitForText(page, "病例三维导航工作台", options.timeoutMs);
    await waitForSelectorCount(page, ".three-d-runtime-embed", 1, 30_000);
    await page.waitForSelector('.three-d-runtime-embed[data-state="ready"]', { timeout: options.timeoutMs });
  });

  await auditPhase("病例档案", async () => {
    await navigateHash(page, `#/cases?caseId=${encodeURIComponent(context.standardCaseId)}`);
    await waitForText(page, "病例建立、加载与基础质控", 30_000);
    await delay(1_000);
  });

  await auditPhase("数据准入", async () => {
    await navigateHash(page, "#/intake");
    await waitForText(page, "医院数据准入与隔离", 30_000);
    await delay(500);
  });

  await auditPhase("公开视频库", async () => {
    await navigateHash(page, "#/data");
    await waitForText(page, "公开代理视频库", 30_000);
    await delay(700);
  });

  await auditPhase("静态数据复核", async () => {
    await navigateHash(page, "#/dataset-review");
    await waitForText(page, "静态荧光数据复核", 30_000);
    await delay(500);
  });

  await auditPhase("报告导出", async () => {
    await navigateHash(page, `#/report?caseId=${encodeURIComponent(context.standardCaseId)}`);
    await waitForText(page, "病例证据包预览", 30_000);
    await delay(500);
  });
  log(`逐页逐状态按钮审计结束：共记录 ${buttonAudit.length} 项`);
}

async function fetchJson(url, init) {
  const response = await fetch(url, init);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(`${url} 返回 HTTP ${response.status}: ${JSON.stringify(payload)}`);
  return payload;
}

async function postJson(url, body) {
  return fetchJson(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function waitForPort(port, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await isPortOpen(port)) return;
    await delay(250);
  }
  throw new Error(`端口 ${port} 在 ${timeoutMs}ms 内未监听。`);
}

async function waitForPortClosed(port, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (!(await isPortOpen(port))) return;
    await delay(250);
  }
  throw new Error(`端口 ${port} 在 ${timeoutMs}ms 内仍被占用。`);
}

function isPortOpen(port) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host: "127.0.0.1", port });
    const finish = (open) => {
      socket.destroy();
      resolve(open);
    };
    socket.once("connect", () => finish(true));
    socket.once("error", () => finish(false));
    socket.setTimeout(500, () => finish(false));
  });
}

function getPortOwnerPid(port) {
  if (process.platform !== "win32") return null;
  try {
    const output = execFileSync("powershell.exe", ["-NoProfile", "-NonInteractive", "-Command", `(Get-NetTCPConnection -LocalPort ${port} -State Listen -ErrorAction SilentlyContinue).OwningProcess`], { encoding: "utf8" });
    const pid = Number.parseInt(output.trim().split(/\s+/)[0] || "", 10);
    return Number.isFinite(pid) ? pid : null;
  } catch {
    return null;
  }
}

function processExists(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

async function waitForProcessExit(pid, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (!processExists(pid)) return true;
    await delay(200);
  }
  return !processExists(pid);
}

function killProcess(pid) {
  if (process.platform === "win32") {
    execFile("taskkill.exe", ["/PID", String(pid), "/T", "/F"], { windowsHide: true }, () => undefined);
  } else {
    try {
      process.kill(pid, "SIGTERM");
    } catch {
      // The process may have exited during cleanup.
    }
  }
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isExpectedRuntimeNoise(message) {
  return /ERR_ABORTED|ERR_CONNECTION_RESET|status of 409|status of 429|status of 503|net::ERR_CONNECTION_REFUSED/.test(message);
}

function isExpectedResponse(status, url) {
  return (
    (status === 429 && url.includes("/live-frames")) ||
    (status === 403 && url.includes("/annotation-training-manifests"))
  );
}

function isExpectedConsoleNoise(message) {
  return /Failed to load resource: the server responded with a status of 403 \(Forbidden\)/.test(message);
}

await run();
