import { defineComponent } from "vue";
import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useContinuousCameraAnalysis } from "../src/composables/useContinuousCameraAnalysis";

afterEach(() => {
  vi.useRealTimers();
});

describe("continuous camera analysis", () => {
  it("runs one bounded frame at a time and schedules the next frame after completion", async () => {
    vi.useFakeTimers();
    let releaseAnalysis: (() => void) | undefined;
    const analyzeFrame = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          releaseAnalysis = resolve;
        }),
    );
    const captureFrame = vi.fn().mockResolvedValue(new Blob(["jpeg"], { type: "image/jpeg" }));
    let controls: ReturnType<typeof useContinuousCameraAnalysis> | undefined;

    const Harness = defineComponent({
      setup() {
        controls = useContinuousCameraAnalysis({
          captureFrame,
          analyzeFrame,
          canAnalyze: () => true,
        });
        return () => null;
      },
    });
    const wrapper = mount(Harness);

    controls?.setIntervalSec(5);
    await expect(controls?.start()).resolves.toBe(true);
    await vi.advanceTimersByTimeAsync(0);
    expect(captureFrame).toHaveBeenCalledTimes(1);
    expect(analyzeFrame).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(20000);
    expect(captureFrame).toHaveBeenCalledTimes(1);

    releaseAnalysis?.();
    await Promise.resolve();
    await vi.advanceTimersByTimeAsync(4999);
    expect(captureFrame).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(captureFrame).toHaveBeenCalledTimes(2);

    controls?.stop(false);
    wrapper.unmount();
  });

  it("runs the next frame immediately after the previous inference when interval is zero", async () => {
    vi.useFakeTimers();
    const analyzeFrame = vi.fn().mockResolvedValue(undefined);
    let controls: ReturnType<typeof useContinuousCameraAnalysis> | undefined;
    const Harness = defineComponent({
      setup() {
        controls = useContinuousCameraAnalysis({
          captureFrame: vi.fn().mockResolvedValue(new Blob(["jpeg"], { type: "image/jpeg" })),
          analyzeFrame,
          canAnalyze: () => true,
        });
        return () => null;
      },
    });
    const wrapper = mount(Harness);

    controls?.setIntervalSec(0);
    await expect(controls?.start()).resolves.toBe(true);
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(1);

    expect(analyzeFrame).toHaveBeenCalledTimes(2);
    controls?.stop(false);
    wrapper.unmount();
  });

  it("refuses to start when the case or camera is unavailable", async () => {
    let controls: ReturnType<typeof useContinuousCameraAnalysis> | undefined;
    const Harness = defineComponent({
      setup() {
        controls = useContinuousCameraAnalysis({
          captureFrame: vi.fn(),
          analyzeFrame: vi.fn(),
          canAnalyze: () => false,
        });
        return () => null;
      },
    });
    const wrapper = mount(Harness);

    await expect(controls?.start()).resolves.toBe(false);
    expect(controls?.active.value).toBe(false);
    wrapper.unmount();
  });

  it("stops continuous analysis after a missing live-frame route response", async () => {
    vi.useFakeTimers();
    const onMessage = vi.fn();
    let controls: ReturnType<typeof useContinuousCameraAnalysis> | undefined;
    const Harness = defineComponent({
      setup() {
        controls = useContinuousCameraAnalysis({
          captureFrame: vi.fn().mockResolvedValue(new Blob(["jpeg"], { type: "image/jpeg" })),
          analyzeFrame: vi.fn().mockRejectedValue(new Error("接口请求失败，状态码 404")),
          canAnalyze: () => true,
          onMessage,
        });
        return () => null;
      },
    });
    const wrapper = mount(Harness);

    await expect(controls?.start()).resolves.toBe(true);
    await vi.advanceTimersByTimeAsync(0);

    expect(controls?.active.value).toBe(false);
    expect(onMessage).toHaveBeenCalledWith(
      "实时分割接口未就绪，请通过根目录 start_platform.cmd 重启平台后重试。",
      "error",
    );
    wrapper.unmount();
  });

  it("waits for model preparation before capturing the first live frame", async () => {
    vi.useFakeTimers();
    const beforeStart = vi.fn().mockResolvedValue(undefined);
    const captureFrame = vi.fn().mockResolvedValue(new Blob(["jpeg"], { type: "image/jpeg" }));
    let controls: ReturnType<typeof useContinuousCameraAnalysis> | undefined;
    const Harness = defineComponent({
      setup() {
        controls = useContinuousCameraAnalysis({
          captureFrame,
          analyzeFrame: vi.fn().mockResolvedValue(undefined),
          canAnalyze: () => true,
          beforeStart,
        });
        return () => null;
      },
    });
    const wrapper = mount(Harness);

    await expect(controls?.start()).resolves.toBe(true);
    expect(beforeStart).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(0);
    expect(captureFrame).toHaveBeenCalledTimes(1);
    controls?.stop(false);
    wrapper.unmount();
  });

  it("shares one start preparation across repeated start requests", async () => {
    let releasePreparation: (() => void) | undefined;
    const beforeStart = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          releasePreparation = resolve;
        }),
    );
    let controls: ReturnType<typeof useContinuousCameraAnalysis> | undefined;
    const Harness = defineComponent({
      setup() {
        controls = useContinuousCameraAnalysis({
          captureFrame: vi.fn(),
          analyzeFrame: vi.fn(),
          canAnalyze: () => true,
          beforeStart,
        });
        return () => null;
      },
    });
    const wrapper = mount(Harness);

    const firstStart = controls?.start();
    const secondStart = controls?.start();
    expect(controls?.starting.value).toBe(true);
    expect(controls?.active.value).toBe(false);
    expect(beforeStart).toHaveBeenCalledTimes(1);

    releasePreparation?.();
    await expect(firstStart).resolves.toBe(true);
    await expect(secondStart).resolves.toBe(true);
    expect(controls?.starting.value).toBe(false);
    expect(controls?.active.value).toBe(true);

    controls?.stop(false);
    wrapper.unmount();
  });

  it("passes the playback timestamp through each continuous frame context", async () => {
    vi.useFakeTimers();
    const analyzeFrame = vi.fn().mockResolvedValue(undefined);
    let controls: ReturnType<typeof useContinuousCameraAnalysis> | undefined;
    const Harness = defineComponent({
      setup() {
        controls = useContinuousCameraAnalysis({
          captureFrame: vi.fn().mockResolvedValue(new Blob(["jpeg"], { type: "image/jpeg" })),
          analyzeFrame,
          canAnalyze: () => true,
          getTimestampSec: () => 3.25,
        });
        return () => null;
      },
    });
    const wrapper = mount(Harness);

    await expect(controls?.start()).resolves.toBe(true);
    await vi.advanceTimersByTimeAsync(0);
    expect(analyzeFrame).toHaveBeenCalledWith(
      expect.any(Blob),
      expect.objectContaining({ timestampSec: 3.25 }),
    );
    controls?.stop(false);
    wrapper.unmount();
  });
});
