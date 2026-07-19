import { computed, onBeforeUnmount, ref } from "vue";

export type ContinuousCameraAnalysisIntervalSec = 0 | 1 | 2 | 3 | 5 | 10;

export interface ContinuousCameraAnalysisOptions {
  captureFrame: () => Promise<Blob>;
  analyzeFrame: (blob: Blob, context: ContinuousCameraFrameContext) => Promise<void>;
  canAnalyze: () => boolean;
  getTimestampSec?: () => number | undefined;
  beforeStart?: () => Promise<void>;
  onMessage?: (message: string, type?: "info" | "error") => void;
}

export interface ContinuousCameraFrameContext {
  capturedAt: string;
  sequence: number;
  sessionId: string;
  trigger: "continuous";
  timestampSec?: number;
}

const SUPPORTED_INTERVALS = [0, 1, 2, 3, 5, 10] as const;

export function useContinuousCameraAnalysis(options: ContinuousCameraAnalysisOptions) {
  const active = ref(false);
  const starting = ref(false);
  const running = ref(false);
  const intervalSec = ref<ContinuousCameraAnalysisIntervalSec>(0);
  const completedCount = ref(0);
  const failedCount = ref(0);
  const lastCompletedAt = ref("");
  const sessionId = ref("");
  let timerId: number | null = null;
  let startPromise: Promise<boolean> | null = null;

  const statusLabel = computed(() => {
    if (starting.value) return "正在启动连续分析";
    if (running.value) return `正在分析第 ${completedCount.value + failedCount.value + 1} 个关键帧`;
    if (active.value) return `连续分析已启动，已完成 ${completedCount.value} 帧`;
    if (completedCount.value || failedCount.value) {
      return `连续分析已停止，完成 ${completedCount.value} 帧，失败 ${failedCount.value} 帧`;
    }
    return "连续关键帧分析未启动";
  });

  function setIntervalSec(value: number) {
    const normalized = Number(value);
    intervalSec.value = SUPPORTED_INTERVALS.includes(normalized as ContinuousCameraAnalysisIntervalSec)
      ? (normalized as ContinuousCameraAnalysisIntervalSec)
      : 5;
  }

  async function start(): Promise<boolean> {
    if (active.value) return true;
    if (startPromise) return startPromise;
    if (!options.canAnalyze()) return false;
    const task = startOnce();
    startPromise = task;
    try {
      return await task;
    } finally {
      if (startPromise === task) startPromise = null;
    }
  }

  async function startOnce(): Promise<boolean> {
    clearScheduledCycle();
    starting.value = true;
    try {
      await options.beforeStart?.();
      if (!options.canAnalyze()) return false;
      active.value = true;
      completedCount.value = 0;
      failedCount.value = 0;
      lastCompletedAt.value = "";
      sessionId.value = createSessionId();
      options.onMessage?.(
        intervalSec.value === 0 ? "实时分割已启动，将在每帧推理完成后立即继续。" : `实时分割已启动，采样间隔 ${intervalSec.value} 秒。`,
      );
      scheduleNextCycle(0);
      return true;
    } catch (error) {
      options.onMessage?.(
        error instanceof Error ? error.message : "实时分割模型预热失败。",
        "error",
      );
      return false;
    } finally {
      starting.value = false;
    }
  }

  function stop(message = true) {
    const wasActive = active.value;
    active.value = false;
    clearScheduledCycle();
    if (wasActive && message) {
      options.onMessage?.(`实时分割已停止，共完成 ${completedCount.value} 帧。`);
    }
  }

  async function runCycle() {
    timerId = null;
    if (!active.value) return;
    if (!options.canAnalyze()) {
      stop(false);
      options.onMessage?.("连续关键帧分析已停止，请确认病例和摄像头仍处于可用状态。", "error");
      return;
    }
    if (running.value) {
      scheduleNextCycle(500);
      return;
    }

    running.value = true;
    const sequence = completedCount.value + failedCount.value + 1;
    const capturedAt = new Date().toISOString();
    const timestampSec = options.getTimestampSec?.();
    try {
      const blob = await options.captureFrame();
      await options.analyzeFrame(blob, {
        capturedAt,
        sequence,
        sessionId: sessionId.value,
        trigger: "continuous",
        timestampSec: typeof timestampSec === "number" && Number.isFinite(timestampSec) ? timestampSec : undefined,
      });
      completedCount.value += 1;
      lastCompletedAt.value = new Date().toISOString();
    } catch (error) {
      failedCount.value += 1;
      options.onMessage?.(
        error instanceof Error ? error.message : "连续摄像头关键帧分析失败。",
        "error",
      );
      if (isMissingLiveFrameRoute(error)) {
        stop(false);
        options.onMessage?.("实时分割接口未就绪，请通过根目录 start_platform.cmd 重启平台后重试。", "error");
        return;
      }
    } finally {
      running.value = false;
      if (active.value) scheduleNextCycle(intervalSec.value * 1000);
    }
  }

  function scheduleNextCycle(delayMs: number) {
    clearScheduledCycle();
    timerId = window.setTimeout(() => {
      void runCycle();
    }, delayMs);
  }

  function clearScheduledCycle() {
    if (timerId === null) return;
    window.clearTimeout(timerId);
    timerId = null;
  }

  onBeforeUnmount(() => stop(false));

  return {
    active,
    starting,
    running,
    intervalSec,
    completedCount,
    failedCount,
    lastCompletedAt,
    sessionId,
    statusLabel,
    setIntervalSec,
    start,
    stop,
  };
}

function createSessionId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `browser-camera-${crypto.randomUUID()}`;
  }
  return `browser-camera-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function isMissingLiveFrameRoute(error: unknown): boolean {
  return error instanceof Error && error.message.includes("状态码 404");
}
