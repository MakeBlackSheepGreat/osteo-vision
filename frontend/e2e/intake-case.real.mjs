import { _electron as electron } from "playwright";
import fs from "node:fs";
import net from "node:net";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(frontendRoot, "..", "..");
const outputRoot = path.join(repoRoot, "output", "playwright", "intake-case-real-test");
const defaultPackageRoot = path.join(
  repoRoot,
  "artifacts",
  "release",
  "competition-disc",
  "Osteo-Vision-Competition-Disc-win32-x64-20260831-r28",
);
const physicianToken = "playwright-physician-token-20260715";
const options = parseOptions(process.argv.slice(2));
const packageRoot = path.resolve(options.packageRoot || defaultPackageRoot);
const executablePath = path.join(packageRoot, "Osteo Vision Platform.exe");
const runId = timestamp();
const runRoot = path.join(outputRoot, runId);
const userDataDir = path.join(runRoot, "user-data");
const screenshotDir = path.join(runRoot, "screenshots");
const resultPath = path.join(runRoot, "result.json");
const checks = [];
const browserErrors = [];
const failedResponses = [];
let app = null;
let backendPid = null;

fs.mkdirSync(screenshotDir, { recursive: true });

function parseOptions(args) {
  const parsed = { packageRoot: process.env.OSTEO_DESKTOP_PACKAGE_ROOT || "", timeoutMs: 300_000 };
  for (let index = 0; index < args.length; index += 1) {
    if (args[index] === "--package-root") parsed.packageRoot = args[++index] || "";
    if (args[index] === "--timeout-ms") parsed.timeoutMs = Number(args[++index] || parsed.timeoutMs);
  }
  if (!Number.isFinite(parsed.timeoutMs) || parsed.timeoutMs < 30_000) {
    throw new Error("--timeout-ms 必须是至少 30000 的数字。");
  }
  return parsed;
}

function timestamp() {
  return new Date().toISOString().replaceAll(/[-:.TZ]/g, "").slice(0, 14);
}

function check(name, passed, detail = "") {
  checks.push({ name, passed, detail });
  if (!passed) throw new Error(`${name}${detail ? `：${detail}` : ""}`);
}

async function main() {
  check("r28 桌面入口存在", fs.existsSync(executablePath), executablePath);
  check("r28 内置 JPEG 存在", fs.existsSync(bundledJpeg()), bundledJpeg());
  check("r28 内置 MP4 存在", fs.existsSync(bundledVideo()), bundledVideo());
  await waitForPortClosed(8001, 10_000);
  app = await launchApp();
  let page = await app.firstWindow();
  await wirePage(page);
  await waitForPort(8001, options.timeoutMs);
  backendPid = getPortOwnerPid(8001);
  await waitForText(page, "病例工作台", options.timeoutMs);
  check("准入与病例专项测试窗口已显示", await page.locator("body").isVisible());

  const successBatch = await exerciseSuccessfulAdmission(page);
  const quarantineBatch = await exerciseQuarantineAdmission(page);
  await exerciseHistoricalBatchLoad(page, successBatch.batchId);
  const createdCaseId = await exerciseCaseArchive(page, successBatch.caseId);

  await app.close();
  app = null;
  await waitForPortClosed(8001, 20_000);
  check("首次关闭后病例后端端口已释放", true);
  check(
    "病例 SQLite 档案已持久化",
    fs.existsSync(path.join(userDataDir, "artifacts", "cases.sqlite")),
    path.join(userDataDir, "artifacts", "cases.sqlite"),
  );
  check(
    "准入报告与清单已持久化",
    fs.existsSync(successBatch.reportPath) && fs.existsSync(successBatch.csvPath),
    `${successBatch.reportPath}; ${successBatch.csvPath}`,
  );

  app = await launchApp();
  page = await app.firstWindow();
  await wirePage(page);
  await waitForPort(8001, options.timeoutMs);
  await waitForText(page, "病例工作台", options.timeoutMs);
  await verifyCaseAfterRestart(page, createdCaseId);
  await verifyIntakeAfterRestart(page, successBatch.batchId, quarantineBatch.batchId);

  return {
    status: "passed",
    packageRoot,
    runId,
    successBatch,
    quarantineBatch,
    createdCaseId,
    checks,
    browserErrors,
    failedResponses,
  };
}

