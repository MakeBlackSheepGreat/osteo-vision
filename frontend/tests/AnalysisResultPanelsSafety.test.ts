import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import AnalysisResultPanels from "../src/components/AnalysisResultPanels.vue";

describe("AnalysisResultPanels safety labels", () => {
  const candidate = { candidate_id: "cand_1", run_id: "run_1", risk_type: "signal", confidence: 0.8, status: "review_required" as const };

  it("does not fabricate physical area or use confidence as P95", () => {
    const wrapper = mount(AnalysisResultPanels, { props: { candidates: [candidate], metrics: {} } });
    expect(wrapper.text()).toContain("面积: 暂无");
    expect(wrapper.text()).toContain("P95 强度: 暂无");
    expect(wrapper.text()).not.toContain("cm²");
  });

  it("shows measured pixel area without uncalibrated unit conversion", () => {
    const wrapper = mount(AnalysisResultPanels, { props: { candidates: [candidate], metrics: { positive_area_px: 4200 } } });
    expect(wrapper.text()).toContain("面积: 4200 px");
  });
});
