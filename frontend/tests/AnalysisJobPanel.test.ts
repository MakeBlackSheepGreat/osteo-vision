import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import AnalysisJobPanel from "../src/components/AnalysisJobPanel.vue";

describe("AnalysisJobPanel", () => {
  it("renders backend job progress and emits control actions", async () => {
    const wrapper = mount(AnalysisJobPanel, {
      props: {
        jobId: "job-001",
        status: "running",
        error: "",
        progress: { percent: 42.4, message: "正在抽取关键帧" },
        timedOut: false,
        loading: false,
      },
      global: {
        stubs: {
          AppButton: true,
        },
      },
    });

    expect(wrapper.text()).toContain("job-001 · 运行中");
    expect(wrapper.text()).toContain("正在抽取关键帧 · 42%");
    expect(wrapper.find(".job-progress span").attributes("style")).toContain("width: 42%");

    const buttons = wrapper.findAllComponents({ name: "AppButton" });
    await buttons[0].trigger("click");
    await buttons[1].trigger("click");

    expect(wrapper.emitted("refresh")).toHaveLength(1);
    expect(wrapper.emitted("cancel")).toHaveLength(1);
  });

  it("allows retry for failed or timed out jobs", () => {
    const wrapper = mount(AnalysisJobPanel, {
      props: {
        jobId: "job-002",
        status: "failed",
        error: "decode failed",
        progress: {},
        timedOut: false,
        loading: false,
      },
      global: {
        stubs: {
          AppButton: true,
        },
      },
    });

    expect(wrapper.text()).toContain("job-002 · 失败");
    expect(wrapper.text()).toContain("decode failed");
    expect(wrapper.findAllComponents({ name: "AppButton" })[2].attributes("disabled")).toBe("false");
  });
});
