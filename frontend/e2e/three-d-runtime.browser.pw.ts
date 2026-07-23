import { expect, type FrameLocator, type Page, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(frontendRoot, "..", "..");
const backendPort = Number(process.env.OSTEO_E2E_BACKEND_PORT ?? "18991");
const threeDRuntimePort = Number(process.env.OSTEO_E2E_THREE_D_RUNTIME_PORT ?? "15192");
const e2eRunId = process.env.OSTEO_E2E_RUN_ID;

if (!e2eRunId) {
  throw new Error("OSTEO_E2E_RUN_ID must be initialized by frontend/playwright.config.ts.");
}

const d024FixturePath = path.join(
  repoRoot,
  ".pytest_tmp",
  "playwright",
  e2eRunId,
  "artifacts",
  "three_d_runtime",
  "references",
  "d024",
  "mandible_d024_0001.stl",
);
const backendOrigin = `http://127.0.0.1:${backendPort}`;
const runtimeOrigin = `http://127.0.0.1:${threeDRuntimePort}`;

test.describe.configure({ mode: "serial" });

test.afterEach(() => {
  restoreD024Fixture();
});

test("independent renderer loads the controlled D024 scene through the iframe bridge", async ({ page }) => {
  const snapshotResponse = page.waitForResponse((response) =>
    isBackendRuntimeResponse(response.url(), "/three-d-runtime/v1/references/d024/snapshot"),
  );
  const assetResponse = page.waitForResponse((response) =>
    isBackendRuntimeResponse(response.url(), "/three-d-runtime/v1/references/d024/assets/model"),
  );

  await page.goto("/showcase");
  const snapshot = await snapshotResponse;
  const asset = await assetResponse;

  expect(snapshot.status()).toBe(200);
  expect(asset.status()).toBe(200);
  expect(asset.headers()["content-type"]).toContain("model/stl");
  expect(asset.headers()["cache-control"]).toBe("private, no-store");
  expect(asset.headers()["access-control-allow-origin"]).toBe(runtimeOrigin);

  const snapshotPayload = (await snapshot.json()) as {
    model_asset?: { format?: string; size_bytes?: number } | null;
    safety?: { navigation_level?: string; navigation_ready?: boolean };
  };
  expect(snapshotPayload.model_asset?.format).toBe("stl");
  expect(snapshotPayload.model_asset?.size_bytes).toBeGreaterThan(100);
  expect(snapshotPayload.safety).toMatchObject({ navigation_level: "L0", navigation_ready: false });

  const embed = page.locator(".three-d-runtime-embed");
  await expect(embed).toHaveAttribute("data-state", "ready", { timeout: 60_000 });
  const frame = page.frameLocator('iframe[title="独立三维渲染工作区"]');
  await expect(frame.locator(".three-d-viewport")).toHaveAttribute("data-state", "ready", { timeout: 60_000 });
  await expect(frame.locator("canvas")).toBeVisible();
  const hasWebGlContext = await frame.locator("canvas").evaluate((element) => {
    const canvas = element as HTMLCanvasElement;
    return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  });
  expect(hasWebGlContext).toBe(true);

  await expect
    .poll(async () => JSON.stringify(await readCanvasScreenshotPixels(page, frame)), { timeout: 30_000, intervals: [500] })
    .toContain('"hasRenderedGeometry":true');
});

test("independent renderer keeps a readable reference state when the D024 model asset is unavailable", async ({ page }) => {
  fs.rmSync(d024FixturePath, { force: true });
  const snapshotResponse = page.waitForResponse((response) =>
    isBackendRuntimeResponse(response.url(), "/three-d-runtime/v1/references/d024/snapshot"),
  );

  await page.goto(`${runtimeOrigin}/?referenceId=d024&assetState=missing`);
  const snapshot = await snapshotResponse;

  expect(snapshot.status()).toBe(200);
  const snapshotPayload = (await snapshot.json()) as { model_asset?: unknown; safety?: { navigation_ready?: boolean } };
  expect(snapshotPayload.model_asset).toBeNull();
  expect(snapshotPayload.safety?.navigation_ready).toBe(false);
  await expect(page.locator(".three-d-viewport")).toHaveAttribute("data-state", "reference");
  await expect(page.getByText("没有可渲染的三维模型")).toBeVisible();
  await expect(page.locator(".runtime-status")).toContainText("未提供模型");
  await expect(page.locator("canvas")).toHaveCount(0);
});

function isBackendRuntimeResponse(url: string, pathname: string): boolean {
  const parsed = new URL(url);
  return parsed.origin === backendOrigin && parsed.pathname === pathname;
}

async function readCanvasScreenshotPixels(page: Page, frame: FrameLocator): Promise<{
  hasRenderedGeometry: boolean;
  sampledColorCount: number;
  nonBackgroundSamples: number;
}> {
  const screenshot = await frame.locator("canvas").screenshot();
  return page.evaluate(async (pngBase64) => {
    const image = new Image();
    image.src = `data:image/png;base64,${pngBase64}`;
    await image.decode();
    const canvas = document.createElement("canvas");
    canvas.width = image.naturalWidth;
    canvas.height = image.naturalHeight;
    const context = canvas.getContext("2d", { willReadFrequently: true });
    if (!context || !canvas.width || !canvas.height) {
      return { hasRenderedGeometry: false, sampledColorCount: 0, nonBackgroundSamples: 0 };
    }
    context.drawImage(image, 0, 0);
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
    const sampleStride = Math.max(1, Math.ceil((canvas.width * canvas.height) / 20_000));
    const colors = new Set<string>();
    let nonBackgroundSamples = 0;
    for (let pixel = 0; pixel < canvas.width * canvas.height; pixel += sampleStride) {
      const offset = pixel * 4;
      const red = pixels[offset];
      const green = pixels[offset + 1];
      const blue = pixels[offset + 2];
      const alpha = pixels[offset + 3];
      colors.add(`${red},${green},${blue},${alpha}`);
      if (red !== 17 || green !== 26 || blue !== 30 || alpha !== 255) nonBackgroundSamples += 1;
    }
    return {
      hasRenderedGeometry: nonBackgroundSamples > 10 && colors.size > 1,
      sampledColorCount: colors.size,
      nonBackgroundSamples,
    };
  }, screenshot.toString("base64"));
}

function restoreD024Fixture(): void {
  fs.mkdirSync(path.dirname(d024FixturePath), { recursive: true });
  fs.writeFileSync(
    d024FixturePath,
    [
      "solid osteo_vision_e2e_d024",
      "facet normal 0 0 1",
      "outer loop",
      "vertex 0 0 0",
      "vertex 48 0 0",
      "vertex 0 32 0",
      "endloop",
      "endfacet",
      "facet normal 0 0 1",
      "outer loop",
      "vertex 48 0 0",
      "vertex 48 32 0",
      "vertex 0 32 0",
      "endloop",
      "endfacet",
      "endsolid osteo_vision_e2e_d024",
      "",
    ].join("\n"),
    "utf8",
  );
}
