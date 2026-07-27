import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import InferenceViewSwitcher from "../src/components/InferenceViewSwitcher.vue";

describe("InferenceViewSwitcher", () => {
  it("switches one current-frame surface across signal, risk, and uncertainty outputs", async () => {
    const wrapper = mount(InferenceViewSwitcher, {
      props: {
        sources: {
          signal: "/signal.jpg",
          risk: "/risk.png",
          uncertainty: "/uncertainty.png",
        },
        sourceMode: "continuous",
        statusLabel: "当前时钟帧 AI · 已更新",
      },
      global: { stubs: { AppIcon: true } },
    });

    expect(wrapper.get("img").attributes("src")).toBe("/signal.jpg");
    expect(wrapper.text()).toContain("当前时钟帧 AI · 已更新");
    expect(wrapper.text()).toContain("信号候选分割");

    await wrapper.get('[role="tab"][title="边界风险"]').trigger("click");
    expect(wrapper.get("img").attributes("src")).toBe("/risk.png");

    await wrapper.get('[role="tab"][title="不确定区域"]').trigger("click");
    expect(wrapper.get("img").attributes("src")).toBe("/uncertainty.png");
    expect(wrapper.get('[role="tab"][title="不确定区域"]').attributes("aria-selected")).toBe("true");
  });

  it("keeps a readable waiting state for an unavailable selected output", async () => {
    const wrapper = mount(InferenceViewSwitcher, {
      props: { sources: { signal: "/signal.jpg" } },
      global: { stubs: { AppIcon: true } },
    });

    await wrapper.get('[role="tab"][title="边界风险"]').trigger("click");
    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.text()).toContain("等待边界风险输出");
  });
});
