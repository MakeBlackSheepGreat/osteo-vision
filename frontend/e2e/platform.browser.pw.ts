import { expect, type Page, type Response, type TestInfo, test } from "@playwright/test";
import { Buffer } from "node:buffer";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(frontendRoot, "..", "..");
const generatedFixtureDir = path.join(repoRoot, ".pytest_tmp", "playwright", "fixtures");
const whiteFixturePath = path.join(generatedFixtureDir, "white_4k.jpg");
const fluorescenceFixturePath = path.join(generatedFixtureDir, "fluorescence_4k.jpg");
const videoFixturePath = path.join(generatedFixtureDir, "fluorescence_4k_h264.mp4");
const screenshotDir = path.join(repoRoot, "artifacts", "e2e", "browser_smoke");
const physicianReviewToken = "playwright-physician-token-20260715";
const independentPhysicianReviewToken = "playwright-independent-physician-token-20260719";
const projectEnvironment = path.join(process.env.USERPROFILE ?? "", ".conda", "envs", "osteo-vision");
const projectPython = process.env.OSTEO_E2E_PYTHON || path.join(projectEnvironment, "python.exe");
const projectFfmpeg = process.env.OSTEO_E2E_FFMPEG || path.join(projectEnvironment, "Library", "bin", "ffmpeg.exe");

test.beforeAll(() => {
  fs.mkdirSync(screenshotDir, { recursive: true });
  ensureJpegFixtures();
  ensureMp4Fixture();
});

