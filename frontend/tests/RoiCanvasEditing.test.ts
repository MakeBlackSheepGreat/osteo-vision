import { mount } from "@vue/test-utils";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import RoiCanvas from "../src/components/RoiCanvas.vue";

describe("RoiCanvas editing", () => {
  it("keeps empty and active canvases on the same stable review height", () => {
    const source = readFileSync(join(process.cwd(), "src", "components", "RoiCanvas.vue"), "utf8");

    expect(source).toMatch(/--roi-canvas-height:\s*clamp\(440px,\s*54vh,\s*620px\);/);
    expect(source).toMatch(
      /\.roi-svg\s*\{[^}]*height:\s*var\(--roi-canvas-height\);[^}]*min-height:\s*var\(--roi-canvas-height\);/s,
    );
    expect(source).toMatch(
      /\.canvas-frame\.empty \.roi-svg\s*\{[^}]*height:\s*var\(--roi-canvas-height\);[^}]*min-height:\s*var\(--roi-canvas-height\);[^}]*max-height:\s*var\(--roi-canvas-height\);/s,
    );
  });

  it("uses a neutral state until manual annotation starts", async () => {
    const wrapper = mount(RoiCanvas, {
      global: {
        stubs: {
          SectionHeading: true,
        },
      },
    });

    expect(wrapper.get(".canvas-frame").classes()).toContain("empty");
    expect(wrapper.find(".roi-media-scene").exists()).toBe(false);
    expect(wrapper.text()).toContain("尚无可复核候选区或 ROI");

    await wrapper.get(".empty-canvas-copy button").trigger("click");

    expect(wrapper.get(".canvas-frame").classes()).toContain("active");
    expect(wrapper.get(".canvas-frame").classes()).not.toContain("empty");
    expect(wrapper.find(".roi-media-scene").exists()).toBe(true);
  });

  it("keeps the review canvas active when analysis output exists", () => {
    const wrapper = mount(RoiCanvas, {
      props: { hasOutput: true },
      global: {
        stubs: {
          SectionHeading: true,
        },
      },
    });

    expect(wrapper.get(".canvas-frame").classes()).toContain("active");
    expect(wrapper.find(".empty-canvas-copy").exists()).toBe(false);
    expect(wrapper.find(".roi-media-scene").exists()).toBe(true);
  });

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

  it("locks candidate controls and geometry while saving", async () => {
    const wrapper = mount(RoiCanvas, {
      props: {
        hasOutput: true,
        loading: true,
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

    expect(wrapper.find(".roi-label-field input").attributes("disabled")).toBeDefined();
    expect(wrapper.find(".roi-label-field select").attributes("disabled")).toBeDefined();
    expect(wrapper.findAll(".roi-toolbar button").every((button) => button.attributes("disabled") !== undefined)).toBe(true);
    expect(wrapper.get(".canvas-frame").classes()).toContain("locked");
    expect(wrapper.get(".canvas-frame").attributes("aria-disabled")).toBe("true");

    await wrapper.get(".canvas-frame").trigger("keydown", { key: "ArrowRight" });
    const saveButton = wrapper.findAll("button").find((button) => button.text().includes("保存 ROI"));
    await saveButton?.trigger("click");
    expect(wrapper.emitted("save")).toBeUndefined();

    await wrapper.setProps({ loading: false });
    await saveButton?.trigger("click");

    expect(wrapper.emitted("save")?.[0]?.[0]).toMatchObject({
      roiId: "candidate_1",
      geometry: {
        type: "rect",
        coordinate_space: "normalized",
        x: 0.2,
        y: 0.25,
        width: 0.3,
        height: 0.35,
      },
    });
  });
});
