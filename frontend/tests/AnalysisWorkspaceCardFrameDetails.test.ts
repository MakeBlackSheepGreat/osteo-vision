import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import AnalysisQuadGrid from "../src/components/AnalysisQuadGrid.vue";
import AnalysisWorkspaceCard from "../src/components/AnalysisWorkspaceCard.vue";
import VideoStreamSyncPanel from "../src/components/VideoStreamSyncPanel.vue";
import type { HotspotFrameDetail } from "../src/components/analysisPreview";

const frameDetails: HotspotFrameDetail[] = [
  {
    key: "8-0",
    frameIndex: 8,
    timestampSec: 0.8,
    frameLabel: "帧 8",
    timestampLabel: "0.80s",
    candidateCountLabel: "2 个候选",
    positiveAreaLabel: "12.34%",
    roiAreaLabel: "4.56%",
    topBBoxLabel: "10, 20, 31, 44",
    evidenceLabel: "evidence_frame.jpg",
    domainBoundary: "平台热点分析，需医生复核。",
    reviewRequired: true,
    evidenceHref: "/preview?path=evidence_frame.jpg",
    overlayHref: "/preview?path=hotspot_overlay.png",
    maskHref: "/preview?path=hotspot_mask.png",
  },
  {
    key: "12-1",
    frameIndex: 12,
    timestampSec: 1.2,
    frameLabel: "帧 12",
    timestampLabel: "1.20s",
    candidateCountLabel: "0 个候选",
    positiveAreaLabel: "0.00%",
    roiAreaLabel: "未命中 ROI",
    topBBoxLabel: "暂无",
    evidenceLabel: "frame_12.jpg",
    domainBoundary: "平台热点分析，需医生复核。",
    reviewRequired: false,
  },
];