test("browser case workflow creates, analyzes, reviews, exports, and opens data library", async ({ page }, testInfo) => {
  const browserErrors = collectBrowserErrors(page);
  await page.goto("/cases");
  await expectHealthyPage(page, "病例建立、加载与基础质控");
  await createCaseThroughUi(page, "Playwright 闭环病例");

  await page.getByRole("link", { name: "病例工作台", exact: true }).click();
  await expectHealthyPage(page, "颌骨骨髓炎术中辅助决策平台");
  await page.getByRole("tab", { name: "JPEG 图像" }).click();
  const [whiteInputResponse] = await Promise.all([
    waitForCaseInputAttachment(page),
    page.locator('input[type="file"][accept=".jpg,.jpeg,image/jpeg"]').nth(0).setInputFiles(whiteFixturePath),
  ]);
  const whiteCase = await whiteInputResponse.json();
  const whiteInput = whiteCase.inputs.find((item: { channel: string }) => item.channel === "white_light");
  expect(whiteInput.dimensions).toEqual([3840, 2160]);
  await expect(page.getByText(/白光 JPEG 已导入病例：/)).toBeVisible();
  const [fluorescenceInputResponse] = await Promise.all([
    waitForCaseInputAttachment(page),
    page.locator('input[type="file"][accept=".jpg,.jpeg,image/jpeg"]').nth(1).setInputFiles(fluorescenceFixturePath),
  ]);
  const fluorescenceCase = await fluorescenceInputResponse.json();
  const fluorescenceInput = fluorescenceCase.inputs.find(
    (item: { channel: string }) => item.channel === "fluorescence",
  );
  expect(fluorescenceInput.dimensions).toEqual([3840, 2160]);
  await expect(page.getByText(/ICG 荧光 JPEG 已导入病例：/)).toBeVisible();

  await page.getByRole("button", { name: "开始图像融合分析" }).click();
  await expect(page.getByText("分析完成，结果已同步到工作台。")).toBeVisible();
  await expect(page.locator("body")).toContainText("候选区域");
  const resultSummary = page.locator("details.sidebar-summary-details");
  await resultSummary.locator("summary").click();
  await expect(resultSummary.getByText("阳性面积占比", { exact: true })).toBeVisible();

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

  await page.getByRole("link", { name: "病例工作台", exact: true }).click();
  await expectHealthyPage(page, "颌骨骨髓炎术中辅助决策平台");
  const [videoInputResponse] = await Promise.all([
    waitForCaseInputAttachment(page),
    page.locator('input[type="file"][accept="video/mp4,.mp4"]').setInputFiles(videoFixturePath),
  ]);
  const videoCase = await videoInputResponse.json();
  const videoInput = videoCase.inputs.find((item: { channel: string }) => item.channel === "video");
  expect(videoInput.dimensions).toEqual([3840, 2160]);
  expect(videoInput.metadata.ffprobe.available).toBe(true);
  expect(videoInput.metadata.ffprobe.stream.codec_name).toBe("h264");
  await expect(page.getByText(/MP4 视频已导入病例：/)).toBeVisible({ timeout: 30_000 });

  await page.getByLabel("重点复核时间点（秒，可选）").fill("0, 0.2, 0.4");
  await page.getByRole("button", { name: "启动离线关键帧分析" }).click();
  await expect(page.getByText(/MP4 分割分析完成，已抽取 [1-9]\d* 帧，生成 [1-9]\d* 个候选区。/)).toBeVisible({ timeout: 120_000 });
  await expect(page.getByText("MP4 分割时间轴")).toBeVisible();
  const liveFrameResponses: Array<{ overlayPath: string }> = [];
  const recordLiveFrameResponse = async (response: Response) => {
    if (
      /\/cases\/[^/]+\/live-frames$/.test(new URL(response.url()).pathname) &&
      response.request().method() === "POST" &&
      response.status() === 200
    ) {
      const payload = (await response.json()) as { overlay_path?: string };
      if (payload.overlay_path) liveFrameResponses.push({ overlayPath: payload.overlay_path });
    }
  };
  page.on("response", recordLiveFrameResponse);
  await page.locator("video.video-stream-player").evaluate(async (video) => {
    video.loop = true;
    await video.play();
  });
  await expect.poll(() => liveFrameResponses.length, { timeout: 120_000 }).toBeGreaterThanOrEqual(2);
  page.off("response", recordLiveFrameResponse);
  expect(liveFrameResponses[0]?.overlayPath).not.toBe(liveFrameResponses[1]?.overlayPath);
  await expect(page.locator("img.live-segmentation-overlay")).toBeVisible();
  await expect(page.locator(".live-frame-status")).toContainText("MP4 实时分割已更新");
  await page.locator("video.video-stream-player").evaluate((video) => video.pause());
  const timelineManifest = page.getByLabel("时间轴清单");
  await timelineManifest.locator("summary").click();
  await expect(timelineManifest).toContainText("全时长低频索引");
  await expect(timelineManifest).toContainText("候选轨迹");
  await expect(page.locator(".hotspot-timeline-item").first()).toBeVisible();
  await expect(page.locator('[aria-label="当前帧详情"]')).toContainText("最大候选框");
  const positiveAreaFilter = page.getByRole("button", { name: "阳性面积", exact: true });
  await positiveAreaFilter.click();
  await expect(positiveAreaFilter).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".hotspot-timeline-item").first()).toBeVisible();
  const withCandidatesFilter = page.getByRole("button", { name: "有候选", exact: true });
  await withCandidatesFilter.click();
  await expect(withCandidatesFilter).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".hotspot-timeline-item").first()).toBeVisible();
  const selectedFrameButton = page.locator(".hotspot-timeline-item").first();
  await selectedFrameButton.click();
  await expect(selectedFrameButton).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator('[aria-label="当前帧详情"]')).toContainText("候选数量");
  await page.getByRole("button", { name: "重算当前帧" }).click();
  await expect(page.getByText(/当前帧重算完成，已抽取 1 帧，生成 [1-9]\d* 个热点候选区。/)).toBeVisible({ timeout: 120_000 });
  await expect(page.locator('[aria-label="当前帧详情"]')).toContainText("最大候选框");
  await page.getByRole("link", { name: /医生复核/ }).click();
  await expectHealthyPage(page, "候选区域与 ROI 判读");
  const firstHotspotCandidate = page.locator(".candidate-list li").first();
  await firstHotspotCandidate.getByRole("button", { name: "编辑框" }).click();
  await expect(page.getByRole("heading", { name: "候选框几何编辑" })).toBeVisible();
  await drawManualRoi(page, "保存候选框");
  await page.getByRole("button", { name: "保存候选框" }).click();
  await expect(firstHotspotCandidate).toContainText("已修改");
  await page.getByRole("link", { name: "病例工作台", exact: true }).click();
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
  await expect(page.locator(".library-status")).toContainText("视频已导入病例");
  await expect(firstCandidate.getByRole("button", { name: "已导入" })).toBeDisabled();

  await page.getByRole("link", { name: /病例档案/ }).click();
  await expectHealthyPage(page, "病例建立、加载与基础质控");
  await expect(page.locator(".asset-stack li").filter({ hasText: "短视频 / 摄像头" })).toHaveCount(1);
  await page.getByRole("link", { name: "病例工作台", exact: true }).click();
  await expect(page.getByText("术中 MP4 视频")).toBeVisible();
  await expect(page.locator(".selected-input-path")).not.toHaveText("尚未选择 MP4 文件");
  await capturePage(page, testInfo, "05-video-library-import.png");

  expect(browserErrors).toEqual([]);
});

