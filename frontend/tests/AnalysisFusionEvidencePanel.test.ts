import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import AnalysisFusionEvidencePanel from "../src/components/AnalysisFusionEvidencePanel.vue";
import type { FusionEvidenceSummary } from "../src/components/analysisPreview";

const summary: FusionEvidenceSummary = {
  algorithmVersionLabel: "fusion-v2",
  methodLabel: "白光/ICG 伪彩融合",
  thresholdLabel: "0.37",
  alphaLabel: "0.65",
  backgroundLabel: "已扣除 · P5 · baseline 12",
  registrationLabel: "已应用 · 相位相关",
  translationLabel: "2.50, -1.00 px",
  responseLabel: "0.812",
  resizeLabel: "3840x2160 -> 960x540",
  colorbarPath: "artifacts/platform/cases/case-001/colorbar.png",
  colorbarPreviewSrc: "/files/preview?path=colorbar.png",
};

describe("AnalysisFusionEvidencePanel", () => {
  it("renders fusion evidence metadata and colorbar preview", () => {
    const wrapper = mount(AnalysisFusionEvidencePanel, {
      props: { summary },
      global: {
        stubs: {
          AppIcon: true,
        },
      },
    });

    expect(wrapper.text()).toContain("荧光融合证据");
    expect(wrapper.text()).toContain("fusion-v2");
    expect(wrapper.text()).toContain("阈值 0.37");
    expect(wrapper.text()).toContain("透明度 0.65");
    expect(wrapper.text()).toContain("白光/ICG 伪彩融合");
    expect(wrapper.text()).toContain("已扣除 · P5 · baseline 12");
    expect(wrapper.text()).toContain("已应用 · 相位相关");
    expect(wrapper.text()).toContain("2.50, -1.00 px");
    expect(wrapper.text()).toContain("0.812");
    expect(wrapper.text()).toContain("3840x2160 -> 960x540");

    expect(wrapper.find("img").attributes("src")).toBe("/files/preview?path=colorbar.png");
    expect(wrapper.find("a.fusion-colorbar-link").attributes("href")).toBe("/files/preview?path=colorbar.png");
  });
});
