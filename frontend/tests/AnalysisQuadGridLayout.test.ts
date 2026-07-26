import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

describe("analysis quad grid layout", () => {
  it("uses a balanced desktop 2-by-2 layout for single-video analysis", () => {
    const source = readFileSync(resolve(process.cwd(), "src/components/AnalysisQuadGrid.vue"), "utf8");
    const pageSource = readFileSync(resolve(process.cwd(), "src/pages/CaseWorkspacePage.vue"), "utf8");

    expect(source).toContain("const visiblePanels = computed(() => props.panels.slice(0, 3));");
    expect(source).toContain('v-for="panel in visiblePanels"');
    expect(pageSource).toContain("].slice(0, 3).map((panel) => ({ ...panel, overlays }));");
    expect(pageSource).toContain('activeAnalysisVideoMode.value === "paired_videos"');
    expect(pageSource).toContain('"双通道配准融合"');
    expect(pageSource).toContain('inputMode.value === "video"');
    expect(pageSource).toContain('"MP4 视频分析"');
    expect(source).toContain("grid-template-columns: repeat(2, minmax(0, 1fr));");
    expect(source).toContain("grid-template-rows: repeat(2, minmax(280px, 1fr));");
    expect(source).toContain("min-height: clamp(620px, 70vh, 800px);");
    expect(source).toMatch(/\.analysis-quad-card\s*\{[\s\S]*?min-height:\s*0;/);
    expect(source).not.toContain("grid-row: 1 / -1;");
    expect(pageSource).not.toMatch(
      /@media \(max-width: 1180px\)\s*\{[\s\S]*?\.workspace-grid\s*\{[\s\S]*?grid-template-columns:\s*1fr;/,
    );
    expect(source).toMatch(/\.camera-live-player\s*\{[\s\S]*?object-fit: contain;/);
    expect(source).toMatch(/\.live-segmentation-overlay\s*\{[\s\S]*?object-fit: contain;/);
    expect(source).toMatch(
      /\.video-stream-player\s*\{[\s\S]*?width:\s*auto;[\s\S]*?height:\s*auto;[\s\S]*?max-width:\s*100%;[\s\S]*?max-height:\s*100%;[\s\S]*?object-fit:\s*contain;/,
    );
    expect(source).toMatch(
      /\.camera-live-player\s*\{[\s\S]*?width:\s*auto;[\s\S]*?height:\s*auto;[\s\S]*?max-width:\s*100%;[\s\S]*?max-height:\s*100%;/,
    );
  });

  it("does not render the former physician-review banner in the case workspace", () => {
    const source = readFileSync(resolve(process.cwd(), "src/pages/CaseWorkspacePage.vue"), "utf8");

    expect(source).not.toContain('class="review-notice"');
    expect(source).not.toContain("<strong>医生复核边界</strong>");
  });

  it("keeps the case workspace header focused on the operative imaging workflow", () => {
    const source = readFileSync(resolve(process.cwd(), "src/pages/CaseWorkspacePage.vue"), "utf8");

    expect(source).not.toContain("AppCaseContext");
    expect(source).not.toContain('class="workspace-header-actions"');
    expect(source).not.toContain('class="navigation-workspace-link"');
  });

  it("keeps medical image and video previews fully visible", () => {
    const mediaComponents = [
      "src/components/AnalysisFusionEvidencePanel.vue",
      "src/components/AnalysisWorkspaceCard.vue",
      "src/components/BoneGateMaskEditor.vue",
      "src/components/ManualAnnotationCanvas.vue",
      "src/components/MultichannelVideoWorkspace.vue",
      "src/components/VideoCandidateSelectorPanel.vue",
      "src/components/VideoStreamSyncPanel.vue",
      "src/pages/DataLibraryPage.vue",
    ];

    for (const file of mediaComponents) {
      const source = readFileSync(resolve(process.cwd(), file), "utf8");
      expect(source, file).not.toMatch(/object-fit:\s*(?:cover|fill)/);
    }

    const multichannelSource = readFileSync(
      resolve(process.cwd(), "src/components/MultichannelVideoWorkspace.vue"),
      "utf8",
    );
    expect(multichannelSource).toMatch(
      /\.media-viewport video,[\s\S]*?width:\s*auto;[\s\S]*?height:\s*auto;[\s\S]*?max-width:\s*100%;[\s\S]*?max-height:\s*100%;[\s\S]*?object-fit:\s*contain;/,
    );
  });
});
