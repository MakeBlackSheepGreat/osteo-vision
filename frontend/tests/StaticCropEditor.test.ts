import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import StaticCropEditor from "../src/components/StaticCropEditor.vue";
import type { DatasetReviewRecord } from "../src/types/datasetReview";

const record: DatasetReviewRecord = {
  record_id: "review_panel_a",
  image_path: "C:\\data\\figure.jpg",
  review_state: "review_required",
  crop_required: true,
  suggestion_id: "suggestion_a",
  suggested_crop_bbox: { x: 20, y: 30, width: 200, height: 120 },
  suggested_panel_role: "paired_fluorescence",
  suggested_pair_id: "pair_a",
  suggestion_method: "curated_visual_panel_audit_v1",
  suggestion_score: 0.99,
  suggestion_quality_status: "warning",
  suggestion_quality_warnings: ["crop_dimension_below_96px"],
};

let imageInstances: Array<{ naturalWidth: number; naturalHeight: number; onload: null | (() => void); onerror: null | (() => void) }> = [];

describe("StaticCropEditor", () => {
  beforeEach(() => {
    imageInstances = [];
    HTMLCanvasElement.prototype.getContext = vi.fn(function (this: HTMLCanvasElement) {
      return {
        canvas: this,
        drawImage: vi.fn(),
        fillRect: vi.fn(),
        strokeRect: vi.fn(),
        save: vi.fn(),
        restore: vi.fn(),
        setLineDash: vi.fn(),
        fillStyle: "",
        strokeStyle: "",
        lineWidth: 1,
      } as unknown as CanvasRenderingContext2D;
    }) as unknown as HTMLCanvasElement["getContext"];
    vi.stubGlobal("Image", class {
      naturalWidth = 640;
      naturalHeight = 360;
      decoding = "async";
      onload: null | (() => void) = null;
      onerror: null | (() => void) = null;

      constructor() {
        imageInstances.push(this);
      }
      set src(_value: string) {
        queueMicrotask(() => this.onload?.());
      }
    });
  });

  it("ignores a late image load from a previous source URL", async () => {
    const wrapper = mount(StaticCropEditor, {
      props: { record, sourceUrl: "/image/old", loading: false },
      global: { stubs: { AppIcon: true } },
    });
    await wrapper.setProps({ sourceUrl: "/image/new" });
    expect(imageInstances).toHaveLength(2);
    imageInstances[0].naturalWidth = 111;
    imageInstances[0].naturalHeight = 77;
    imageInstances[0].onload?.();
    expect(wrapper.text()).not.toContain("111 × 77 px");
    imageInstances[1].naturalWidth = 640;
    imageInstances[1].naturalHeight = 360;
    imageInstances[1].onload?.();
    await flushPromises();
    expect(wrapper.text()).toContain("200 × 120 px");
  });

  afterEach(() => vi.unstubAllGlobals());

  it("preselects the suggestion and emits an accepted traced crop", async () => {
    const wrapper = mount(StaticCropEditor, {
      props: { record, sourceUrl: "/dataset-review/review_panel_a/image", loading: false },
      global: { stubs: { AppIcon: true } },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("自动面板建议 99%");
    expect(wrapper.text()).toContain("面板短边小于 96 px");
    const acceptButton = wrapper.findAll("button").find((button) => button.text().includes("接受建议"));
    await acceptButton?.trigger("click");

    expect(wrapper.emitted("save")?.[0]?.[0]).toEqual({
      x: 20,
      y: 30,
      width: 200,
      height: 120,
      panel_role: "paired_fluorescence",
      pair_id: "pair_a",
      crop_notes: null,
      suggestion_id: "suggestion_a",
      crop_review_action: "accepted",
    });
  });

  it("keeps blocked suggestions editable while disabling direct acceptance", async () => {
    const wrapper = mount(StaticCropEditor, {
      props: {
        record: { ...record, suggestion_quality_status: "blocked" },
        sourceUrl: "/dataset-review/review_panel_a/image",
        loading: false,
      },
      global: { stubs: { AppIcon: true } },
    });
    await flushPromises();

    const acceptButton = wrapper.findAll("button").find((button) => button.text().includes("接受建议"));
    const modifyButton = wrapper.findAll("button").find((button) => button.text().includes("保存修改"));
    expect(acceptButton?.attributes("disabled")).toBeDefined();
    expect(modifyButton?.attributes("disabled")).toBeUndefined();
  });

  it("locks crop fields and canvas interaction while saving", async () => {
    const wrapper = mount(StaticCropEditor, {
      props: { record, sourceUrl: "/dataset-review/review_panel_a/image", loading: true },
      global: { stubs: { AppIcon: true } },
    });
    await flushPromises();

    expect(wrapper.findAll(".crop-fields input").every((input) => input.attributes("disabled") !== undefined)).toBe(true);
    expect(wrapper.find(".crop-fields select").attributes("disabled")).toBeDefined();
    expect(wrapper.find("textarea").attributes("disabled")).toBeDefined();
    expect(wrapper.findAll("footer button").every((button) => button.attributes("disabled") !== undefined)).toBe(true);
    expect(wrapper.find("canvas").classes()).toContain("is-locked");
    expect(wrapper.find("canvas").attributes("aria-disabled")).toBe("true");

    await wrapper.find("canvas").trigger("pointerdown", { clientX: 420, clientY: 300, pointerId: 1 });
    await wrapper.findAll("footer button").at(-1)?.trigger("click");
    expect(wrapper.emitted("save")).toBeUndefined();

    await wrapper.setProps({ loading: false });
    await wrapper.findAll("footer button").at(-1)?.trigger("click");

    expect(wrapper.emitted("save")?.[0]?.[0]).toEqual({
      x: 20,
      y: 30,
      width: 200,
      height: 120,
      panel_role: "paired_fluorescence",
      pair_id: "pair_a",
      crop_notes: null,
      suggestion_id: "suggestion_a",
      crop_review_action: "modified",
    });
  });
});
