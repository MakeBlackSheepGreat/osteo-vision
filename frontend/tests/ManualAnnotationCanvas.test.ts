import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ManualAnnotationCanvas from "../src/components/ManualAnnotationCanvas.vue";
import type { AnnotationGeometry } from "../src/types/annotation";

interface CanvasContextHarness {
  canvas: HTMLCanvasElement;
  clearRect: ReturnType<typeof vi.fn>;
  save: ReturnType<typeof vi.fn>;
  restore: ReturnType<typeof vi.fn>;
  beginPath: ReturnType<typeof vi.fn>;
  moveTo: ReturnType<typeof vi.fn>;
  lineTo: ReturnType<typeof vi.fn>;
  drawImage: ReturnType<typeof vi.fn>;
  closePath: ReturnType<typeof vi.fn>;
  stroke: ReturnType<typeof vi.fn>;
  fill: ReturnType<typeof vi.fn>;
  arc: ReturnType<typeof vi.fn>;
  setLineDash: ReturnType<typeof vi.fn>;
  globalCompositeOperation: GlobalCompositeOperation;
  strokeStyle: string;
  fillStyle: string;
  lineWidth: number;
  lineCap: CanvasLineCap;
  lineJoin: CanvasLineJoin;
}

let canvasContexts: Map<HTMLCanvasElement, CanvasContextHarness>;

