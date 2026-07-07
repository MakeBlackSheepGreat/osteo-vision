import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

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
  boneGateStatusLabel: "待生成骨面门控",
};

describe("BoneGateMaskEditor", () => {
  beforeEach(() => {
    const context = {
      canvas: { width: 256, height: 192 },
      clearRect: vi.fn(),
      beginPath: vi.fn(),
      arc: vi.fn(),
      fill: vi.fn(),
      drawImage: vi.fn(),
      fillStyle: "",
      globalCompositeOperation: "source-over",
    };
    HTMLCanvasElement.prototype.getContext = vi.fn(() => context) as unknown as HTMLCanvasElement["getContext"];
    HTMLCanvasElement.prototype.toDataURL = vi.fn(() => "data:image/png;base64,ZmFrZQ==") as unknown as HTMLCanvasElement["toDataURL"];
    HTMLCanvasElement.prototype.getBoundingClientRect = vi.fn(
      () => ({ left: 0, top: 0, width: 256, height: 192 }) as DOMRect,
    ) as unknown as HTMLCanvasElement["getBoundingClientRect"];
  });

  it("emits edited mask payload after drawing and saving", async () => {
    const wrapper = mount(BoneGateMaskEditor, {
      props: { detail, loading: false },
      global: { stubs: { AppIcon: true } },
    });

    await wrapper.find("canvas").trigger("pointerdown", { clientX: 20, clientY: 20 });
    await wrapper.find("canvas").trigger("pointermove", { clientX: 30, clientY: 30 });
    await wrapper.find("canvas").trigger("pointerup");
    await wrapper.findAll("button").at(-1)?.trigger("click");

    const emitted = wrapper.emitted("save")?.[0]?.[0] as Record<string, unknown>;
    expect(emitted.maskPngBase64).toBe("data:image/png;base64,ZmFrZQ==");
    expect(emitted.reviewState).toBe("modified");
    expect(emitted.reviewerNotes).toBe("frontend binary mask editor");
  });
});
