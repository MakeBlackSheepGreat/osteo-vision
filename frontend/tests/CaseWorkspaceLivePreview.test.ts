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
    const fetchIndex = source.indexOf(
      "const fusionResponse = await fetch(multichannelRealtimeFusionSrc.value, { signal: requestController.signal });",
    );
    const releaseIndex = source.indexOf("multichannelRealtimeAnalysisBusy.value = false;");

    expect(fetchIndex).toBeGreaterThan(-1);
    expect(releaseIndex).toBeGreaterThan(fetchIndex);
    expect(source).toContain("queueMultichannelLiveAi(");
    expect(source).toContain('const source = activeAnalysisVideoMode.value === "browser_cameras" ? "camera" : "video";');
    expect(source).toContain("while (pendingMultichannelLiveAi)");
    expect(source).toContain("error instanceof ApiError");
    expect(source).toContain("error.status === 429");
    expect(source).toContain("isCurrentMultichannelRealtimeRequest(");
    expect(source).toContain("multichannelRealtimeRequestController?.abort()");
  });

  it("clears multichannel previews and pending AI work when the input source changes", () => {
    const source = readFileSync(resolve(process.cwd(), "src/pages/CaseWorkspacePage.vue"), "utf8");

    expect(source).toContain('resetMultichannelRealtimeState({ clearBrowserSession: source === "file" });');
    expect(source).toContain("multichannelRealtimeFrameRecord.value = null;");
    expect(source).toContain("pendingMultichannelLiveAi = null;");
    expect(source).toContain('liveFrameStaleStatus.value = "";');
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

  it("keeps exactly one multichannel playback surface active for real-time analysis", () => {
    const source = readFileSync(resolve(process.cwd(), "src/components/AnalysisWorkspaceCard.vue"), "utf8");

    expect(source).toContain(':realtime-analysis-enabled="multichannelRealtimeAnalysisEnabled && !analysisExpanded"');
    expect(source).toContain(':realtime-analysis-enabled="multichannelRealtimeAnalysisEnabled && analysisExpanded"');
    expect(source).toContain('@live-frame="emit(\'multichannelLiveFrame\', $event)"');
  });

  it("automatically imports and prepares the selected OFDVDnet composite candidate", () => {
    const source = readFileSync(resolve(process.cwd(), "src/pages/CaseWorkspacePage.vue"), "utf8");
    const controls = readFileSync(resolve(process.cwd(), "src/components/CaseWorkspaceControls.vue"), "utf8");
    const workspace = readFileSync(resolve(process.cwd(), "src/components/AnalysisWorkspaceCard.vue"), "utf8");

    expect(source).toContain("async function ensureCompositeWorkspaceReady");
    expect(source).toContain("preferredCompositeCandidate(videoCandidates.value, requestedRecordId)");
    expect(source).toContain("caseIncludesVideoCandidate(currentCase, candidate)");
    expect(source).toContain("sessionIncludesCompositeCandidate(multichannelSession.value");
    expect(source).toContain("|| !session.analysis_allowed");
    expect(source).toContain("return prepareMultichannelSession();");
    expect(source).toContain('if (mode === "composite_layout")');
    expect(source).toContain("void ensureCompositeWorkspaceReady();");
    expect(controls).toContain(':show-actions="false"');
    expect(workspace).toContain('`${expectedChannelCount} 路待接入`');
    expect(workspace).not.toContain('{ label: "已选通道", value: `${channelCount} 路`');
  });

  it("recovers a blocked composite session from the primary realtime action", () => {
    const source = readFileSync(resolve(process.cwd(), "src/pages/CaseWorkspacePage.vue"), "utf8");
    const toggleIndex = source.indexOf("async function toggleMultichannelRealtimeAnalysis");
    const compositeRecoveryIndex = source.indexOf(
      'requestedMode === "composite_layout"\n        ? await ensureCompositeWorkspaceReady(selectedVideoCandidateId.value)',
    );

    expect(toggleIndex).toBeGreaterThan(-1);
    expect(compositeRecoveryIndex).toBeGreaterThan(toggleIndex);
    expect(source).toContain("双通道同步预览正在准备，请等待当前准备完成后再点击。");
  });
});
