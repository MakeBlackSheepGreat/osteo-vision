import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import ViabilitySpectrumPanel from "../src/components/ViabilitySpectrumPanel.vue";

const previewUrl = (path: string) => `/preview?path=${encodeURIComponent(path)}`;
const downloadUrl = (path: string) => `/download?path=${encodeURIComponent(path)}`;

describe("ViabilitySpectrumPanel", () => {
  it("degrades safely without a reviewed bone gate", () => {
    const wrapper = mount(ViabilitySpectrumPanel, { props: { spectrum: {
      available: false,
      status: "pending_reviewed_bone_gate",
      spatial_effect_applied: false,
      calibration_status: "pending_target_domain_validation",
      activity_score: { available: true, path: "artifacts/activity.png", scale: [0, 1] },
      activity_class_map_path: "artifacts/class-map.png",
      low_activity_candidate: { available: true, positive_area_px: 12, bone_gate_fraction: 0.2 },
      confidence_statement: "0.80 仅表示信号候选置信度。",
    }, previewUrl, downloadUrl } });

    expect(wrapper.text()).toContain("安全降级");
    expect(wrapper.text()).toContain("规则派生骨活性连续谱");
    expect(wrapper.text()).toContain("等待可信医生骨面门控");
    expect(wrapper.text()).toContain("三类空间候选、无法判断区、面积比例和分类图层保持不可用");
    expect(wrapper.text()).toContain("不得解释为可切除比例或切除成功率");
    expect(wrapper.find('img[alt="连续骨活性评分图"]').attributes("src")).toContain("activity.png");
    expect(wrapper.find('img[alt="骨活性三分类与无法判断区图"]').exists()).toBe(false);
    expect(wrapper.text()).not.toContain("20.0%");
  });

  it("shows reviewed spatial candidates, ratios and evidence layers", () => {
    const wrapper = mount(ViabilitySpectrumPanel, { props: { spectrum: {
      available: true,
      status: "available_for_physician_review",
      spatial_effect_applied: true,
      calibration_status: "pending_target_domain_validation",
      activity_score: { available: true, path: "artifacts/activity.png", scale: [0, 1] },
      activity_class_map_path: "artifacts/class-map.png",
      thresholds: { low_max: 0.3, high_min: 0.6 },
      low_activity_candidate: { available: true, label: "低活性候选", positive_area_px: 100, bone_gate_fraction: 0.25, path: "artifacts/low.png" },
      transition_candidate: { available: true, label: "过渡复核区", positive_area_px: 60, bone_gate_fraction: 0.15 },
      high_activity_candidate: { available: true, label: "高活性参考", positive_area_px: 200, bone_gate_fraction: 0.5 },
      ignore_region: {
        available: true,
        label: "无法判断区",
        positive_area_px: 40,
        bone_gate_fraction: 0.1,
        path: "artifacts/ignore.png",
        sources: [
          { source_type: "uncertain_mask", path: "artifacts/uncertain.png", sha256: "a".repeat(64) },
          { source_type: "physician_ignore_mask", path: "artifacts/review-ignore.png", sha256: "b".repeat(64) },
        ],
      },
    }, previewUrl, downloadUrl } });

    expect(wrapper.text()).toContain("医生复核可用");
    expect(wrapper.text()).toContain("25.0%");
    expect(wrapper.text()).toContain("100 px");
    expect(wrapper.text()).toContain("低 ≤ 0.30；高 ≥ 0.60");
    expect(wrapper.find('img[alt="骨活性三分类与无法判断区图"]').attributes("src")).toContain("class-map.png");
    expect(wrapper.find('a[href*="low.png"]').text()).toBe("查看候选掩膜");
    expect(wrapper.find('a[href*="ignore.png"]').text()).toBe("查看候选掩膜");
    expect(wrapper.text()).toContain("来源 模型不确定性、医生标注");
  });
});