describe("ManualAnnotationCanvas", () => {
  beforeEach(() => {
    canvasContexts = new Map();
    class ResizeObserverStub {
      constructor(private readonly callback: ResizeObserverCallback) {}
      observe() {
        this.callback(
          [{ contentRect: { width: 900, height: 600 } as DOMRectReadOnly } as ResizeObserverEntry],
          this as unknown as ResizeObserver,
        );
      }
      disconnect() {}
      unobserve() {}
    }
    vi.stubGlobal("ResizeObserver", ResizeObserverStub);
    HTMLCanvasElement.prototype.getContext = vi.fn(function (this: HTMLCanvasElement) {
      const existing = canvasContexts.get(this);
      if (existing) return existing as unknown as CanvasRenderingContext2D;
      const context: CanvasContextHarness = {
        canvas: this,
        clearRect: vi.fn(),
        save: vi.fn(),
        restore: vi.fn(),
        beginPath: vi.fn(),
        moveTo: vi.fn(),
        lineTo: vi.fn(),
        drawImage: vi.fn(),
        closePath: vi.fn(),
        stroke: vi.fn(),
        fill: vi.fn(),
        arc: vi.fn(),
        setLineDash: vi.fn(),
        globalCompositeOperation: "source-over",
        strokeStyle: "",
        fillStyle: "",
        lineWidth: 1,
        lineCap: "round",
        lineJoin: "round",
      };
      canvasContexts.set(this, context);
      return context as unknown as CanvasRenderingContext2D;
    }) as unknown as HTMLCanvasElement["getContext"];
    HTMLCanvasElement.prototype.getBoundingClientRect = vi.fn(
      () => ({ left: 0, top: 0, width: 800, height: 600 }) as DOMRect,
    ) as unknown as HTMLCanvasElement["getBoundingClientRect"];
  });

  afterEach(() => vi.unstubAllGlobals());

  it("records brush, eraser and polygon operations in original pixel coordinates", async () => {
    const wrapper = mount(ManualAnnotationCanvas, {
      props: {
        sourceUrl: "/files/preview?path=frame.jpg",
        sourceTitle: "关键帧 12",
        originalWidth: 800,
        originalHeight: 600,
      },
      global: { stubs: { AppIcon: true } },
    });
    const image = wrapper.get("img").element as HTMLImageElement;
    Object.defineProperty(image, "naturalWidth", { configurable: true, value: 800 });
    Object.defineProperty(image, "naturalHeight", { configurable: true, value: 600 });
    await wrapper.get("img").trigger("load");

    const canvas = wrapper.get("canvas");
    await canvas.trigger("pointerdown", { pointerId: 1, clientX: 100, clientY: 120 });
    await canvas.trigger("pointermove", { pointerId: 1, clientX: 180, clientY: 180 });
    await canvas.trigger("pointerup", { pointerId: 1, clientX: 180, clientY: 180 });

    let geometry = latestGeometry(wrapper.emitted("geometry-change"));
    expect(geometry.operations).toHaveLength(1);
    expect(geometry.operations[0]).toMatchObject({ tool: "brush", mode: "add" });
    expect(geometry.operations[0].points[0]).toEqual({ x: 100, y: 120 });

    await wrapper.get('button[aria-label="橡皮擦"]').trigger("click");
    await canvas.trigger("pointerdown", { pointerId: 2, clientX: 220, clientY: 220 });
    await canvas.trigger("pointerup", { pointerId: 2, clientX: 220, clientY: 220 });
    geometry = latestGeometry(wrapper.emitted("geometry-change"));
    expect(geometry.operations[1]).toMatchObject({ tool: "eraser", mode: "erase" });

    await wrapper.get('button[aria-label="多边形"]').trigger("click");
    await canvas.trigger("pointerdown", { pointerId: 3, clientX: 300, clientY: 200 });
    await canvas.trigger("pointerdown", { pointerId: 4, clientX: 420, clientY: 220 });
    await canvas.trigger("pointerdown", { pointerId: 5, clientX: 360, clientY: 340 });
    const closeButton = wrapper.findAll("button").find((button) => button.text().includes("闭合"));
    expect(closeButton).toBeDefined();
    await closeButton!.trigger("click");

    geometry = latestGeometry(wrapper.emitted("geometry-change"));
    expect(geometry.coordinate_space).toBe("image_pixels");
    expect(geometry.operations[2]).toMatchObject({ tool: "polygon", mode: "add" });
    expect(geometry.operations[2].points).toHaveLength(3);

    await wrapper.setProps({ geometry });
    expect(wrapper.get<HTMLButtonElement>('button[aria-label="撤销"]').element.disabled).toBe(false);
    await wrapper.get('button[aria-label="撤销"]').trigger("click");
    geometry = latestGeometry(wrapper.emitted("geometry-change"));
    expect(geometry.operations).toHaveLength(2);
    await wrapper.get('button[aria-label="重做"]').trigger("click");
    geometry = latestGeometry(wrapper.emitted("geometry-change"));
    expect(geometry.operations).toHaveLength(3);
  });

  it("keeps all drawing controls disabled when a submitted annotation is locked", async () => {
    const wrapper = mount(ManualAnnotationCanvas, {
      props: {
        sourceUrl: "/frame.jpg",
        originalWidth: 32,
        originalHeight: 24,
        disabled: true,
        disabledReason: "待医生复核，编辑已锁定",
      },
      global: { stubs: { AppIcon: true } },
    });
    const image = wrapper.get("img").element as HTMLImageElement;
    Object.defineProperty(image, "naturalWidth", { configurable: true, value: 32 });
    Object.defineProperty(image, "naturalHeight", { configurable: true, value: 24 });
    await wrapper.get("img").trigger("load");

    expect(wrapper.get<HTMLButtonElement>('button[aria-label="画笔"]').element.disabled).toBe(true);
    expect(wrapper.get<HTMLButtonElement>('button[aria-label="橡皮擦"]').element.disabled).toBe(true);
    expect(wrapper.text()).toContain("待医生复核，编辑已锁定");
  });

  it("keeps other labels visible on an isolated reference layer", async () => {
    const wrapper = mount(ManualAnnotationCanvas, {
      props: {
        sourceUrl: "/frame.jpg",
        originalWidth: 800,
        originalHeight: 600,
        referenceLayers: [{
          id: "fluorescence_signal",
          label: "fluorescence_signal",
          color: "#1db996",
          geometry: {
            coordinate_space: "image_pixels",
            operations: [{ tool: "brush", mode: "add", radius: 20, points: [{ x: 120, y: 140 }] }],
          },
        }],
      },
      global: { stubs: { AppIcon: true } },
    });
    const image = wrapper.get("img").element as HTMLImageElement;
    Object.defineProperty(image, "naturalWidth", { configurable: true, value: 800 });
    Object.defineProperty(image, "naturalHeight", { configurable: true, value: 600 });
    await wrapper.get("img").trigger("load");

    const canvases = wrapper.findAll("canvas");
    expect(canvases).toHaveLength(3);
    const referenceContext = canvasContexts.get(canvases[0].element as HTMLCanvasElement);
    expect(referenceContext?.drawImage).toHaveBeenCalledTimes(1);
  });

  it("renders a 4K active stroke incrementally without replaying committed geometry per pointer sample", async () => {
    const wrapper = mount(ManualAnnotationCanvas, {
      props: {
        sourceUrl: "/frame-4k.jpg",
        originalWidth: 3840,
        originalHeight: 2160,
      },
      global: { stubs: { AppIcon: true } },
    });
    const image = wrapper.get("img").element as HTMLImageElement;
    Object.defineProperty(image, "naturalWidth", { configurable: true, value: 3840 });
    Object.defineProperty(image, "naturalHeight", { configurable: true, value: 2160 });
    await wrapper.get("img").trigger("load");

    const canvases = wrapper.findAll("canvas");
    expect(canvases).toHaveLength(2);
    const committed = canvasContexts.get(canvases[0].element as HTMLCanvasElement);
    const draft = canvasContexts.get(canvases[1].element as HTMLCanvasElement);
    expect(committed).toBeDefined();
    expect(draft).toBeDefined();
    committed!.clearRect.mockClear();
    committed!.lineTo.mockClear();
    draft!.clearRect.mockClear();
    draft!.lineTo.mockClear();

    await canvases[0].trigger("pointerdown", { pointerId: 9, clientX: 40, clientY: 50 });
    for (let index = 1; index <= 120; index += 1) {
      await canvases[0].trigger("pointermove", {
        pointerId: 9,
        clientX: 40 + index * 2,
        clientY: 50 + index,
      });
    }

    expect(committed!.clearRect).not.toHaveBeenCalled();
    expect(committed!.lineTo).not.toHaveBeenCalled();
    expect(draft!.clearRect).toHaveBeenCalledTimes(1);
    expect(draft!.lineTo).toHaveBeenCalledTimes(120);

    await canvases[0].trigger("pointerup", { pointerId: 9, clientX: 280, clientY: 170 });

    expect(committed!.clearRect).not.toHaveBeenCalled();
    expect(committed!.lineTo).toHaveBeenCalledTimes(120);
    expect(draft!.clearRect).toHaveBeenCalledTimes(2);
    const geometry = latestGeometry(wrapper.emitted("geometry-change"));
    expect(geometry.operations[0].points).toHaveLength(121);
    expect(geometry.coordinate_space).toBe("image_pixels");
  });

  it("previews 4K erasing incrementally and performs one canonical replay when the stroke ends", async () => {
    const wrapper = mount(ManualAnnotationCanvas, {
      props: {
        sourceUrl: "/frame-4k.jpg",
        originalWidth: 3840,
        originalHeight: 2160,
        geometry: {
          coordinate_space: "image_pixels",
          operations: [{
            tool: "brush",
            mode: "add",
            radius: 30,
            points: [{ x: 100, y: 100 }, { x: 800, y: 500 }],
          }],
        },
      },
      global: { stubs: { AppIcon: true } },
    });
    const image = wrapper.get("img").element as HTMLImageElement;
    Object.defineProperty(image, "naturalWidth", { configurable: true, value: 3840 });
    Object.defineProperty(image, "naturalHeight", { configurable: true, value: 2160 });
    await wrapper.get("img").trigger("load");
    await wrapper.get('button[aria-label="橡皮擦"]').trigger("click");

    const canvases = wrapper.findAll("canvas");
    const committed = canvasContexts.get(canvases[0].element as HTMLCanvasElement)!;
    committed.clearRect.mockClear();
    committed.lineTo.mockClear();

    await canvases[0].trigger("pointerdown", { pointerId: 10, clientX: 120, clientY: 100 });
    for (let index = 1; index <= 40; index += 1) {
      await canvases[0].trigger("pointermove", {
        pointerId: 10,
        clientX: 120 + index * 3,
        clientY: 100 + index * 2,
      });
    }

    expect(committed.clearRect).not.toHaveBeenCalled();
    expect(committed.lineTo).toHaveBeenCalledTimes(40);
    await canvases[0].trigger("pointerup", { pointerId: 10, clientX: 240, clientY: 180 });
    expect(committed.clearRect).toHaveBeenCalledTimes(1);
    const geometry = latestGeometry(wrapper.emitted("geometry-change"));
    expect(geometry.operations.at(-1)).toMatchObject({ tool: "eraser", mode: "erase" });
    expect(geometry.operations.at(-1)?.points).toHaveLength(41);
  });
});

function latestGeometry(events: unknown[] | undefined): AnnotationGeometry {
  const latest = events?.at(-1) as [AnnotationGeometry] | undefined;
  if (!latest) throw new Error("geometry-change was not emitted");
  return latest[0];
}
