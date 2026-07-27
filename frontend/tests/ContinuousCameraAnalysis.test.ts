import { defineComponent } from "vue";
import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  isDisplayableLiveFrame,
  isCurrentLiveFrameDisplay,
  resolveLiveFrameDisplaySource,
  useContinuousCameraAnalysis,
} from "../src/composables/useContinuousCameraAnalysis";
import { ApiError, apiClient } from "../src/services/apiClient";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
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

  it("aborts an in-flight frame and ignores its completion after stop", async () => {
    vi.useFakeTimers();
    let releaseAnalysis: (() => void) | undefined;
    let frameSignal: AbortSignal | undefined;
    const analyzeFrame = vi.fn(
      (_blob: Blob, context: { signal: AbortSignal }) =>
        new Promise<void>((resolve) => {
          frameSignal = context.signal;
          releaseAnalysis = resolve;
        }),
    );
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

    await expect(controls?.start()).resolves.toBe(true);
    await vi.advanceTimersByTimeAsync(0);
    expect(frameSignal?.aborted).toBe(false);

    controls?.stop(false);
    expect(frameSignal?.aborted).toBe(true);
    releaseAnalysis?.();
    await Promise.resolve();
    await vi.runOnlyPendingTimersAsync();

    expect(controls?.completedCount.value).toBe(0);
    expect(controls?.failedCount.value).toBe(0);
    expect(analyzeFrame).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });

  it("does not activate or schedule frames when unmounted during preparation", async () => {
    vi.useFakeTimers();
    let releasePreparation: (() => void) | undefined;
    const captureFrame = vi.fn();
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
          captureFrame,
          analyzeFrame: vi.fn(),
          canAnalyze: () => true,
          beforeStart,
        });
        return () => null;
      },
    });
    const wrapper = mount(Harness);

    const startPromise = controls?.start();
    expect(controls?.starting.value).toBe(true);
    wrapper.unmount();
    releasePreparation?.();

    await expect(startPromise).resolves.toBe(false);
    await vi.runOnlyPendingTimersAsync();
    expect(controls?.active.value).toBe(false);
    expect(captureFrame).not.toHaveBeenCalled();
  });

  it.each([
    { status: 429, retryAfterMs: 2000 },
    { status: 503, retryAfterMs: null },
  ])("backs off boundedly after a $status response", async ({ status, retryAfterMs }) => {
    vi.useFakeTimers();
    const analyzeFrame = vi.fn().mockRejectedValue(new ApiError(status, null, retryAfterMs));
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
    expect(analyzeFrame).toHaveBeenCalledTimes(1);

    const firstDelayMs = status === 429 ? 2000 : 500;
    await vi.advanceTimersByTimeAsync(firstDelayMs - 1);
    expect(analyzeFrame).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(analyzeFrame).toHaveBeenCalledTimes(2);

    await vi.advanceTimersByTimeAsync(10_000);
    expect(analyzeFrame.mock.calls.length).toBeLessThanOrEqual(status === 429 ? 7 : 6);
    controls?.stop(false);
    wrapper.unmount();
  });

  it("aborts a timed-out request and delays the next attempt when interval is zero", async () => {
    vi.useFakeTimers();
    const invalidations: string[] = [];
    const analyzeFrame = vi.fn(
      (_blob: Blob, context: { signal: AbortSignal }) =>
        new Promise<void>((_resolve, reject) => {
          context.signal.addEventListener(
            "abort",
            () => reject(new DOMException("request timed out", "AbortError")),
            { once: true },
          );
        }),
    );
    let controls: ReturnType<typeof useContinuousCameraAnalysis> | undefined;
    const Harness = defineComponent({
      setup() {
        controls = useContinuousCameraAnalysis({
          captureFrame: vi.fn().mockResolvedValue(new Blob(["jpeg"], { type: "image/jpeg" })),
          analyzeFrame,
          canAnalyze: () => true,
          requestTimeoutMs: 250,
          onFrameInvalidated: (reason) => invalidations.push(reason),
        });
        return () => null;
      },
    });
    const wrapper = mount(Harness);

    await expect(controls?.start()).resolves.toBe(true);
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(249);
    expect(analyzeFrame).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);

    expect(controls?.failedCount.value).toBe(1);
    expect(invalidations).toContain("timed_out");
    await vi.advanceTimersByTimeAsync(499);
    expect(analyzeFrame).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(analyzeFrame).toHaveBeenCalledTimes(2);

    controls?.stop(false);
    wrapper.unmount();
  });

  it("clears an old overlay on failure and accepts a later successful frame", async () => {
    vi.useFakeTimers();
    let overlay = "old-overlay.png";
    const analyzeFrame = vi.fn()
      .mockRejectedValueOnce(new ApiError(503, null))
      .mockImplementationOnce(async () => {
        overlay = "recovered-overlay.png";
      });
    let controls: ReturnType<typeof useContinuousCameraAnalysis> | undefined;
    const Harness = defineComponent({
      setup() {
        controls = useContinuousCameraAnalysis({
          captureFrame: vi.fn().mockResolvedValue(new Blob(["jpeg"], { type: "image/jpeg" })),
          analyzeFrame,
          canAnalyze: () => true,
          onFrameInvalidated: () => {
            overlay = "";
          },
        });
        return () => null;
      },
    });
    const wrapper = mount(Harness);

    controls?.setIntervalSec(1);
    await expect(controls?.start()).resolves.toBe(true);
    await vi.advanceTimersByTimeAsync(0);
    expect(overlay).toBe("");

    await vi.advanceTimersByTimeAsync(1000);
    expect(analyzeFrame).toHaveBeenCalledTimes(2);
    expect(overlay).toBe("recovered-overlay.png");
    expect(controls?.completedCount.value).toBe(1);

    controls?.stop(false);
    wrapper.unmount();
  });

  it("only accepts live overlays whose sequence, source, case, timestamp, and age still match", () => {
    const identity = {
      source: "video" as const,
      sequence: 7,
      sessionId: "session-1",
      capturedAt: "2026-07-19T12:00:00.000Z",
      capturedAtMs: Date.parse("2026-07-19T12:00:00.000Z"),
      requestGeneration: 4,
    };
    const result = { case_id: "case-1", captured_at: identity.capturedAt };
    const options = {
      activeSource: "video" as const,
      caseId: "case-1",
      requestGeneration: 4,
      nowMs: identity.capturedAtMs + 1000,
      maxAgeMs: 15_000,
    };

    expect(isCurrentLiveFrameDisplay(result, identity, identity, options)).toBe(true);
    expect(isCurrentLiveFrameDisplay(result, identity, { ...identity, sequence: 8 }, options)).toBe(false);
    expect(isDisplayableLiveFrame(result, identity, options)).toBe(true);
    expect(isDisplayableLiveFrame(result, identity, { ...options, nowMs: identity.capturedAtMs + 1_000 })).toBe(true);
    expect(isCurrentLiveFrameDisplay(result, identity, identity, { ...options, activeSource: "camera" })).toBe(false);
    expect(isDisplayableLiveFrame(result, identity, { ...options, activeSource: "camera" })).toBe(false);
    expect(isCurrentLiveFrameDisplay(result, identity, identity, { ...options, nowMs: identity.capturedAtMs + 15_001 })).toBe(false);
    expect(isDisplayableLiveFrame(result, identity, { ...options, nowMs: identity.capturedAtMs + 15_001 })).toBe(false);
    expect(isCurrentLiveFrameDisplay({ ...result, case_id: "case-2" }, identity, identity, options)).toBe(false);
    expect(isDisplayableLiveFrame({ ...result, case_id: "case-2" }, identity, options)).toBe(false);
    expect(isCurrentLiveFrameDisplay({ ...result, captured_at: "2026-07-19T12:00:01.000Z" }, identity, identity, options)).toBe(false);
    expect(isDisplayableLiveFrame({ ...result, captured_at: "2026-07-19T12:00:01.000Z" }, identity, options)).toBe(false);
  });

  it("keeps multichannel MP4 and camera results displayable during continuous inference", () => {
    expect(
      resolveLiveFrameDisplaySource({
        inputSource: "file",
        cameraActive: false,
        fileVideoActive: false,
        multichannelModeActive: true,
        multichannelRealtimeEnabled: true,
      }),
    ).toBe("video");
    expect(
      resolveLiveFrameDisplaySource({
        inputSource: "camera",
        cameraActive: true,
        fileVideoActive: false,
        multichannelModeActive: true,
        multichannelRealtimeEnabled: true,
      }),
    ).toBe("camera");
    expect(
      resolveLiveFrameDisplaySource({
        inputSource: "file",
        cameraActive: false,
        fileVideoActive: false,
        multichannelModeActive: true,
        multichannelRealtimeEnabled: false,
      }),
    ).toBe("");
  });

  it("reads Retry-After from a live-frame capacity response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "busy" }), {
          status: 429,
          headers: { "Content-Type": "application/json", "Retry-After": "2" },
        }),
      ),
    );

    await expect(
      apiClient.analyzeLiveFrame("case_busy", new Blob(["jpeg"], { type: "image/jpeg" }), {
        capturedAt: "2026-07-19T12:00:00.000Z",
        sequence: 1,
        threshold: 0.6,
        colormap: "green",
      }),
    ).rejects.toMatchObject({ status: 429, retryAfterMs: 2000 });
  });

  it("forwards cancellation to the live-frame HTTP request", async () => {
    const controller = new AbortController();
    let receivedSignal: AbortSignal | null | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
        receivedSignal = init?.signal;
        return new Promise<Response>((_resolve, reject) => {
          receivedSignal?.addEventListener(
            "abort",
            () => reject(new DOMException("request canceled", "AbortError")),
            { once: true },
          );
        });
      }),
    );

    const request = apiClient.analyzeLiveFrame(
      "case_abort",
      new Blob(["jpeg"], { type: "image/jpeg" }),
      {
        capturedAt: "2026-07-19T12:00:00.000Z",
        sequence: 1,
        threshold: 0.6,
        colormap: "green",
        signal: controller.signal,
      },
    );
    controller.abort();

    await expect(request).rejects.toMatchObject({ name: "AbortError" });
    expect(receivedSignal).toBe(controller.signal);
  });
});