async function launchApp() {
  return electron.launch({
    executablePath,
    args: [
      `--user-data-dir=${userDataDir}`,
      "--use-fake-device-for-media-stream",
      "--use-fake-ui-for-media-stream",
      "--autoplay-policy=no-user-gesture-required",
    ],
    timeout: options.timeoutMs,
    env: { ...process.env, ELECTRON_ENABLE_LOGGING: "1" },
  });
}

async function wirePage(page) {
  page.on("console", (message) => {
    if (message.type() === "error") browserErrors.push(`console: ${message.text()}`);
  });
  page.on("pageerror", (error) => browserErrors.push(`pageerror: ${error.message}`));
  page.on("response", (response) => {
    if (response.status() >= 400) failedResponses.push({ status: response.status(), url: response.url() });
  });
  page.on("requestfailed", (request) => {
    const failureText = request.failure()?.errorText || "unknown";
    if (failureText === "net::ERR_ABORTED" || request.url().includes("/files/video?")) return;
    browserErrors.push(`requestfailed: ${request.method()} ${request.url()} (${failureText})`);
  });
  await page.waitForLoadState("domcontentloaded", { timeout: options.timeoutMs });
}

async function exerciseSuccessfulAdmission(page) {
  await navigateHash(page, "#/intake");
  await waitForText(page, "医院数据准入与隔离", options.timeoutMs);
  const batchId = `R28INTAKE-${Date.now()}`;
  const externalCaseId = `R28_CASE_${Date.now()}`;
  await fillIntakeHeader(page, batchId, "准入测试医院", "approved");
  await page.getByRole("checkbox", { name: "已确认影像与元数据完成脱敏", exact: true }).check();
  await page.getByRole("checkbox", { name: "病例编号映射表由医院保管", exact: true }).check();
  await page.getByRole("checkbox", { name: "已确认属于颌骨骨髓炎目标场景", exact: true }).check();
  await page.locator('input[type="file"]').setInputFiles([bundledJpeg(), bundledVideo()]);
  await waitForSelectorCount(page, ".file-row", 2, 20_000);
  for (const row of await page.locator(".file-row").all()) {
    await row.getByLabel("脱敏病例编号", { exact: true }).fill(externalCaseId);
  }
  const submit = page.getByRole("button", { name: "执行准入检查", exact: true });
  await waitForLocatorEnabled(submit, 20_000);
  await submit.click();
  await waitForText(page, `批次检查完成：准入 2，隔离 0。`, options.timeoutMs);
  check("数据准入通过授权与双文件上传", true);
  check("准入结果显示病例证据完整关联", (await page.locator(".artifact-attachment").innerText()).includes("1/1"));
  await page.screenshot({ path: path.join(screenshotDir, "01-intake-admitted.png"), fullPage: true });

  const report = await fetchJson(`http://127.0.0.1:8001/hospital-intake/batches/${encodeURIComponent(batchId)}`);
  check("准入报告可读取", report.summary?.admitted_count === 2, JSON.stringify(report.summary));
  check("准入病例已创建并带来源元数据", Boolean(report.case_map?.[externalCaseId]));
  check("准入记录默认保持复核与训练禁入", report.records.every((record) => record.review_state === "review_required" && record.training_eligible === false));
  check("准入报告包含病例证据关联状态", report.artifact_attachment?.status === "completed");
  const reportPath = String(report.report_path || "");
  const csvPath = String(report.csv_path || "");
  check("准入 JSON/CSV 文件存在", fs.existsSync(reportPath) && fs.existsSync(csvPath), `${reportPath}; ${csvPath}`);
  check("准入 JSON 下载端点可用", await fileEndpointOk(reportPath));
  check("准入 CSV 下载端点可用", await fileEndpointOk(csvPath));
  return { batchId, caseId: String(report.case_map[externalCaseId]), reportPath, csvPath };
}

