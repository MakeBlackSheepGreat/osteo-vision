import { expect, type Page, type TestInfo, test } from "@playwright/test";
import { Buffer } from "node:buffer";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(frontendRoot, "..", "..");
const whiteFixturePath = path.join(repoRoot, "tests", "fixtures", "platform", "white.png");
const fluorescenceFixturePath = path.join(repoRoot, "tests", "fixtures", "platform", "fluorescence.png");
const syntheticVideoPath = path.join(repoRoot, ".pytest_tmp", "playwright", "fixtures", "synthetic_icg_hotspot.mp4");
const screenshotDir = path.join(repoRoot, "artifacts", "e2e", "browser_smoke");

test.beforeAll(() => {
  fs.mkdirSync(screenshotDir, { recursive: true });
  ensureSyntheticVideoFixture();
});

test("browser case workflow creates, analyzes, reviews, exports, and opens data library", async ({ page }, testInfo) => {
  const browserErrors = collectBrowserErrors(page);
  await page.goto("/cases");
  await expectHealthyPage(page, "病例建立、加载与基础质控");
  await createCaseThroughUi(page, "Playwright 闭环病例");

  await page.getByRole("link", { name: /病例工作台/ }).click();
  await expectHealthyPage(page, "颌骨骨髓炎术中辅助决策平台");
  await page.getByLabel("白光图像路径").fill(whiteFixturePath);
  await page.getByLabel("ICG 荧光图像路径").fill(fluorescenceFixturePath);
  await page.getByRole("button", { name: "写入双通道" }).click();
  await expect(page.getByText("双通道输入已写入病例。")).toBeVisible();

  await page.getByRole("button", { name: "双通道分析" }).click();
  await expect(page.getByText("分析完成，结果已同步到工作台。")).toBeVisible();
  await expect(page.locator("body")).toContainText("候选区域");
  await expect(page.getByText("阳性面积")).toBeVisible();

  await page.getByRole("button", { name: "导出证据包" }).click();
  await expect(page.getByText("证据包已导出", { exact: true })).toBeVisible();
  await capturePage(page, testInfo, "01-case-workspace.png");

  await page.getByRole("link", { name: /医生复核/ }).click();
  await expectHealthyPage(page, "候选区域与 ROI 判读");
  await expect(page.locator("body")).toContainText("候选区域");
  const firstReviewCandidate = page.locator(".candidate-list li").first();
  await firstReviewCandidate.getByRole("button", { name: "接受" }).click();
  await expect(firstReviewCandidate).toContainText("已接受");
  await drawManualRoi(page);
  await page.getByRole("button", { name: "保存 ROI" }).click();
  await expect(page.getByText("已保存 ROI 可随证据包导出。")).toBeVisible();
  await capturePage(page, testInfo, "02-review-workspace.png");

  await page.getByRole("link", { name: /报告导出/ }).click();
  await expectHealthyPage(page, "病例证据包预览");

  await page.getByRole("link", { name: /视频库/ }).click();
  await expectHealthyPage(page, "公开代理视频库");
  await expect(page.locator(".candidate-card").first()).toBeVisible();
  await capturePage(page, testInfo, "03-data-library.png");

  expect(browserErrors).toEqual([]);
});

