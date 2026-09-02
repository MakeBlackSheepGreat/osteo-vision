import { computed, onBeforeUnmount, ref } from "vue";

export type ContinuousCameraAnalysisIntervalSec = 0 | 1 | 2 | 3 | 5 | 10;

export interface ContinuousCameraAnalysisOptions {
  captureFrame: () => Promise<Blob>;
  analyzeFrame: (blob: Blob, context: ContinuousCameraFrameContext) => Promise<void>;
  canAnalyze: () => boolean;
  getTimestampSec?: () => number | undefined;
  beforeStart?: () => Promise<void>;
  requestTimeoutMs?: number;
  onFrameInvalidated?: (
    reason: ContinuousCameraFrameInvalidationReason,
    context?: ContinuousCameraFrameContext,
  ) => void;
  onMessage?: (message: string, type?: "info" | "error") => void;
}

export type ContinuousCameraFrameInvalidationReason =
  | "new_frame"
  | "failed"
  | "timed_out"
  | "stopped";

export interface ContinuousCameraFrameContext {
  capturedAt: string;
  sequence: number;
  sessionId: string;
  signal: AbortSignal;
  trigger: "continuous";
  timestampSec?: number;
}

export interface LiveFrameDisplayIdentity {
  source: "camera" | "video";
  sequence: number;
  sessionId: string;
  capturedAt: string;
  capturedAtMs: number;
  requestGeneration: number;
}

export interface LiveFrameDisplayResultIdentity {
  case_id: string;
  captured_at: string;
}

export function resolveLiveFrameDisplaySource(options: {
  inputSource: "file" | "camera";
  cameraActive: boolean;
  fileVideoActive: boolean;
  multichannelModeActive: boolean;
  multichannelRealtimeEnabled: boolean;
}): "camera" | "video" | "" {
  if (options.inputSource === "camera" && options.cameraActive) return "camera";
  if (
    options.inputSource === "file"
    && (options.fileVideoActive || (options.multichannelModeActive && options.multichannelRealtimeEnabled))
  ) {
    return "video";
  }
  return "";
}

export function isCurrentLiveFrameDisplay(
  result: LiveFrameDisplayResultIdentity | null,
  display: LiveFrameDisplayIdentity | null,
  expected: LiveFrameDisplayIdentity | null,
  options: {
    activeSource: "camera" | "video" | "";
    caseId: string;
    requestGeneration: number;
    nowMs: number;
    maxAgeMs: number;
  },
): boolean {
  if (!result || !display || !expected) return false;
  const ageMs = options.nowMs - display.capturedAtMs;
  return (
    display.requestGeneration === options.requestGeneration &&
    display.requestGeneration === expected.requestGeneration &&
    display.source === options.activeSource &&
    display.source === expected.source &&
    display.sequence === expected.sequence &&
    display.sessionId === expected.sessionId &&
    display.capturedAt === expected.capturedAt &&
    ageMs >= 0 &&
    ageMs <= options.maxAgeMs &&
    result.case_id === options.caseId &&
    result.captured_at === display.capturedAt
  );
}

export function isDisplayableLiveFrame(
  result: LiveFrameDisplayResultIdentity | null,
  display: LiveFrameDisplayIdentity | null,
  options: {
    activeSource: "camera" | "video" | "";
    caseId: string;
    nowMs: number;
    maxAgeMs: number;
  },
): boolean {
  if (!result || !display) return false;
  const ageMs = options.nowMs - display.capturedAtMs;
  return (
    display.source === options.activeSource &&
    ageMs >= 0 &&
    ageMs <= options.maxAgeMs &&
    result.case_id === options.caseId &&
    result.captured_at === display.capturedAt
  );
}