test("browser failure states show actionable upload and analysis errors", async ({ page }, testInfo) => {
  const browserErrors = collectBrowserErrors(page);
  await page.goto("/cases");
  await expectHealthyPage(page, "病例建立、加载与基础质控");
  await createCaseThroughUi(page, "Playwright 失败态病例");

  await page.getByRole("link", { name: "病例工作台", exact: true }).click();
  await expectHealthyPage(page, "颌骨骨髓炎术中辅助决策平台");
  await page.getByRole("tab", { name: "JPEG 图像" }).click();
  await page.locator('input[type="file"][accept=".jpg,.jpeg,image/jpeg"]').first().setInputFiles({
    name: "captcha.jpg",
    mimeType: "image/jpeg",
    buffer: Buffer.from("<html><body>captcha</body></html>", "utf8"),
  });
  await expect(page.getByText("上传文件内容与图片后缀不匹配")).toBeVisible();
  await capturePage(page, testInfo, "06-upload-error-state.png");

  await expect(page.getByRole("button", { name: "开始图像融合分析" })).toBeDisabled();
  await expect(page.locator(".image-pair-status")).toContainText("未选择");
  await expect(page.locator(".analysis-card")).toContainText("等待融合图输出");
  await capturePage(page, testInfo, "07-analysis-failure-state.png");

  expect(browserErrors.filter((message) => !message.includes("status of 415"))).toEqual([]);
});