test("browser MP4 upload analysis and public-video import stay usable", async ({ page }, testInfo) => {
  const browserErrors = collectBrowserErrors(page);
  await page.goto("/cases");
  await expectHealthyPage(page, "病例建立、加载与基础质控");
  await createCaseThroughUi(page, "Playwright MP4 闭环病例");

  await page.getByRole("link", { name: /病例工作台/ }).click();
  await expectHealthyPage(page, "颌骨骨髓炎术中辅助决策平台");
  await page.locator('input[type="file"][accept="video/mp4,.mp4"]').setInputFiles(syntheticVideoPath);
  await expect(page.getByText(/MP4 视频已上传：/)).toBeVisible({ timeout: 120_000 });

  await page.getByLabel("关键时间点（秒）").fill("0, 0.2, 0.4");
  await page.getByRole("button", { name: "MP4关键帧" }).click();
  await expect(page.getByText(/MP4 分割分析完成，已抽取 [1-9]\d* 帧，生成 [1-9]\d* 个候选区。/)).toBeVisible({ timeout: 120_000 });
  await expect(page.getByText("MP4 分割时间轴")).toBeVisible();
  await expect(page.getByLabel("时间轴 Manifest")).toContainText("全时长低频索引");
  await expect(page.getByLabel("时间轴 Manifest")).toContainText("候选 Trace");
  await expect(page.locator(".hotspot-timeline-item").first()).toBeVisible();
  await expect(page.locator('[aria-label="当前帧详情"]')).toContainText("Top BBox");
  const positiveAreaFilter = page.getByRole("button", { name: "阳性面积", exact: true });
  await positiveAreaFilter.click();
  await expect(positiveAreaFilter).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".hotspot-timeline-item").first()).toBeVisible();
  const withCandidatesFilter = page.getByRole("button", { name: "有候选", exact: true });
  await withCandidatesFilter.click();
  await expect(withCandidatesFilter).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".hotspot-timeline-item").first()).toBeVisible();
  const frameOneButton = page.getByRole("button", { name: /帧 1/ });
  await frameOneButton.click();
  await expect(frameOneButton).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".analysis-card")).toContainText("keyframe_02_f000001");
  await page.getByRole("button", { name: "重算当前帧" }).click();
  await expect(page.getByText(/当前帧重算完成，已抽取 1 帧，生成 [1-9]\d* 个热点候选区。/)).toBeVisible({ timeout: 120_000 });
  await expect(page.locator('[aria-label="当前帧详情"]')).toContainText("Top BBox");
  await page.getByRole("link", { name: /医生复核/ }).click();
  await expectHealthyPage(page, "候选区域与 ROI 判读");
  const firstHotspotCandidate = page.locator(".candidate-list li").first();
  await firstHotspotCandidate.getByRole("button", { name: "编辑框" }).click();
  await expect(page.getByRole("heading", { name: "候选框几何编辑" })).toBeVisible();
  await drawManualRoi(page, "保存候选框");
  await page.getByRole("button", { name: "保存候选框" }).click();
  await expect(firstHotspotCandidate).toContainText("已修改");
  await page.getByRole("link", { name: /病例工作台/ }).click();
  await expectHealthyPage(page, "颌骨骨髓炎术中辅助决策平台");
  await capturePage(page, testInfo, "04-mp4-hotspot-workflow.png");

  await page.getByRole("link", { name: /病例档案/ }).click();
  await expectHealthyPage(page, "病例建立、加载与基础质控");
  await createCaseThroughUi(page, "Playwright 视频库导入病例");
  await page.getByRole("link", { name: /视频库/ }).click();
  await expectHealthyPage(page, "公开代理视频库");
  const firstCandidate = page.locator(".candidate-card").first();
  await expect(firstCandidate).toBeVisible();
  await Promise.all([
    page.waitForResponse((response) => response.url().includes("/video-library/") && response.request().method() === "POST"),
    firstCandidate.getByRole("button", { name: "导入病例" }).click(),
  ]);

  await page.getByRole("link", { name: /病例档案/ }).click();
  await expectHealthyPage(page, "病例建立、加载与基础质控");
  await expect(page.locator(".asset-stack li").filter({ hasText: "短视频 / 摄像头" })).toHaveCount(1);
  await page.getByRole("link", { name: /病例工作台/ }).click();
  await expect(page.getByLabel("官方 MP4 视频路径")).not.toHaveValue("");
  await capturePage(page, testInfo, "05-video-library-import.png");

  expect(browserErrors).toEqual([]);
});

test("mobile viewport and fullscreen analysis stay framed", async ({ page }, testInfo) => {
  const browserErrors = collectBrowserErrors(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/cases");
  await expectHealthyPage(page, "病例建立、加载与基础质控");
  await createCaseThroughUi(page, "Playwright 移动端布局病例");

  await page.getByRole("link", { name: /病例工作台/ }).click();
  await expectHealthyPage(page, "颌骨骨髓炎术中辅助决策平台");
  await page.getByLabel("白光图像路径").fill(whiteFixturePath);
  await page.getByLabel("ICG 荧光图像路径").fill(fluorescenceFixturePath);
  await page.getByRole("button", { name: "写入双通道" }).click();
  await expect(page.getByText("双通道输入已写入病例。")).toBeVisible();
  await page.getByRole("button", { name: "双通道分析" }).click();
  await expect(page.getByText("分析完成，结果已同步到工作台。")).toBeVisible();
  await expectHealthyPage(page, "颌骨骨髓炎术中辅助决策平台");
  await capturePage(page, testInfo, "06-mobile-case-workspace.png");

  await page.getByRole("button", { name: "进入全屏分析视图" }).click();
  await expect(page.getByRole("dialog", { name: "全屏分析视图" })).toBeVisible();
  await expect(page.locator(".analysis-fullscreen .analysis-quad-card").first()).toBeVisible();
  await expectStableViewport(page);
  await capturePage(page, testInfo, "07-mobile-analysis-fullscreen.png");
  await page.getByRole("button", { name: "关闭全屏分析视图" }).click();
  await expect(page.getByRole("dialog", { name: "全屏分析视图" })).toBeHidden();

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole("button", { name: "进入全屏分析视图" }).click();
  await expect(page.getByRole("dialog", { name: "全屏分析视图" })).toBeVisible();
  await expectStableViewport(page);
  await capturePage(page, testInfo, "08-desktop-analysis-fullscreen.png");

  expect(browserErrors).toEqual([]);
});

test("browser failure states show actionable upload and analysis errors", async ({ page }, testInfo) => {
  const browserErrors = collectBrowserErrors(page);
  await page.goto("/cases");
  await expectHealthyPage(page, "病例建立、加载与基础质控");
  await createCaseThroughUi(page, "Playwright 失败态病例");

  await page.getByRole("link", { name: /病例工作台/ }).click();
  await expectHealthyPage(page, "颌骨骨髓炎术中辅助决策平台");
  await page.locator('input[type="file"][accept="image/*"]').first().setInputFiles({
    name: "captcha.jpg",
    mimeType: "image/jpeg",
    buffer: Buffer.from("<html><body>captcha</body></html>", "utf8"),
  });
  await expect(page.getByText("上传文件内容与图片后缀不匹配")).toBeVisible();
  await capturePage(page, testInfo, "09-upload-error-state.png");

  await page.getByRole("button", { name: "双通道分析" }).click();
  await expect(page.getByText("需要同时提供白光和 ICG 荧光输入后才能进行融合分析。")).toBeVisible();
  await expect(page.locator(".analysis-card")).toContainText("未通过");
  await capturePage(page, testInfo, "10-analysis-failure-state.png");

  expect(browserErrors.filter((message) => !message.includes("status of 415"))).toEqual([]);
});

function collectBrowserErrors(page: Page): string[] {
  const browserErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") browserErrors.push(message.text());
  });
  page.on("pageerror", (error) => browserErrors.push(error.message));
  return browserErrors;
}