describe("AnalysisWorkspaceCard frame details", () => {
  it("marks and compacts an entirely empty viewport group until analysis imagery arrives", async () => {
    const wrapper = mount(AnalysisQuadGrid, {
      props: {
        panels: [
          {
            title: "融合图",
            tag: "待分析",
            label: "白光 + ICG",
            scale: "0 - 1",
          },
        ],
        cameraStream: null,
        cameraActive: false,
        cameraStatusLabel: "摄像头未连接",
      },
      global: {
        stubs: {
          AppIcon: true,
        },
      },
    });

    const cameraViewport = wrapper.find(".camera-viewport");
    const outputViewport = wrapper.find(".output-viewport");
    expect(wrapper.find('[aria-label="术中影像与分析结果"]').classes()).toContain("analysis-quad-grid--empty");
    expect(cameraViewport.classes()).toContain("is-empty");
    expect(cameraViewport.classes()).not.toContain("active");
    expect(cameraViewport.classes()).not.toContain("has-file-video");
    expect(outputViewport.classes()).toContain("is-empty");
    expect(outputViewport.classes()).not.toContain("has-image");
    expect(wrapper.text()).toContain("等待视频流");
    expect(wrapper.text()).toContain("等待融合图输出");

    await wrapper.setProps({
      panels: [
        {
          title: "融合图",
          tag: "已分析",
          label: "白光 + ICG",
          scale: "0 - 1",
          previewSrc: "/files/preview?path=fusion.png",
          path: "C:\\evidence\\fusion.png",
        },
      ],
    });

    expect(wrapper.find('[aria-label="术中影像与分析结果"]').classes()).not.toContain(
      "analysis-quad-grid--empty",
    );
    expect(wrapper.find('[aria-label="术中影像与分析结果"]').classes()).toContain(
      "analysis-quad-grid--stream-empty-with-outputs",
    );
    expect(wrapper.find(".output-viewport").classes()).toContain("has-image");
    expect(wrapper.find(".preview-path-details summary").text()).toContain("fusion.png");
    expect(wrapper.find(".preview-path-details code").text()).toContain("C:\\evidence\\fusion.png");
  });

  it("shows imported MP4 in the shared video stream viewport even when camera is active", () => {
    const wrapper = mount(AnalysisQuadGrid, {
      props: {
        panels: [],
        cameraStream: null,
        cameraActive: true,
        cameraStatusLabel: "摄像头已连接",
        videoPlayback: {
          sourcePath: "artifacts/platform/uploads/demo.mp4",
          sourceLabel: "demo.mp4",
          videoSrc: "/files/video?path=demo.mp4",
          modeLabel: "MP4 keyframe analysis",
          analysisScopeLabel: "selected MP4 keyframes",
          frameDetails,
          boundaryLabel: "Keyframe-based playback analysis; physician review required.",
        },
        liveOverlaySrc: "/files/preview?path=live_overlay.png",
        liveFrameStatus: "MP4 实时分割已更新",
        liveModelLatencyMs: 62,
        liveEndToEndLatencyMs: 94,
        cameraOpening: false,
      },
      global: {
        stubs: {
          AppIcon: true,
        },
      },
    });

    expect(wrapper.text()).toContain("视频流输入");
    expect(wrapper.text()).toContain("MP4");
    expect(wrapper.find("video.video-stream-player").exists()).toBe(true);
    expect(wrapper.find("video.video-stream-player").attributes("crossorigin")).toBe("anonymous");
    expect(wrapper.find("video.camera-live-player").attributes("style")).toContain("display: none");
    expect(wrapper.find("img.live-segmentation-overlay").exists()).toBe(true);
    expect(wrapper.find(".camera-viewport").classes()).toContain("has-live-overlay");
    expect(wrapper.text()).toContain("模型 62 ms");
    expect(wrapper.text()).toContain("端到端 94 ms");
    expect(wrapper.find('[aria-label="术中影像与分析结果"]').classes()).not.toContain(
      "analysis-quad-grid--empty",
    );
    expect(wrapper.find('[aria-label="术中影像与分析结果"]').exists()).toBe(true);
    expect(wrapper.find(".analysis-quad-card--camera").exists()).toBe(true);
  });

  it("keeps the shared video stream viewport free of camera operation controls", () => {
    const wrapper = mount(AnalysisQuadGrid, {
      props: {
        panels: [],
        cameraStream: null,
        cameraActive: true,
        cameraStatusLabel: "摄像头已连接",
      },
      global: {
        stubs: {
          AppIcon: true,
        },
      },
    });

    expect(wrapper.text()).toContain("视频流输入");
    expect(wrapper.text()).not.toContain("开启摄像头");
    expect(wrapper.text()).not.toContain("关闭摄像头");
    expect(wrapper.text()).not.toContain("抓取关键帧分析");
    expect(wrapper.text()).not.toContain("开始实时分割");
    expect(wrapper.find('[aria-label="连续关键帧采样间隔"]').exists()).toBe(false);
  });

  it("shows all frame details and emits selected frame keys", async () => {
    const wrapper = mount(AnalysisWorkspaceCard, {
      props: {
        loading: false,
        error: "",
        hasCase: true,
        exportPath: "",
        exportLinks: [],
        exportSummary: {},
        exportArtifactEntries: [],
        activeAnalysisJobId: "",
        activeAnalysisJobStatus: "",
        activeAnalysisJobError: "",
        activeAnalysisJobProgress: {},
        lastAnalysisJobTimedOut: false,
        latestRunStatusLabel: "已完成",
        analysisStatusClass: "completed",
        kpiItems: [],
        previewPanels: [],
        hotspotTimelineItems: [],
        hotspotTimelineTotalCount: 2,
        hotspotTimelineFilter: "all",
        selectedHotspotTimelineKey: "8-0",
        selectedHotspotFrameDetail: frameDetails[0],
        boneGateCandidateFrameIndexes: [8, 12],
        hotspotFrameDetails: frameDetails,
        timelineManifestSummary: null,
        fusionEvidenceSummary: null,
        videoPlayback: null,
        cameraStream: null,
        cameraActive: false,
        cameraStatusLabel: "未连接",
        analysisExpanded: false,
      },
      global: {
        stubs: {
          AnalysisQuadGrid: true,
          AppButton: true,
          AppIcon: true,
        },
      },
    });

    expect(wrapper.text()).toContain("逐帧详情");
    expect(wrapper.text()).toContain("2 帧");
    expect(wrapper.text()).toContain("帧 8");
    expect(wrapper.text()).toContain("12.34%");
    expect(wrapper.text()).toContain("需复核");
    expect(wrapper.text()).toContain("帧 12");
    expect(wrapper.text()).toContain("低风险");

    const rows = wrapper.findAll(".hotspot-frame-row");
    expect(rows).toHaveLength(2);
    await rows[1].trigger("click");

    expect(wrapper.emitted("selectHotspotFrame")?.[0]).toEqual(["12-1"]);
  });

  it("syncs MP4 playback time to the nearest keyframe detail", async () => {
    const wrapper = mount(AnalysisWorkspaceCard, {
      props: {
        loading: false,
        error: "",
        hasCase: true,
        exportPath: "",
        exportLinks: [],
        exportSummary: {},
        exportArtifactEntries: [],
        activeAnalysisJobId: "",
        activeAnalysisJobStatus: "",
        activeAnalysisJobError: "",
        activeAnalysisJobProgress: {},
        lastAnalysisJobTimedOut: false,
        latestRunStatusLabel: "已完成",
        analysisStatusClass: "completed",
        kpiItems: [],
        previewPanels: [],
        hotspotTimelineItems: [],
        hotspotTimelineTotalCount: 2,
        hotspotTimelineFilter: "all",
        selectedHotspotTimelineKey: "8-0",
        selectedHotspotFrameDetail: frameDetails[0],
        hotspotFrameDetails: frameDetails,
        timelineManifestSummary: null,
        fusionEvidenceSummary: null,
        videoPlayback: {
          sourcePath: "artifacts/platform/uploads/demo.mp4",
          sourceLabel: "demo.mp4",
          videoSrc: "/files/video?path=demo.mp4",
          modeLabel: "MP4 keyframe analysis",
          analysisScopeLabel: "selected MP4 keyframes",
          frameDetails,
          boundaryLabel: "Keyframe-based playback analysis; physician review required.",
        },
        cameraStream: null,
        cameraActive: false,
        cameraStatusLabel: "未连接",
        analysisExpanded: false,
      },
      global: {
        stubs: {
          AppButton: true,
          AppIcon: true,
        },
      },
    });

    expect(wrapper.text()).toContain("视频流同步分析");
    expect(wrapper.text()).toContain("视频流输入");
    expect(wrapper.find('[aria-label="视频流同步分析"]').exists()).toBe(true);
    expect(wrapper.find(".video-playback-panel video").exists()).toBe(false);
    const video = wrapper.find("video.video-stream-player");
    expect(video.exists()).toBe(true);
    Object.defineProperty(video.element, "duration", { configurable: true, value: 3 });
    (video.element as HTMLVideoElement).currentTime = 1.18;
    await video.trigger("timeupdate");

    const emitted = wrapper.emitted("selectHotspotFrame") ?? [];
    expect(emitted.at(-1)).toEqual(["12-1"]);
    expect(wrapper.text()).toContain("帧 12");

    await video.trigger("play");
    await video.trigger("pause");
    await video.trigger("ended");
    expect(wrapper.emitted("playbackStarted")).toHaveLength(1);
    expect(wrapper.emitted("playbackPaused")).toHaveLength(1);
    expect(wrapper.emitted("playbackEnded")).toHaveLength(1);
  });

  it("selects the nearest playback keyframe before bone gate actions", async () => {
    const actionOrder: string[] = [];
    const wrapper = mount(AnalysisWorkspaceCard, {
      props: {
        loading: false,
        error: "",
        hasCase: true,
        exportPath: "",
        exportLinks: [],
        exportSummary: {},
        exportArtifactEntries: [],
        activeAnalysisJobId: "",
        activeAnalysisJobStatus: "",
        activeAnalysisJobError: "",
        activeAnalysisJobProgress: {},
        lastAnalysisJobTimedOut: false,
        latestRunStatusLabel: "已完成",
        analysisStatusClass: "completed",
        kpiItems: [],
        previewPanels: [],
        hotspotTimelineItems: [],
        hotspotTimelineTotalCount: 2,
        hotspotTimelineFilter: "all",
        selectedHotspotTimelineKey: "8-0",
        selectedHotspotFrameDetail: frameDetails[0],
        hotspotFrameDetails: frameDetails,
        timelineManifestSummary: null,
        fusionEvidenceSummary: null,
        videoPlayback: {
          sourcePath: "artifacts/platform/uploads/demo.mp4",
          sourceLabel: "demo.mp4",
          videoSrc: "/files/video?path=demo.mp4",
          modeLabel: "MP4 keyframe analysis",
          analysisScopeLabel: "selected MP4 keyframes",
          frameDetails,
          boundaryLabel: "Keyframe-based playback analysis; physician review required.",
        },
        cameraStream: null,
        cameraActive: false,
        cameraStatusLabel: "未连接",
        analysisExpanded: false,
        boneGateCandidateFrameIndexes: [8, 12],
        onSelectHotspotFrame: (key: string) => actionOrder.push(`select:${key}`),
        onGenerateBoneGateForFrame: () => actionOrder.push("generate"),
      },
      global: {
        stubs: {
          AppButton: true,
          AppIcon: true,
          BoneGateMaskEditor: true,
        },
      },
    });

    const video = wrapper.find("video.video-stream-player");
    Object.defineProperty(video.element, "duration", { configurable: true, value: 3 });
    (video.element as HTMLVideoElement).currentTime = 1.18;
    await video.trigger("timeupdate");
    actionOrder.length = 0;

    const syncPanel = wrapper.findComponent(VideoStreamSyncPanel);
    await syncPanel.get("button.bone-gate-generate-button").trigger("click");

    expect(actionOrder).toEqual(["select:12-1", "generate"]);
    expect(syncPanel.get("button.bone-gate-edit-button").attributes("disabled")).toBeDefined();
    expect(syncPanel.text()).toContain("请先生成当前帧的骨面门控");

    const frameWithMask = { ...frameDetails[1], boneGateMaskHref: "/preview?path=bone_gate.png" };
    await wrapper.setProps({
      selectedHotspotFrameDetail: frameWithMask,
      videoPlayback: {
        sourcePath: "artifacts/platform/uploads/demo.mp4",
        sourceLabel: "demo.mp4",
        videoSrc: "/files/video?path=demo.mp4",
        modeLabel: "MP4 keyframe analysis",
        analysisScopeLabel: "selected MP4 keyframes",
        frameDetails: [frameDetails[0], frameWithMask],
        boundaryLabel: "Keyframe-based playback analysis; physician review required.",
      },
    });

    actionOrder.length = 0;
    await syncPanel.get("button.bone-gate-edit-button").trigger("click");
    expect(actionOrder).toEqual(["select:12-1"]);
    expect(wrapper.find("bone-gate-mask-editor-stub").exists()).toBe(true);
    expect(syncPanel.get("button.bone-gate-generate-button").attributes("disabled")).toBeDefined();
  });

  it("disables unmatched and busy bone gate actions with a visible reason", async () => {
    const videoPlayback = {
      sourcePath: "artifacts/platform/uploads/demo.mp4",
      sourceLabel: "demo.mp4",
      videoSrc: "/files/video?path=demo.mp4",
      modeLabel: "MP4 keyframe analysis",
      analysisScopeLabel: "selected MP4 keyframes",
      frameDetails,
      boundaryLabel: "Keyframe-based playback analysis; physician review required.",
    };
    const wrapper = mount(VideoStreamSyncPanel, {
      props: {
        videoPlayback,
        nearestFrameDetail: frameDetails[1],
        loading: false,
        generateAvailable: false,
        editAvailable: false,
        generateUnavailableReason: "帧 12 没有匹配的候选区，骨面门控操作已停用。",
        editUnavailableReason: "帧 12 没有匹配的候选区，骨面门控操作已停用。",
      },
      global: { stubs: { AppIcon: true } },
    });

    expect(wrapper.get("button.bone-gate-generate-button").attributes("disabled")).toBeDefined();
    expect(wrapper.get("button.bone-gate-edit-button").attributes("disabled")).toBeDefined();
    expect(wrapper.text()).toContain("帧 12 没有匹配的候选区");
    expect(wrapper.emitted("generateBoneGate")).toBeUndefined();

    await wrapper.setProps({ loading: true, generateAvailable: true, editAvailable: true });
    expect(wrapper.get("button.bone-gate-generate-button").attributes("disabled")).toBeDefined();
    expect(wrapper.get("button.bone-gate-edit-button").attributes("disabled")).toBeDefined();
    expect(wrapper.text()).toContain("骨面门控任务处理中");
  });

  it("keeps fullscreen MP4 playback linked to the same analysis lifecycle", async () => {
    const wrapper = mount(AnalysisWorkspaceCard, {
      props: {
        loading: false,
        error: "",
        hasCase: true,
        exportPath: "",
        exportLinks: [],
        exportSummary: {},
        exportArtifactEntries: [],
        activeAnalysisJobId: "",
        activeAnalysisJobStatus: "",
        activeAnalysisJobError: "",
        activeAnalysisJobProgress: {},
        lastAnalysisJobTimedOut: false,
        latestRunStatusLabel: "已完成",
        analysisStatusClass: "completed",
        kpiItems: [],
        previewPanels: [],
        hotspotTimelineItems: [],
        hotspotTimelineTotalCount: 2,
        hotspotTimelineFilter: "all",
        selectedHotspotTimelineKey: "8-0",
        selectedHotspotFrameDetail: frameDetails[0],
        hotspotFrameDetails: frameDetails,
        timelineManifestSummary: null,
        fusionEvidenceSummary: null,
        videoPlayback: {
          sourcePath: "artifacts/platform/uploads/demo.mp4",
          sourceLabel: "demo.mp4",
          videoSrc: "/files/video?path=demo.mp4",
          modeLabel: "MP4 keyframe analysis",
          analysisScopeLabel: "selected MP4 keyframes",
          frameDetails,
          boundaryLabel: "Keyframe-based playback analysis; physician review required.",
        },
        cameraStream: null,
        cameraActive: false,
        cameraStatusLabel: "未连接",
        analysisExpanded: true,
      },
      global: {
        stubs: {
          AppButton: true,
          AppIcon: true,
        },
      },
    });

    const videos = wrapper.findAll("video.video-stream-player");
    expect(videos).toHaveLength(2);
    const fullscreenVideo = videos[1];
    Object.defineProperty(fullscreenVideo.element, "duration", { configurable: true, value: 3 });
    (fullscreenVideo.element as HTMLVideoElement).currentTime = 1.18;
    await fullscreenVideo.trigger("timeupdate");
    await fullscreenVideo.trigger("play");
    await fullscreenVideo.trigger("pause");
    await fullscreenVideo.trigger("ended");

    expect(wrapper.emitted("selectHotspotFrame")?.at(-1)).toEqual(["12-1"]);
    expect(wrapper.emitted("playbackStateChange")?.at(-1)).toEqual([1.18, 3]);
    expect(wrapper.emitted("playbackStarted")).toHaveLength(1);
    expect(wrapper.emitted("playbackPaused")).toHaveLength(1);
    expect(wrapper.emitted("playbackEnded")).toHaveLength(1);
  });

  it("returns the playback analysis to the inline player when fullscreen closes", async () => {
    const wrapper = mount(AnalysisWorkspaceCard, {
      props: {
        loading: false,
        error: "",
        hasCase: true,
        exportPath: "",
        exportLinks: [],
        exportSummary: {},
        exportArtifactEntries: [],
        activeAnalysisJobId: "",
        activeAnalysisJobStatus: "",
        activeAnalysisJobError: "",
        activeAnalysisJobProgress: {},
        lastAnalysisJobTimedOut: false,
        latestRunStatusLabel: "已完成",
        analysisStatusClass: "completed",
        kpiItems: [],
        previewPanels: [],
        hotspotTimelineItems: [],
        hotspotTimelineTotalCount: 2,
        hotspotTimelineFilter: "all",
        selectedHotspotTimelineKey: "8-0",
        selectedHotspotFrameDetail: frameDetails[0],
        hotspotFrameDetails: frameDetails,
        timelineManifestSummary: null,
        fusionEvidenceSummary: null,
        videoPlayback: {
          sourcePath: "artifacts/platform/uploads/demo.mp4",
          sourceLabel: "demo.mp4",
          videoSrc: "/files/video?path=demo.mp4",
          modeLabel: "MP4 keyframe analysis",
          analysisScopeLabel: "selected MP4 keyframes",
          frameDetails,
          boundaryLabel: "Keyframe-based playback analysis; physician review required.",
        },
        cameraStream: null,
        cameraActive: false,
        cameraStatusLabel: "未连接",
        analysisExpanded: true,
      },
      global: {
        stubs: {
          AppButton: false,
          AppIcon: true,
        },
      },
    });

    const fullscreenVideo = wrapper.findAll("video.video-stream-player")[1];
    await fullscreenVideo.trigger("play");
    await wrapper.get('[title="关闭全屏分析视图"]').trigger("click");

    expect(wrapper.emitted("closeFullscreen")).toHaveLength(1);
    expect(wrapper.emitted("playbackPaused")).toHaveLength(1);
  });
});