async function exerciseQuarantineAdmission(page) {
  const newBatch = page.getByRole("button", { name: "开始新批次", exact: true });
  await newBatch.click();
  const batchId = `R28QUARANTINE-${Date.now()}`;
  await fillIntakeHeader(page, batchId, "准入测试医院", "pending");
  await page.locator('input[type="file"]').setInputFiles(bundledJpeg());
  await waitForSelectorCount(page, ".file-row", 1, 20_000);
  const submit = page.getByRole("button", { name: "执行准入检查", exact: true });
  await waitForLocatorEnabled(submit, 20_000);
  await submit.click();
  await waitForText(page, `批次检查完成：准入 0，隔离 1。`, options.timeoutMs);
  const body = await page.locator("body").innerText();
  check("未完成授权的批次进入隔离", body.includes("机构授权状态尚未批准") && body.includes("脱敏状态尚未确认"));
  check("隔离结果不创建平台病例", !(await page.locator(".result-list .case-link").count()));
  await page.screenshot({ path: path.join(screenshotDir, "02-intake-quarantined.png"), fullPage: true });
  const report = await fetchJson(`http://127.0.0.1:8001/hospital-intake/batches/${encodeURIComponent(batchId)}`);
  check("隔离报告可读取", report.summary?.quarantined_count === 1, JSON.stringify(report.summary));
  check("隔离记录原因可追溯", report.records[0]?.reasons?.some((item) => item.code === "authorization_not_approved"));
  return { batchId };
}

async function exerciseHistoricalBatchLoad(page, batchId) {
  await page.locator("details.recent-batches summary").click();
  const historical = page.locator(".recent-batches button").filter({ hasText: batchId });
  await waitForLocatorCount(historical, 1, 20_000);
  await historical.click();
  await waitForText(page, `已载入准入批次：${batchId}`, 20_000);
  check("历史准入批次可从病例档案恢复", (await page.locator(".result-list").innerText()).includes("已准入"));
}

async function exerciseCaseArchive(page, admittedCaseId) {
  await navigateHash(page, "#/cases");
  await waitForText(page, "病例建立、加载与基础质控", options.timeoutMs);
  await page.waitForFunction(
    (caseId) => Array.from(document.querySelectorAll("select option")).some((option) => option.value === caseId),
    admittedCaseId,
    { timeout: options.timeoutMs },
  );
  const catalog = page.locator("select").first();
  await catalog.selectOption(admittedCaseId);
  await page.getByRole("button", { name: "加载病例", exact: true }).click();
  await waitForText(page, `病例已加载：${admittedCaseId}`, 20_000);
  check("病例档案可加载准入病例", (await page.locator(".case-summary").innerText()).includes(admittedCaseId));

  await page.locator("details.create-case summary").click();
  const title = `r28 档案重启测试 ${Date.now()}`;
  await page.getByPlaceholder("请输入病例标题").fill(title);
  await page.getByRole("button", { name: "新建病例", exact: true }).click();
  await waitForText(page, "病例已创建：case_", 20_000);
  const createdCaseId = await page.locator(".case-summary dd").first().innerText();
  check("病例档案可新建病例", /^case_[a-f0-9]+$/.test(createdCaseId), createdCaseId);
  check("新建病例标题已显示", (await page.locator(".current-case-card > h2").innerText()) === title);
  await page.screenshot({ path: path.join(screenshotDir, "03-case-archive-created.png"), fullPage: true });
  return createdCaseId;
}

async function verifyCaseAfterRestart(page, caseId) {
  await navigateHash(page, "#/cases");
  await waitForText(page, "病例建立、加载与基础质控", options.timeoutMs);
  await page.waitForFunction(
    (value) => Array.from(document.querySelectorAll("select option")).some((option) => option.value === value),
    caseId,
    { timeout: options.timeoutMs },
  );
  await page.locator("select").first().selectOption(caseId);
  await page.getByRole("button", { name: "加载病例", exact: true }).click();
  await waitForText(page, `病例已加载：${caseId}`, 20_000);
  check("重启后病例档案可恢复", (await page.locator(".case-summary").innerText()).includes(caseId));
  await page.screenshot({ path: path.join(screenshotDir, "04-case-archive-after-restart.png"), fullPage: true });
}