async function createCaseThroughUi(page: Page, title: string): Promise<void> {
  await page.getByLabel("病例标题").fill(`${title} ${Date.now()}`);
  await page.getByRole("button", { name: "新建病例" }).click();
  await expect(page.getByText(/病例已创建：case_/)).toBeVisible();
}

async function expectHealthyPage(page: Page, heading: string): Promise<void> {
  await expect(page.getByRole("heading", { name: heading })).toBeVisible();
  await expect(page.locator("body")).not.toContainText("Internal Server Error");
  await expect(page.locator("body")).not.toContainText("Cannot GET");
  await expectStableViewport(page);
}

async function expectStableViewport(page: Page): Promise<void> {
  const metrics = await page.evaluate(() => {
    const bodyText = document.body.innerText.trim();
    return {
      textLength: bodyText.length,
      horizontalOverflow: Math.max(0, document.documentElement.scrollWidth - window.innerWidth),
      blankImages: Array.from(document.images).filter((image) => image.complete && image.naturalWidth === 0).length,
      fullscreenOverflow: (() => {
        const fullscreen = document.querySelector(".analysis-fullscreen");
        if (!fullscreen) return 0;
        return Math.max(0, fullscreen.scrollWidth - fullscreen.clientWidth);
      })(),
    };
  });
  expect(metrics.textLength).toBeGreaterThan(80);
  expect(metrics.horizontalOverflow).toBeLessThanOrEqual(8);
  expect(metrics.fullscreenOverflow).toBeLessThanOrEqual(8);
  expect(metrics.blankImages).toBe(0);
}

async function drawManualRoi(page: Page, saveButtonName = "保存 ROI"): Promise<void> {
  const canvas = page.getByLabel("ROI 手动矩形标注画布");
  const box = await canvas.boundingBox();
  expect(box).not.toBeNull();
  if (!box) return;
  await page.mouse.move(box.x + box.width * 0.24, box.y + box.height * 0.26);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.62, box.y + box.height * 0.58, { steps: 6 });
  await page.mouse.up();
  await expect(page.getByRole("button", { name: saveButtonName })).toBeEnabled();
}

async function capturePage(page: Page, testInfo: TestInfo, fileName: string): Promise<void> {
  const screenshotPath = path.join(screenshotDir, fileName);
  await page.screenshot({ path: screenshotPath, fullPage: true });
  await testInfo.attach(fileName, { path: screenshotPath, contentType: "image/png" });
}

function ensureSyntheticVideoFixture(): void {
  if (fs.existsSync(syntheticVideoPath)) return;
  fs.mkdirSync(path.dirname(syntheticVideoPath), { recursive: true });
  const scriptPath = path.join(path.dirname(syntheticVideoPath), "create_synthetic_video.py");
  const script = `
from pathlib import Path
import cv2
import numpy as np
path = Path(r"${syntheticVideoPath.replaceAll("\\", "\\\\")}")
path.parent.mkdir(parents=True, exist_ok=True)
writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 5.0, (96, 96))
for idx in range(12):
    frame = np.zeros((96, 96, 3), dtype=np.uint8)
    frame[:, :] = (24, 24, 24)
    center = (20 + idx * 5, 48)
    cv2.circle(frame, center, 14, (0, 255, 0), -1)
    cv2.rectangle(frame, (54, 22), (78, 46), (0, 180, 0), -1)
    writer.write(frame)
writer.release()
`;
  fs.writeFileSync(scriptPath, script, "utf8");
  execFileSync("conda", ["run", "-n", "osteo-vision", "python", scriptPath], {
    cwd: repoRoot,
    env: { ...process.env, PYTHONIOENCODING: "utf-8" },
    stdio: "pipe",
  });
}
