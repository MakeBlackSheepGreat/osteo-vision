import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import StaticMaskEditor from "../src/components/StaticMaskEditor.vue";
import type { DatasetReviewRecord } from "../src/types/datasetReview";

const record: DatasetReviewRecord = {
  record_id: "d047-panel-001",
  dataset_id: "d047_pmc_jaw_fluorescence_figures",
  source_record_id: "PMC_TEST_figure_2",
  image_path: "C:\\data\\panel.png",
  image_href: "/dataset-review/d047-panel-001/image",
  review_state: "review_required",
  license: "CC BY",
};

type PendingImage = {
  onload: (() => void) | null;
  onerror: (() => void) | null;
};

function installPendingImageLoader(): PendingImage[] {
  const pendingImages: PendingImage[] = [];
  class PendingMaskImage implements PendingImage {
    crossOrigin = "";
    onload: (() => void) | null = null;
    onerror: (() => void) | null = null;

    set src(_value: string) {
      pendingImages.push(this);
    }
  }
  vi.stubGlobal("Image", PendingMaskImage);
  return pendingImages;
}

describe("StaticMaskEditor", () => {
  beforeEach(() => {
    HTMLCanvasElement.prototype.getContext = vi.fn(function (this: HTMLCanvasElement) {
      return {
        canvas: this,
        clearRect: vi.fn(),
        drawImage: vi.fn(),
        getImageData: vi.fn((_x: number, _y: number, width: number, height: number) => ({
          data: new Uint8ClampedArray(width * height * 4),
          width,
          height,
        })),
        createImageData: vi.fn((width: number, height: number) => ({
          data: new Uint8ClampedArray(width * height * 4),
          width,
          height,
        })),
        putImageData: vi.fn(),
        save: vi.fn(),
        restore: vi.fn(),
        beginPath: vi.fn(),
        moveTo: vi.fn(),
        lineTo: vi.fn(),
        stroke: vi.fn(),
        arc: vi.fn(),
        fill: vi.fn(),
        globalCompositeOperation: "source-over",
        strokeStyle: "",
        fillStyle: "",
        lineWidth: 1,
        lineCap: "round",
        lineJoin: "round",
      } as unknown as CanvasRenderingContext2D;
    }) as unknown as HTMLCanvasElement["getContext"];
    HTMLCanvasElement.prototype.toDataURL = vi.fn(() => "data:image/png;base64,YmluYXJ5") as unknown as HTMLCanvasElement["toDataURL"];
    HTMLCanvasElement.prototype.getBoundingClientRect = vi.fn(
      () => ({ left: 0, top: 0, width: 640, height: 360 }) as DOMRect,
    ) as unknown as HTMLCanvasElement["getBoundingClientRect"];
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("keeps the original image dimensions and exports a binary PNG payload", async () => {
    const wrapper = mount(StaticMaskEditor, {
      props: {
        record,
        sourceUrl: "http://127.0.0.1:8001/dataset-review/d047-panel-001/image",
        loading: false,
      },
      global: { stubs: { AppIcon: true } },
    });
    const image = wrapper.find("img").element as HTMLImageElement;
    Object.defineProperty(image, "naturalWidth", { configurable: true, value: 640 });
    Object.defineProperty(image, "naturalHeight", { configurable: true, value: 360 });
    await wrapper.find("img").trigger("load");

    const canvas = wrapper.find("canvas").element as HTMLCanvasElement;
    expect(canvas.width).toBe(640);
    expect(canvas.height).toBe(360);

    await wrapper.find("canvas").trigger("pointerdown", { clientX: 320, clientY: 180 });
    await wrapper.find("canvas").trigger("pointerup");
    await wrapper.find("button.save-button").trigger("click");

    const payload = wrapper.emitted("save")?.[0]?.[0] as Record<string, unknown>;
    expect(payload.maskPngBase64).toBe("data:image/png;base64,YmluYXJ5");
    expect(payload.reviewState).toBe("modified");
    expect(payload.reviewerRole).toBe("project_reviewer");
  });

  it("sends physician authority only after the user selects it", async () => {
    const wrapper = mount(StaticMaskEditor, {
      props: { record: { ...record, width: 32, height: 24 }, sourceUrl: "/image", loading: false },
      global: { stubs: { AppIcon: true } },
    });
    const image = wrapper.find("img").element as HTMLImageElement;
    Object.defineProperty(image, "naturalWidth", { configurable: true, value: 32 });
    Object.defineProperty(image, "naturalHeight", { configurable: true, value: 24 });
    await wrapper.find("img").trigger("load");
    const selects = wrapper.findAll("select");
    await selects[0].setValue("physician");
    await wrapper.find("button.save-button").trigger("click");

    expect((wrapper.emitted("save")?.[0]?.[0] as Record<string, unknown>).reviewerRole).toBe("physician");
  });

  it("disables every mask editing tool until the source image loads", async () => {
    const wrapper = mount(StaticMaskEditor, {
      props: { record, sourceUrl: "/image", loading: false },
      global: { stubs: { AppIcon: true } },
    });

    const toolbarButtons = wrapper.findAll<HTMLButtonElement>(".editor-toolbar button");
    expect(toolbarButtons).toHaveLength(5);
    expect(toolbarButtons.every((button) => button.element.disabled)).toBe(true);
    expect(toolbarButtons[0].attributes("title")).toBe("原始裁剪图尚未载入，编辑工具暂不可用。");
    expect(wrapper.get<HTMLInputElement>('.brush-control input[type="range"]').element.disabled).toBe(true);

    await wrapper.find("img").trigger("error");

    expect(wrapper.findAll<HTMLButtonElement>(".editor-toolbar button").every((button) => button.element.disabled)).toBe(true);
    expect(wrapper.get('.editor-toolbar button').attributes("title")).toBe("原始裁剪图读取失败，编辑工具暂不可用。");
    expect(wrapper.text()).toContain("图像未载入，保存已停用");
  });

  it("enables drawing tools after the source image loads", async () => {
    const wrapper = mount(StaticMaskEditor, {
      props: { record: { ...record, width: 32, height: 24 }, sourceUrl: "/image", loading: false },
      global: { stubs: { AppIcon: true } },
    });
    const image = wrapper.find("img").element as HTMLImageElement;
    Object.defineProperty(image, "naturalWidth", { configurable: true, value: 32 });
    Object.defineProperty(image, "naturalHeight", { configurable: true, value: 24 });

    await wrapper.find("img").trigger("load");

    const toolbarButtons = wrapper.findAll<HTMLButtonElement>(".editor-toolbar button");
    expect(toolbarButtons[0].element.disabled).toBe(false);
    expect(toolbarButtons[1].element.disabled).toBe(false);
    expect(toolbarButtons[2].attributes("title")).toBe("暂无可撤销操作");
    expect(toolbarButtons[3].attributes("title")).toBe("暂无可重做操作");
    expect(toolbarButtons[4].element.disabled).toBe(false);
    expect(wrapper.get<HTMLInputElement>('.brush-control input[type="range"]').element.disabled).toBe(false);
  });

  it("keeps editing and saving locked until an existing mask finishes loading", async () => {
    const pendingImages = installPendingImageLoader();
    const wrapper = mount(StaticMaskEditor, {
      props: {
        record: { ...record, width: 32, height: 24 },
        sourceUrl: "/image",
        maskUrl: "/mask",
        loading: false,
      },
      global: { stubs: { AppIcon: true } },
    });
    const image = wrapper.find("img").element as HTMLImageElement;
    Object.defineProperty(image, "naturalWidth", { configurable: true, value: 32 });
    Object.defineProperty(image, "naturalHeight", { configurable: true, value: 24 });

    await wrapper.find("img").trigger("load");

    expect(pendingImages).toHaveLength(1);
    expect(wrapper.findAll<HTMLButtonElement>(".editor-toolbar button").every((button) => button.element.disabled)).toBe(true);
    expect(wrapper.get<HTMLButtonElement>("button.save-button").element.disabled).toBe(true);
    expect(wrapper.get("button.save-button").attributes("title")).toContain("正在载入已有复核掩膜");

    pendingImages[0].onload?.();
    await flushPromises();

    expect(wrapper.get<HTMLButtonElement>(".editor-toolbar button").element.disabled).toBe(false);
    expect(wrapper.get<HTMLButtonElement>("button.save-button").element.disabled).toBe(false);
    expect(wrapper.text()).toContain("已有复核掩膜已载入");
  });

  it("keeps editing and saving locked when an existing mask fails to load", async () => {
    const pendingImages = installPendingImageLoader();
    const wrapper = mount(StaticMaskEditor, {
      props: {
        record: { ...record, width: 32, height: 24 },
        sourceUrl: "/image",
        maskUrl: "/missing-mask",
        loading: false,
      },
      global: { stubs: { AppIcon: true } },
    });
    const image = wrapper.find("img").element as HTMLImageElement;
    Object.defineProperty(image, "naturalWidth", { configurable: true, value: 32 });
    Object.defineProperty(image, "naturalHeight", { configurable: true, value: 24 });

    await wrapper.find("img").trigger("load");
    pendingImages[0].onerror?.();
    await flushPromises();

    expect(wrapper.findAll<HTMLButtonElement>(".editor-toolbar button").every((button) => button.element.disabled)).toBe(true);
    expect(wrapper.get<HTMLButtonElement>("button.save-button").element.disabled).toBe(true);
    expect(wrapper.text()).toContain("已有复核掩膜读取失败，编辑和保存已停用");
    await wrapper.get("button.save-button").trigger("click");
    expect(wrapper.emitted("save")).toBeUndefined();
  });
});