const SUPPORTED_INTERVALS = [0, 1, 2, 3, 5, 10] as const;
const DEFAULT_REQUEST_TIMEOUT_MS = 12_000;
const MIN_REQUEST_TIMEOUT_MS = 250;
const MAX_REQUEST_TIMEOUT_MS = 120_000;
const MIN_RETRY_DELAY_MS = 500;
const MAX_RETRY_DELAY_MS = 10_000;

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
  let runGeneration = 0;
  let activeRequest: AbortController | null = null;
  let disposed = false;
  let consecutiveFailures = 0;

  const statusLabel = computed(() => {
    if (starting.value) return "正在启动连续分析";
    if (running.value) return `正在分析第 ${completedCount.value + failedCount.value + 1} 帧`;
    if (active.value) return `连续分析已启动，已完成 ${completedCount.value} 帧`;
    if (completedCount.value || failedCount.value) {
      return `连续分析已停止，完成 ${completedCount.value} 帧，失败 ${failedCount.value} 帧`;
    }
    return "逐帧连续分析未启动";
  });

  function setIntervalSec(value: number) {
    const normalized = Number(value);
    intervalSec.value = SUPPORTED_INTERVALS.includes(normalized as ContinuousCameraAnalysisIntervalSec)
      ? (normalized as ContinuousCameraAnalysisIntervalSec)
      : 5;
  }

  async function start(): Promise<boolean> {
    if (disposed) return false;
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
    const generation = ++runGeneration;
    clearScheduledCycle();
    starting.value = true;
    try {
      await options.beforeStart?.();
      if (disposed || generation !== runGeneration || !options.canAnalyze()) return false;
      active.value = true;
      completedCount.value = 0;
      failedCount.value = 0;
      lastCompletedAt.value = "";
      sessionId.value = createSessionId();
      consecutiveFailures = 0;
      options.onMessage?.(
        intervalSec.value === 0 ? "实时分割已启动，将在每帧推理完成后立即继续。" : `实时分割已启动，采样间隔 ${intervalSec.value} 秒。`,
      );
      scheduleNextCycle(0, generation);
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
    const wasActive = active.value || starting.value || running.value || Boolean(activeRequest);
    active.value = false;
    runGeneration += 1;
    clearScheduledCycle();
    activeRequest?.abort();
    activeRequest = null;
    if (wasActive) notifyFrameInvalidated("stopped");
    if (wasActive && message) {
      options.onMessage?.(`实时分割已停止，共完成 ${completedCount.value} 帧。`);
    }
  }

  async function runCycle(generation: number) {
    timerId = null;
    if (!active.value || disposed || generation !== runGeneration) return;
    if (!options.canAnalyze()) {
      stop(false);
      options.onMessage?.("逐帧连续分析已停止，请确认输入源仍处于可用状态。", "error");
      return;
    }
    if (running.value) {
      scheduleNextCycle(500, generation);
      return;
    }

    running.value = true;
    const request = new AbortController();
    activeRequest = request;
    const sequence = completedCount.value + failedCount.value + 1;
    const capturedAt = new Date().toISOString();
    const timestampSec = options.getTimestampSec?.();
    const context: ContinuousCameraFrameContext = {
      capturedAt,
      sequence,
      sessionId: sessionId.value,
      signal: request.signal,
      trigger: "continuous",
      timestampSec: typeof timestampSec === "number" && Number.isFinite(timestampSec) ? timestampSec : undefined,
    };
    const requestTimeoutMs = normalizedRequestTimeout(options.requestTimeoutMs);
    let timedOut = false;
    let nextDelayMs = intervalSec.value * 1000;
    const timeoutId = window.setTimeout(() => {
      timedOut = true;
      request.abort();
    }, requestTimeoutMs);
    try {
      notifyFrameInvalidated("new_frame", context);
      const blob = await options.captureFrame();
      if (timedOut) throw timeoutError(requestTimeoutMs);
      if (!active.value || disposed || generation !== runGeneration || request.signal.aborted) return;
      await options.analyzeFrame(blob, context);
      if (timedOut) throw timeoutError(requestTimeoutMs);
      if (!active.value || disposed || generation !== runGeneration || request.signal.aborted) return;
      completedCount.value += 1;
      lastCompletedAt.value = new Date().toISOString();
      consecutiveFailures = 0;
    } catch (error) {
      if (disposed || generation !== runGeneration) return;
      if (timedOut) {
        failedCount.value += 1;
        consecutiveFailures += 1;
        nextDelayMs = retryDelayMs(error, consecutiveFailures, intervalSec.value * 1000);
        notifyFrameInvalidated("timed_out", context);
        options.onMessage?.(
          `实时分割请求超过 ${formatDelay(requestTimeoutMs)}，已取消；将在 ${formatDelay(nextDelayMs)}后重试。`,
          "info",
        );
        return;
      }
      if (request.signal.aborted || isAbortError(error)) return;
      failedCount.value += 1;
      consecutiveFailures += 1;
      nextDelayMs = retryDelayMs(error, consecutiveFailures, intervalSec.value * 1000);
      notifyFrameInvalidated("failed", context);
      if (isMissingLiveFrameRoute(error)) {
        stop(false);
        options.onMessage?.("实时分割接口未就绪，请通过根目录 start_platform.cmd 重启平台后重试。", "error");
        return;
      }
      const errorText = continuousAnalysisErrorText(error);
      options.onMessage?.(
        `${errorText}；将在 ${formatDelay(nextDelayMs)}后重试。`,
        isServiceBusyError(error) ? "info" : "error",
      );
    } finally {
      window.clearTimeout(timeoutId);
      if (activeRequest === request) activeRequest = null;
      running.value = false;
      if (active.value && !disposed && generation === runGeneration) {
        scheduleNextCycle(nextDelayMs, generation);
      }
    }
  }

  function scheduleNextCycle(delayMs: number, generation: number) {
    clearScheduledCycle();
    timerId = window.setTimeout(() => {
      void runCycle(generation);
    }, delayMs);
  }

  function clearScheduledCycle() {
    if (timerId === null) return;
    window.clearTimeout(timerId);
    timerId = null;
  }

  function notifyFrameInvalidated(
    reason: ContinuousCameraFrameInvalidationReason,
    context?: ContinuousCameraFrameContext,
  ) {
    try {
      options.onFrameInvalidated?.(reason, context);
    } catch {
      // 展示状态回调异常不能破坏串行推理、取消和退避控制。
    }
  }

  onBeforeUnmount(() => {
    disposed = true;
    stop(false);
  });

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

function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === "AbortError";
}