async function verifyIntakeAfterRestart(page, admittedBatchId, quarantineBatchId) {
  await navigateHash(page, "#/intake");
  await waitForText(page, "医院数据准入与隔离", options.timeoutMs);
  await page.locator("details.recent-batches summary").click();
  const admitted = page.locator(".recent-batches button").filter({ hasText: admittedBatchId });
  const quarantined = page.locator(".recent-batches button").filter({ hasText: quarantineBatchId });
  await waitForLocatorCount(admitted, 1, 20_000);
  await waitForLocatorCount(quarantined, 1, 20_000);
  await admitted.click();
  await waitForText(page, `已载入准入批次：${admittedBatchId}`, 20_000);
  check("重启后准入历史仍可读取", (await page.locator(".result-list").innerText()).includes("已准入"));
  await quarantined.click();
  await waitForText(page, `已载入准入批次：${quarantineBatchId}`, 20_000);
  check("重启后隔离历史仍可读取", (await page.locator(".result-list").innerText()).includes("已隔离"));
}

async function fillIntakeHeader(page, batchId, organization, authorization) {
  await page.getByLabel("批次编号", { exact: true }).fill(batchId);
  await page.getByLabel("交接编号", { exact: true }).fill(`HANDOVER-${batchId}`);
  await page.getByLabel("来源机构", { exact: true }).fill(organization);
  await page.getByLabel("接收人", { exact: true }).fill("r28_test_receiver");
  await page.locator(".form-grid label").filter({ hasText: "机构授权状态" }).locator("select").selectOption(authorization);
  await page.getByLabel("允许用途", { exact: true }).fill("competition_research_validation");
  await page.getByLabel("脱敏方法", { exact: true }).fill("institutional export review");
}

function bundledJpeg() {
  return path.join(packageRoot, "resources", "runtime_assets", "demo_data", "ofdvdnet", "previews", "OFDVDNET_001_reference.jpg");
}

function bundledVideo() {
  return path.join(packageRoot, "resources", "runtime_assets", "demo_data", "ofdvdnet", "video", "OFDVDNET_001.mp4");
}

async function fileEndpointOk(filePath) {
  const url = `http://127.0.0.1:8001/files/download?path=${encodeURIComponent(filePath)}`;
  const response = await fetch(url);
  return response.status === 200;
}

async function fetchJson(url) {
  const response = await fetch(url);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(`${url} 返回 HTTP ${response.status}: ${JSON.stringify(payload)}`);
  return payload;
}

async function waitForText(page, text, timeoutMs) {
  await page.getByText(text, { exact: false }).first().waitFor({ state: "visible", timeout: timeoutMs });
}

async function waitForLocatorEnabled(locator, timeoutMs) {
  await locator.waitFor({ state: "visible", timeout: timeoutMs });
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (!(await locator.isDisabled())) return;
    await delay(100);
  }
  throw new Error("等待按钮启用超时");
}

async function waitForSelectorCount(page, selector, count, timeoutMs) {
  await page.waitForFunction(
    ({ selector: value, count: expected }) => document.querySelectorAll(value).length >= expected,
    { selector, count },
    { timeout: timeoutMs },
  );
}

async function waitForLocatorCount(locator, count, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if ((await locator.count()) >= count) return;
    await delay(100);
  }
  throw new Error(`等待元素数量超时：${count}`);
}

async function navigateHash(page, hash) {
  await page.evaluate((value) => window.location.hash = value, hash);
  await delay(250);
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

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function run() {
  let result;
  try {
    result = await main();
    if (browserErrors.length || failedResponses.length) {
      throw new Error(`浏览器错误 ${browserErrors.length} 项，失败响应 ${failedResponses.length} 项`);
    }
  } catch (error) {
    result = {
      status: "failed",
      packageRoot,
      runId,
      error: error instanceof Error ? error.stack || error.message : String(error),
      checks,
      browserErrors,
      failedResponses,
    };
  } finally {
    if (app) {
      try {
        await app.close();
      } catch {
        // Cleanup is best effort; the result still records the observed failure.
      }
    }
    result = result || { status: "failed", packageRoot, runId, checks, browserErrors, failedResponses };
    fs.writeFileSync(resultPath, `${JSON.stringify(result, null, 2)}\n`, "utf8");
    console.log(JSON.stringify({ ...result, resultPath }, null, 2));
    if (result.status !== "passed") process.exitCode = 1;
  }
}

await run();
