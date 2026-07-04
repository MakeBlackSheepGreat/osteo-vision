import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import RoiCanvas from "../src/components/RoiCanvas.vue";

describe("RoiCanvas editing", () => {
  it("nudges, undoes, redoes, and saves a loaded candidate ROI", async () => {
    const wrapper = mount(RoiCanvas, {
      props: {
        hasOutput: true,
        draftId: "candidate_1",
        draftLabel: "AI 候选区",
        draftReviewState: "modified",
        draftGeometry: {
          type: "rect",
          coordinate_space: "normalized",
          x: 0.2,
          y: 0.25,
          width: 0.3,
          height: 0.35,
        },
      },
      global: {
        stubs: {
          SectionHeading: true,
        },
      },
    });

    await wrapper.find(".canvas-frame").trigger("keydown", { key: "ArrowRight" });
    await wrapper.find(".canvas-frame").trigger("keydown", { key: "ArrowDown", shiftKey: true });
    expect(wrapper.text()).toContain("原始");
    expect(wrapper.text()).toContain("当前");

    const undoButton = wrapper.findAll("button").find((button) => button.text().includes("撤销"));
    const redoButton = wrapper.findAll("button").find((button) => button.text().includes("重做"));
    expect(undoButton).toBeTruthy();
    expect(redoButton).toBeTruthy();
    await undoButton!.trigger("click");
    await redoButton!.trigger("click");

    const saveButton = wrapper.findAll("button").find((button) => button.text().includes("保存 ROI"));
    expect(saveButton).toBeTruthy();
    await saveButton!.trigger("click");

    const saved = wrapper.emitted("save")?.[0]?.[0];
    expect(saved).toMatchObject({
      roiId: "candidate_1",
      label: "AI 候选区",
      reviewState: "modified",
      geometry: {
        type: "rect",
        coordinate_space: "normalized",
        x: 0.205,
        y: 0.27,
        width: 0.3,
        height: 0.35,
      },
    });
  });
});
