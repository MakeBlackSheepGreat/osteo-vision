import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import AppEmptyState from "../src/components/AppEmptyState.vue";
import AppEvidenceArtifactList from "../src/components/AppEvidenceArtifactList.vue";
import AppFeedbackBanner from "../src/components/AppFeedbackBanner.vue";
import AppMetricStrip from "../src/components/AppMetricStrip.vue";
import AppPageHeader from "../src/components/AppPageHeader.vue";

const iconStub = { template: '<span class="icon-stub" />' };

describe("shared clinical workstation UI", () => {
  it.each([
    ["pending", "status", "polite"],
    ["success", "status", "polite"],
    ["warning", "status", "polite"],
    ["error", "alert", "assertive"],
  ] as const)("exposes %s feedback with the expected live semantics", (tone, role, live) => {
    const wrapper = mount(AppFeedbackBanner, {
      props: { tone, title: "处理状态", message: "长状态信息需要完整显示并允许自然换行。" },
      global: { stubs: { AppIcon: iconStub } },
    });

    expect(wrapper.attributes("role")).toBe(role);
    expect(wrapper.attributes("aria-live")).toBe(live);
    expect(wrapper.classes()).toContain(`ov-feedback-banner--${tone}`);
    expect(wrapper.text()).toContain("长状态信息需要完整显示");
  });

  it("marks long technical metrics as breakable", () => {
    const value = "CASE-20260725-VERY-LONG-TECHNICAL-IDENTIFIER-WITHOUT-SEPARATORS";
    const wrapper = mount(AppMetricStrip, {
      props: { items: [{ label: "病例编号", value, icon: "case", breakable: true }] },
      global: { stubs: { AppIcon: iconStub } },
    });

    expect(wrapper.get("dd").classes()).toContain("ov-breakable");
    expect(wrapper.find(".icon-stub").exists()).toBe(true);
    expect(wrapper.text()).toContain(value);
  });

  it("renders the page title with its semantic icon", () => {
    const wrapper = mount(AppPageHeader, {
      props: { eyebrow: "病例工作流", title: "病例档案", icon: "case", iconTone: "cyan" },
      global: { stubs: { AppIcon: iconStub } },
    });

    expect(wrapper.get("h1").text()).toBe("病例档案");
    expect(wrapper.find(".ov-title-lead .icon-stub").exists()).toBe(true);
  });

  it("keeps an empty-state action available", () => {
    const wrapper = mount(AppEmptyState, {
      props: { title: "暂无病例", description: "请先建立病例档案。" },
      slots: { actions: '<button type="button">建立病例</button>' },
      global: { stubs: { AppIcon: iconStub } },
    });

    expect(wrapper.get("h2").text()).toBe("暂无病例");
    expect(wrapper.get("button").text()).toBe("建立病例");
  });

  it("renders evidence labels, sizes, and an empty fallback", () => {
    const populated = mount(AppEvidenceArtifactList, {
      props: {
        artifacts: [
          {
            kind: "video_segmentation_manifest",
            path: "artifacts/very/long/path/video-segmentation-manifest.json",
            sizeBytes: 2048,
          },
        ],
      },
      global: { stubs: { AppIcon: iconStub } },
    });
    expect(populated.text()).toContain("MP4 分割清单");
    expect(populated.text()).toContain("2.0 KB");
    expect(populated.get(".ov-breakable").text()).toContain("video-segmentation-manifest.json");

    const empty = mount(AppEvidenceArtifactList, {
      props: { artifacts: [], emptyText: "尚未生成证据文件。" },
      global: { stubs: { AppIcon: iconStub } },
    });
    expect(empty.text()).toContain("尚未生成证据文件");
  });
});
