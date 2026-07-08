import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import AnalysisQuadGrid from "../src/components/AnalysisQuadGrid.vue";
import AnalysisWorkspaceCard from "../src/components/AnalysisWorkspaceCard.vue";
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
    expect(wrapper.find("video.camera-live-player").attributes("style")).toContain("display: none");
  });

  it("exposes camera start and stop actions in the shared video stream viewport", async () => {
    const inactive = mount(AnalysisQuadGrid, {
      props: {
        panels: [],
        cameraStream: null,
        cameraActive: false,
        cameraOpening: false,
        cameraStatusLabel: "未连接",
      },
      global: {
        stubs: {
          AppIcon: true,
        },
      },
    });

    expect(inactive.text()).toContain("开启摄像头");
    await inactive.find("button").trigger("click");
    expect(inactive.emitted("startCamera")).toHaveLength(1);

    const active = mount(AnalysisQuadGrid, {
      props: {
        panels: [],
        cameraStream: null,
        cameraActive: true,
        cameraOpening: false,
        cameraStatusLabel: "摄像头已连接",
      },
      global: {
        stubs: {
          AppIcon: true,
        },
      },
    });

    expect(active.text()).toContain("关闭摄像头");
    await active.find("button").trigger("click");
    expect(active.emitted("stopCamera")).toHaveLength(1);
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
        hotspotFrameDetails: frameDetails,
        timelineManifestSummary: null,
        fusionEvidenceSummary: null,
        videoPlayback: null,
        cameraStream: null,
        cameraActive: false,
        cameraOpening: false,
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
        cameraOpening: false,
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
  });
});
