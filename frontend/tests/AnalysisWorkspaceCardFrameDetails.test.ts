import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

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
    domainBoundary: "原型热点分析，需医生复核。",
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
    domainBoundary: "原型热点分析，需医生复核。",
    reviewRequired: false,
  },
];

describe("AnalysisWorkspaceCard frame details", () => {
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
});
