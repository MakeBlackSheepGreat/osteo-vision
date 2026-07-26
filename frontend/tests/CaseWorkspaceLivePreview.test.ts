import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

describe("case workspace live preview retention", () => {
  it("keeps right-side live result panels bound to the last displayable frame during the next inference", () => {
    const source = readFileSync(resolve(process.cwd(), "src/pages/CaseWorkspacePage.vue"), "utf8");

    expect(source).toContain("if (!result || !liveFrameIsDisplayable.value) return [];");
  });

  it("keeps file playback and browser camera state mutually exclusive", () => {
    const source = readFileSync(resolve(process.cwd(), "src/pages/CaseWorkspacePage.vue"), "utf8");

    expect(source).toContain('const videoInputSource = ref<"file" | "camera">("file");');
    expect(source).toContain(':video-playback="videoInputSource === \'file\' ? videoPlaybackAnalysis : null"');
    expect(source).toContain(':camera-stream="videoInputSource === \'camera\' ? cameraStream : null"');
    expect(source).toContain("analysisWorkspaceCardRef.value?.pausePlayback();");
    expect(source).toContain("stopCameraInput();");
  });

  it("captures the current fusion preview before allowing the next multichannel frame", () => {
    const source = readFileSync(resolve(process.cwd(), "src/pages/CaseWorkspacePage.vue"), "utf8");
    const fetchIndex = source.indexOf("const fusionResponse = await fetch(multichannelRealtimeFusionSrc.value);");
    const releaseIndex = source.indexOf("multichannelRealtimeAnalysisBusy.value = false;");

    expect(fetchIndex).toBeGreaterThan(-1);
    expect(releaseIndex).toBeGreaterThan(fetchIndex);
    expect(source).toContain("void analyzeCameraFrame(fusionBlob, {");
  });

  it("analyzes the current single-video frame after pause or seeking", () => {
    const grid = readFileSync(resolve(process.cwd(), "src/components/AnalysisQuadGrid.vue"), "utf8");
    const workspace = readFileSync(resolve(process.cwd(), "src/pages/CaseWorkspacePage.vue"), "utf8");

    expect(grid).toContain('@seeked="handlePlaybackSeeked"');
    expect(grid).toContain('emit("playbackFrameRequested", "拖动位置")');
    expect(grid).toContain('emit("playbackFrameRequested", "暂停位置")');
    expect(workspace).toContain('@playback-frame-requested="analyzeCurrentSingleVideoFrame"');
    expect(workspace).toContain("await analyzeContinuousVideoFrame(await captureVideoPlaybackFrame(), {");
  });
});
