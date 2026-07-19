import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import BoneGateMaskEditor from "../src/components/BoneGateMaskEditor.vue";
import type { HotspotFrameDetail } from "../src/components/analysisPreview";

const detail: HotspotFrameDetail = {
  key: "1",
  frameIndex: 1,
  timestampSec: 0.5,
  frameLabel: "帧 1",
  timestampLabel: "0.50s",
  candidateCountLabel: "1 个候选",
  positiveAreaLabel: "10.00%",
  roiAreaLabel: "未命中 ROI",
  topBBoxLabel: "1, 2, 10, 20",
  evidenceLabel: "frame.jpg",
  domainBoundary: "需医生复核",
  reviewRequired: true,
  overlayHref: "/preview/frame.jpg",
  boneGateMaskHref: "/preview/bone-gate-mask.png",
  boneGateStatusLabel: "待生成骨面门控",
};

let drawArc = vi.fn();
let drawImage = vi.fn();
let putImageData = vi.fn();
let assignedImageSrc = "";
let imageLoadMode: "success" | "error" = "success";

class TestImage {
  crossOrigin: string | null = null;
  onload: ((event: Event) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  private source = "";

  set src(value: string) {
    this.source = value;
    assignedImageSrc = value;
    queueMicrotask(() => {
      if (imageLoadMode === "success") this.onload?.(new Event("load"));
      else this.onerror?.(new Event("error"));
    });
  }

  get src() {
    return this.source;
  }
}

describe("BoneGateMaskEditor", () => {
  beforeEach(() => {
    drawArc = vi.fn();
    drawImage = vi.fn();
    putImageData = vi.fn();
    assignedImageSrc = "";
    imageLoadMode = "success";
    vi.stubGlobal("Image", TestImage);
    const context = {
      canvas: { width: 256, height: 192 },
      clearRect: vi.fn(),
      beginPath: vi.fn(),
      arc: drawArc,
      fill: vi.fn(),
      drawImage,
      getImageData: vi.fn(() => {
        const data = new Uint8ClampedArray(256 * 192 * 4);
        data[0] = 255;
        data[1] = 255;
        data[2] = 255;
        data[3] = 255;
        return { data, width: 256, height: 192 };
      }),
      createImageData: vi.fn(() => ({ data: new Uint8ClampedArray(256 * 192 * 4), width: 256, height: 192 })),
      putImageData,
      fillStyle: "",
      globalCompositeOperation: "source-over",
    };
    HTMLCanvasElement.prototype.getContext = vi.fn(() => context) as unknown as HTMLCanvasElement["getContext"];
    HTMLCanvasElement.prototype.toDataURL = vi.fn(() => "data:image/png;base64,ZmFrZQ==") as unknown as HTMLCanvasElement["toDataURL"];
    HTMLCanvasElement.prototype.getBoundingClientRect = vi.fn(
      () => ({ left: 0, top: 0, width: 256, height: 192 }) as DOMRect,
    ) as unknown as HTMLCanvasElement["getBoundingClientRect"];
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads the current frame mask before drawing and saving", async () => {
    const wrapper = mount(BoneGateMaskEditor, {
      props: { detail, loading: false },
      global: { stubs: { AppIcon: true } },
    });
    await flushPromises();

    expect(assignedImageSrc).toBe(detail.boneGateMaskHref);
    expect(drawImage).toHaveBeenCalledTimes(1);
    expect(putImageData).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).toContain("已有骨面掩膜已载入");

    await wrapper.find("canvas").trigger("pointerdown", { clientX: 20, clientY: 20 });
    await wrapper.find("canvas").trigger("pointermove", { clientX: 30, clientY: 30 });
    await wrapper.find("canvas").trigger("pointerup");
    await wrapper.find("button.save-mask-button").trigger("click");

    const emitted = wrapper.emitted("save")?.[0]?.[0] as Record<string, unknown>;
    expect(emitted.maskPngBase64).toBe("data:image/png;base64,ZmFrZQ==");
    expect(emitted.reviewState).toBe("modified");
    expect(emitted.reviewerNotes).toBe("frontend binary mask editor");
  });

  it("locks mask controls and canvas interaction while saving", async () => {
    const wrapper = mount(BoneGateMaskEditor, {
      props: { detail, loading: true },
      global: { stubs: { AppIcon: true } },
    });
    await flushPromises();

    expect(wrapper.findAll(".editor-toolbar button").every((button) => button.attributes("disabled") !== undefined)).toBe(true);
    expect(wrapper.find(".editor-toolbar input").attributes("disabled")).toBeDefined();
    expect(wrapper.find(".editor-toolbar select").attributes("disabled")).toBeDefined();
    expect(wrapper.find("canvas").classes()).toContain("is-locked");
    expect(wrapper.find("canvas").attributes("aria-disabled")).toBe("true");

    const drawCount = drawArc.mock.calls.length;
    await wrapper.find("canvas").trigger("pointerdown", { clientX: 20, clientY: 20 });
    expect(drawArc).toHaveBeenCalledTimes(drawCount);
    await wrapper.find("button.save-mask-button").trigger("click");
    expect(wrapper.emitted("save")).toBeUndefined();

    await wrapper.setProps({ loading: false });
    await wrapper.find("button.save-mask-button").trigger("click");

    expect(wrapper.emitted("save")?.[0]?.[0]).toMatchObject({
      maskPngBase64: "data:image/png;base64,ZmFrZQ==",
      reviewState: "modified",
    });
  });

  it("shows a load error and blocks saving an empty canvas", async () => {
    imageLoadMode = "error";
    const wrapper = mount(BoneGateMaskEditor, {
      props: { detail, loading: false },
      global: { stubs: { AppIcon: true } },
    });
    await flushPromises();

    expect(wrapper.get('[role="alert"]').text()).toContain("已有骨面掩膜读取失败");
    expect(wrapper.get("button.save-mask-button").attributes("disabled")).toBeDefined();
    expect(wrapper.get("canvas").attributes("aria-disabled")).toBe("true");

    await wrapper.get("button.save-mask-button").trigger("click");
    expect(wrapper.emitted("save")).toBeUndefined();
  });
});