test("browser physician annotation workflow persists versions, review, and training admission", async ({ page }, testInfo) => {
  const browserErrors = collectBrowserErrors(page);
  await page.goto("/cases");
  await expectHealthyPage(page, "病例建立、加载与基础质控");
  await createCaseThroughUi(page, "Playwright 医生标注病例");

  await page.getByRole("link", { name: "病例工作台", exact: true }).click();
  await expectHealthyPage(page, "颌骨骨髓炎术中辅助决策平台");
  await page.getByRole("tab", { name: "JPEG 图像" }).click();
  await Promise.all([
    waitForCaseInputAttachment(page),
    page.locator('input[type="file"][accept=".jpg,.jpeg,image/jpeg"]').nth(0).setInputFiles(whiteFixturePath),
  ]);
  await expect(page.getByText(/白光 JPEG 已导入病例：/)).toBeVisible();
  await Promise.all([
    waitForCaseInputAttachment(page),
    page.locator('input[type="file"][accept=".jpg,.jpeg,image/jpeg"]').nth(1).setInputFiles(fluorescenceFixturePath),
  ]);
  await expect(page.getByText(/ICG 荧光 JPEG 已导入病例：/)).toBeVisible();

  await page.getByRole("link", { name: "人工标注", exact: true }).click();
  await expectHealthyPage(page, "病灶人工标注");
  await page.getByLabel("复核访问令牌").fill(physicianReviewToken);
  await page.getByRole("button", { name: "核验身份" }).click();
  await expect(page.getByText("医生复核 · playwright-physician-001")).toBeVisible();

  const sourceRows = page.locator(".source-row");
  await expect(sourceRows).toHaveCount(2);
  await sourceRows.nth(1).click();
  await expect(sourceRows.nth(1)).toHaveClass(/selected/);
  await expect(page.getByAltText("医生人工标注来源图像")).toBeVisible();
  await expect(page.getByRole("button", { name: "画笔" })).toBeEnabled();

  await drawAnnotationStroke(page, 0.28, 0.38, 0.44, 0.5);
  await expect(page.locator(".annotation-canvas__meta")).toContainText("1 个标注操作");
  await page.getByRole("button", { name: "撤销" }).click();
  await expect(page.locator(".annotation-canvas__meta")).toContainText("0 个标注操作");
  await page.getByRole("button", { name: "重做" }).click();
  await expect(page.locator(".annotation-canvas__meta")).toContainText("1 个标注操作");

  await page.getByRole("button", { name: "多边形" }).click();
  await drawAnnotationPolygon(page);
  await page.getByRole("button", { name: "闭合" }).click();
  await expect(page.locator(".annotation-canvas__meta")).toContainText("2 个标注操作");

  const [createResponse] = await Promise.all([
    page.waitForResponse(
      (response) =>
        /\/cases\/[^/]+\/annotations$/.test(new URL(response.url()).pathname) &&
        response.request().method() === "POST" &&
        response.status() === 201,
    ),
    page.getByRole("button", { name: "保存草稿" }).click(),
  ]);
  const created = await createResponse.json();
  expect(created.status).toBe("draft");
  expect(created.current_version).toBe(1);
  expect(created.original_width).toBe(3840);
  expect(created.original_height).toBe(2160);
  expect(created.geometry.operations.map((operation: { tool: string }) => operation.tool)).toEqual(["brush", "polygon"]);
  expect(created.mask_path).toMatch(/\.png$/);
  await expect(page.getByText(/已保存为 v1/)).toBeVisible();
  await expect(page.locator(".version-history li")).toHaveCount(1);

  await expect(page.getByRole("button", { name: "画笔" })).toBeEnabled();
  await page.getByRole("button", { name: "画笔" }).click();
  await drawAnnotationStroke(page, 0.56, 0.44, 0.66, 0.57);
  const submitButton = page.getByRole("button", { name: "提交复核" });
  await expect(submitButton).toBeDisabled();
  await expect(submitButton).toHaveAttribute("title", "请先保存或放弃当前修改");

  const [versionResponse] = await Promise.all([
    page.waitForResponse(
      (response) =>
        /\/cases\/[^/]+\/annotations\/[^/]+\/versions$/.test(new URL(response.url()).pathname) &&
        response.request().method() === "PUT" &&
        response.status() === 200,
    ),
    page.getByRole("button", { name: "保存新版本" }).click(),
  ]);
  const versioned = await versionResponse.json();
  expect(versioned.current_version).toBe(2);
  expect(versioned.geometry.operations).toHaveLength(3);
  await expect(page.getByText(/已保存为 v2/)).toBeVisible();
  await expect(page.locator(".version-history li")).toHaveCount(2);
  await expect(page.locator(".version-history")).toContainText("v1");
  await expect(page.locator(".version-history")).toContainText("v2");

  const [submitResponse] = await Promise.all([
    page.waitForResponse(
      (response) =>
        /\/cases\/[^/]+\/annotations\/[^/]+\/submit$/.test(new URL(response.url()).pathname) &&
        response.request().method() === "POST" &&
        response.status() === 200,
    ),
    submitButton.click(),
  ]);
  expect((await submitResponse.json()).status).toBe("submitted");
  await expect(page.getByText("标注已提交医生复核，编辑已锁定。")).toBeVisible();
  await expect(page.getByRole("button", { name: "画笔" })).toBeDisabled();

  await page.getByRole("button", { name: "退出复核身份" }).click();
  await page.getByLabel("复核访问令牌").fill(independentPhysicianReviewToken);
  await page.getByRole("button", { name: "核验身份" }).click();
  await expect(page.getByText("医生复核 · playwright-physician-002")).toBeVisible();

  const [reviewResponse] = await Promise.all([
    page.waitForResponse(
      (response) =>
        /\/cases\/[^/]+\/annotations\/[^/]+\/review$/.test(new URL(response.url()).pathname) &&
        response.request().method() === "POST" &&
        response.status() === 200,
    ),
    page.getByRole("button", { name: "接受标注" }).click(),
  ]);
  const accepted = await reviewResponse.json();
  expect(accepted.status).toBe("accepted");
  expect(accepted.training_eligible).toBe(false);
  expect(accepted.sample_weight).toBe(0);
  expect(accepted.training_exclusion_reason).toBe("case_intake_metadata_missing");
  await expect(page.locator(".annotation-record")).toContainText("已接受");
  await expect(page.locator(".annotation-record")).toContainText("尚未准入");
  await expect(page.locator(".annotation-record")).toContainText("病例缺少批次准入记录");
  await expect(page.locator(".annotation-record")).toContainText("0.00");

  const [manifestResponse] = await Promise.all([
    page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === "/annotation-training-manifests" &&
        response.request().method() === "POST" &&
        response.status() === 201,
    ),
    page.getByRole("button", { name: "生成训练清单" }).click(),
  ]);
  const manifest = await manifestResponse.json();
  expect(manifest.eligible_count).toBe(0);
  expect(manifest.excluded_count).toBe(1);
  expect(manifest.records).toHaveLength(0);
  await expect(page.getByText("训练清单已生成：0 条准入，1 条隔离。")).toBeVisible();
  await expect(page.locator(".training-section p")).toContainText("annotation_training_manifest");
  await expectStableViewport(page);
  await capturePage(page, testInfo, "08-manual-annotation-workflow.png");

  expect(browserErrors).toEqual([]);
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

async function drawAnnotationStroke(
  page: Page,
  startXRatio: number,
  startYRatio: number,
  endXRatio: number,
  endYRatio: number,
): Promise<void> {
  const canvas = page.getByLabel("病灶人工标注层");
  const box = await canvas.boundingBox();
  expect(box).not.toBeNull();
  if (!box) return;
  await page.mouse.move(box.x + box.width * startXRatio, box.y + box.height * startYRatio);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * endXRatio, box.y + box.height * endYRatio, { steps: 8 });
  await page.mouse.up();
}

