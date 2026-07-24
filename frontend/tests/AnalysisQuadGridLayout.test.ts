import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

describe("analysis quad grid layout", () => {
  it("keeps the right-side analysis results column wide enough for desktop review", () => {
    const source = readFileSync(resolve(process.cwd(), "src/components/AnalysisQuadGrid.vue"), "utf8");

    expect(source).toContain("grid-template-columns: minmax(0, 2fr) minmax(320px, 1fr);");
    expect(source).toContain("min-height: clamp(680px, 72vh, 860px);");
    expect(source).toMatch(/\.camera-live-player\s*\{[\s\S]*?object-fit: contain;/);
    expect(source).toMatch(/\.live-segmentation-overlay\s*\{[\s\S]*?object-fit: contain;/);
  });
});
