import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ManualAnnotationCanvas from "../src/components/ManualAnnotationCanvas.vue";
import type { AnnotationGeometry } from "../src/types/annotation";

describe("ManualAnnotationCanvas", () => {
  beforeEach(() => {
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
      return {
        canvas: this,
        clearRect: vi.fn(),
        save: vi.fn(),
        restore: vi.fn(),
        beginPath: vi.fn(),
        moveTo: vi.fn(),
        lineTo: vi.fn(),
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
      } as unknown as CanvasRenderingContext2D;
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
});

function latestGeometry(events: unknown[] | undefined): AnnotationGeometry {
  const latest = events?.at(-1) as [AnnotationGeometry] | undefined;
  if (!latest) throw new Error("geometry-change was not emitted");
  return latest[0];
}