async function drawAnnotationPolygon(page: Page): Promise<void> {
  const canvas = page.getByLabel("病灶人工标注层");
  const box = await canvas.boundingBox();
  expect(box).not.toBeNull();
  if (!box) return;
  for (const [xRatio, yRatio] of [
    [0.48, 0.28],
    [0.7, 0.34],
    [0.62, 0.66],
  ]) {
    await page.mouse.click(box.x + box.width * xRatio, box.y + box.height * yRatio);
  }
}

async function capturePage(page: Page, testInfo: TestInfo, fileName: string): Promise<void> {
  const screenshotPath = path.join(screenshotDir, fileName);
  await page.screenshot({ path: screenshotPath, fullPage: true });
  await testInfo.attach(fileName, { path: screenshotPath, contentType: "image/png" });
}

function waitForCaseInputAttachment(page: Page): Promise<Response> {
  return page.waitForResponse(
    (response) =>
      /^\/cases\/[^/]+\/inputs$/.test(new URL(response.url()).pathname) &&
      response.request().method() === "POST" &&
      response.status() === 200,
  );
}

function ensureJpegFixtures(): void {
  fs.mkdirSync(generatedFixtureDir, { recursive: true });
  for (const [sourcePath, jpegPath] of [
    [path.join(repoRoot, "tests", "fixtures", "platform", "white.png"), whiteFixturePath],
    [path.join(repoRoot, "tests", "fixtures", "platform", "fluorescence.png"), fluorescenceFixturePath],
  ]) {
    if (fs.existsSync(jpegPath)) continue;
    const scriptPath = path.join(path.dirname(jpegPath), `convert_${path.basename(jpegPath, ".jpg")}_fixture.py`);
    const script = `
from pathlib import Path
from PIL import Image
source = Path(r"${sourcePath.replaceAll("\\", "\\\\")}")
target = Path(r"${jpegPath.replaceAll("\\", "\\\\")}")
target.parent.mkdir(parents=True, exist_ok=True)
Image.open(source).convert("RGB").resize((3840, 2160), Image.Resampling.BICUBIC).save(target, "JPEG", quality=95)
`;
    fs.writeFileSync(scriptPath, script, "utf8");
    execFileSync(projectPython, [scriptPath], {
      cwd: repoRoot,
      env: { ...process.env, PYTHONIOENCODING: "utf-8" },
      stdio: "pipe",
    });
  }
}

function ensureMp4Fixture(): void {
  if (fs.existsSync(videoFixturePath)) return;
  fs.mkdirSync(generatedFixtureDir, { recursive: true });
  execFileSync(
    projectFfmpeg,
    [
      "-y",
      "-f",
      "lavfi",
      "-i",
      "color=c=#181f25:s=3840x2160:r=6:d=2",
      "-vf",
      "drawbox=x=300+500*t:y=760:w=520:h=520:color=#00c98d:t=fill,drawbox=x=2600:y=480:w=560:h=560:color=#36a7d8:t=fill",
      "-c:v",
      "libx264",
      "-preset",
      "ultrafast",
      "-crf",
      "28",
      "-pix_fmt",
      "yuv420p",
      "-movflags",
      "+faststart",
      videoFixturePath,
    ],
    {
      cwd: repoRoot,
      env: { ...process.env },
      stdio: "pipe",
    },
  );
}