function normalizedRequestTimeout(value: number | undefined): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return DEFAULT_REQUEST_TIMEOUT_MS;
  return Math.min(MAX_REQUEST_TIMEOUT_MS, Math.max(MIN_REQUEST_TIMEOUT_MS, Math.round(value)));
}

function retryDelayMs(error: unknown, consecutiveFailures: number, configuredIntervalMs: number): number {
  const exponentialDelay = Math.min(
    MAX_RETRY_DELAY_MS,
    MIN_RETRY_DELAY_MS * 2 ** Math.min(8, Math.max(0, consecutiveFailures - 1)),
  );
  const retryAfter = retryAfterDelayMs(error);
  const serviceDelay = isServiceBusyError(error) && retryAfter !== null
    ? Math.min(MAX_RETRY_DELAY_MS, Math.max(MIN_RETRY_DELAY_MS, retryAfter))
    : exponentialDelay;
  return Math.max(configuredIntervalMs, serviceDelay);
}

function retryAfterDelayMs(error: unknown): number | null {
  if (!error || typeof error !== "object" || !("retryAfterMs" in error)) return null;
  const rawValue = (error as { retryAfterMs?: unknown }).retryAfterMs;
  if (rawValue === null || rawValue === undefined || rawValue === "") return null;
  const value = Number(rawValue);
  return Number.isFinite(value) && value >= 0 ? value : null;
}

function isServiceBusyError(error: unknown): boolean {
  if (!error || typeof error !== "object" || !("status" in error)) return false;
  const status = Number((error as { status?: unknown }).status);
  return status === 429 || status === 503;
}

function continuousAnalysisErrorText(error: unknown): string {
  if (error && typeof error === "object" && "status" in error) {
    const status = Number((error as { status?: unknown }).status);
    if (status === 429) return "实时分割请求过多，服务正在限流";
    if (status === 503) return "实时分割服务繁忙或暂时不可用";
  }
  return error instanceof Error ? error.message : "逐帧连续分析失败。";
}

function timeoutError(timeoutMs: number): Error {
  const error = new Error(`实时分割请求超过 ${formatDelay(timeoutMs)}。`);
  error.name = "TimeoutError";
  return error;
}

function formatDelay(delayMs: number): string {
  const seconds = delayMs / 1000;
  return `${Number.isInteger(seconds) ? seconds.toFixed(0) : seconds.toFixed(1)} 秒`;
}
