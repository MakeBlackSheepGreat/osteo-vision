<template>
  <section class="three-d-runtime-embed" :data-state="runtimeState" aria-label="独立三维渲染运行时">
    <header class="three-d-runtime-embed__header">
      <div>
        <span>独立渲染运行时</span>
        <strong>{{ runtimeTitle }}</strong>
        <small>{{ runtimeMessage }}</small>
      </div>
      <div class="three-d-runtime-embed__actions">
        <a :href="runtimeUrl" target="_blank" rel="noopener noreferrer">独立窗口</a>
        <button type="button" title="重新建立与独立三维渲染运行时的连接" @click="reloadRuntime">重新连接</button>
      </div>
    </header>

    <div class="three-d-runtime-embed__viewport" :class="{ 'is-degraded': runtimeState === 'degraded' }">
      <iframe
        v-if="hasSceneRequest"
        :key="runtimeKey"
        ref="runtimeFrame"
        class="three-d-runtime-embed__frame"
        :src="embeddedRuntimeUrl"
        title="独立三维渲染工作区"
        @load="handleFrameLoad"
        @error="markRuntimeUnavailable('运行时页面未能载入')"
      ></iframe>
      <div v-else class="three-d-runtime-embed__empty" role="status">
        <strong>等待可渲染的三维证据</strong>
        <p>载入病例或选择公开参考后，独立运行时会读取受控场景快照。</p>
      </div>
      <div
        v-if="runtimeState !== 'ready' && hasSceneRequest"
        class="three-d-runtime-embed__state"
        data-testid="three-d-runtime-status"
        role="status"
        aria-live="polite"
      >
        <strong>{{ runtimeTitle }}</strong>
        <span>{{ runtimeMessage }}</span>
      </div>
    </div>

    <p v-if="runtimeState === 'degraded'" class="three-d-runtime-embed__fallback" role="status">
      三维渲染未就绪。当前页面仍保留病例安全状态、二维证据、L1/L2 工程记录和医生复核入口。
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

type RuntimeState = "connecting" | "ready" | "degraded";
type RuntimeRequestType = "load_case" | "load_reference";

interface Props {
  caseId?: string;
  referenceId?: string;
  sceneVersion?: number | string;
}

interface RuntimeMessage {
  protocol?: string;
  type?: string;
  request_id?: string;
  candidate?: {
    candidate_id?: string;
    frame_key?: string;
    frame_index?: number | null;
    timestamp_sec?: number | null;
  };
  message?: string;
}

const props = withDefaults(defineProps<Props>(), {
  caseId: "",
  referenceId: "",
  sceneVersion: 0,
});

const emit = defineEmits<{
  selectCandidateFrame: [payload: { candidateId: string; frameKey: string; frameIndex: number | null; timestampSec: number | null }];
}>();

const BRIDGE_PROTOCOL = "osteo-vision-three-d-runtime-bridge-v1";
const RUNTIME_TIMEOUT_MS = 10000;
const RUNTIME_RETRY_INTERVAL_MS = 700;

const runtimeFrame = ref<HTMLIFrameElement | null>(null);
const runtimeState = ref<RuntimeState>("connecting");
const runtimeMessage = ref("正在连接独立三维运行时。");
const runtimeKey = ref(0);
const activeRequestId = ref("");
let timeoutId: number | null = null;
let retryId: number | null = null;
let themeObserver: MutationObserver | null = null;

const hasSceneRequest = computed(() => Boolean(props.caseId || props.referenceId));
const runtimeBaseUrl = computed(
  () => import.meta.env.VITE_OSTEO_THREE_D_RUNTIME_URL?.trim() || "http://127.0.0.1:5175",
);
const runtimeUrl = computed(() => {
  try {
    const url = new URL(runtimeBaseUrl.value, window.location.origin);
    if (props.caseId) url.searchParams.set("caseId", props.caseId);
    if (props.referenceId) url.searchParams.set("referenceId", props.referenceId);
    url.searchParams.set("runtimeInstance", String(runtimeKey.value));
    return url.toString();
  } catch {
    return runtimeBaseUrl.value;
  }
});
const embeddedRuntimeUrl = computed(() => {
  try {
    const url = new URL(runtimeUrl.value, window.location.origin);
    url.searchParams.set("embedded", "1");
    return url.toString();
  } catch {
    return runtimeUrl.value;
  }
});
const runtimeOrigin = computed(() => {
  try {
    return new URL(runtimeUrl.value, window.location.origin).origin;
  } catch {
    return "";
  }
});
const runtimeTitle = computed(() => {
  if (runtimeState.value === "ready") return "三维运行时已就绪";
  if (runtimeState.value === "degraded") return "三维运行时已降级";
  return "正在建立三维渲染会话";
});

watch(
  () => [props.caseId, props.referenceId, props.sceneVersion],
  () => {
    if (!hasSceneRequest.value) {
      clearRuntimeTimeout();
      clearRuntimeRetry();
      activeRequestId.value = "";
      runtimeState.value = "connecting";
      runtimeMessage.value = "等待病例或公开参考场景。";
      return;
    }
    recreateRuntime("正在读取受控三维场景快照。");
  },
);

onMounted(() => {
  window.addEventListener("message", handleRuntimeMessage);
  observeTheme();
  if (hasSceneRequest.value) {
    activeRequestId.value = requestId();
    scheduleRuntimeTimeout();
    scheduleRuntimeRetry();
  }
});

onBeforeUnmount(() => {
  window.removeEventListener("message", handleRuntimeMessage);
  clearRuntimeTimeout();
  clearRuntimeRetry();
  themeObserver?.disconnect();
});

function handleFrameLoad() {
  if (!hasSceneRequest.value) return;
  runtimeState.value = "connecting";
  runtimeMessage.value = "渲染运行时页面已载入，正在等待会话确认。";
  postSceneRequest();
  scheduleRuntimeRetry();
}

function reloadRuntime() {
  if (!hasSceneRequest.value) return;
  recreateRuntime("正在重新建立独立三维运行时。");
}

function postSceneRequest() {
  const target = runtimeFrame.value?.contentWindow;
  const requestType = sceneRequestType();
  if (!target || !requestType || !runtimeOrigin.value) return;
  if (!activeRequestId.value) activeRequestId.value = requestId();
  target.postMessage(
    {
      protocol: BRIDGE_PROTOCOL,
      type: requestType,
      request_id: activeRequestId.value,
      case_id: props.caseId || undefined,
      reference_id: props.referenceId || undefined,
      theme: currentTheme(),
    },
    runtimeOrigin.value,
  );
}

function postTheme() {
  const target = runtimeFrame.value?.contentWindow;
  if (!target || !runtimeOrigin.value) return;
  target.postMessage(
    {
      protocol: BRIDGE_PROTOCOL,
      type: "set_theme",
      theme: currentTheme(),
    },
    runtimeOrigin.value,
  );
}

function handleRuntimeMessage(event: MessageEvent<RuntimeMessage>) {
  if (event.origin !== runtimeOrigin.value || event.source !== runtimeFrame.value?.contentWindow) return;
  const message = event.data;
  if (message?.protocol !== BRIDGE_PROTOCOL || typeof message.type !== "string") return;
  if (message.type === "runtime_ready") {
    postSceneRequest();
    return;
  }
  if (message.request_id !== activeRequestId.value) return;
  if (message.type === "scene_loaded") {
    clearRuntimeTimeout();
    clearRuntimeRetry();
    runtimeState.value = "ready";
    runtimeMessage.value = message.message || "受控场景快照已载入。";
    return;
  }
  if (message.type === "scene_failed" || message.type === "runtime_failed") {
    markRuntimeUnavailable(message.message || "独立三维运行时无法载入场景。");
    return;
  }
  if (message.type === "candidate_selected" && message.candidate?.candidate_id) {
    emit("selectCandidateFrame", {
      candidateId: message.candidate.candidate_id,
      frameKey: message.candidate.frame_key || "",
      frameIndex: numberOrNull(message.candidate.frame_index),
      timestampSec: numberOrNull(message.candidate.timestamp_sec),
    });
  }
}

function markRuntimeUnavailable(message: string) {
  clearRuntimeTimeout();
  clearRuntimeRetry();
  runtimeState.value = "degraded";
  runtimeMessage.value = message;
}

function scheduleRuntimeTimeout() {
  clearRuntimeTimeout();
  timeoutId = window.setTimeout(() => {
    if (runtimeState.value !== "ready") {
      markRuntimeUnavailable("独立三维运行时未在限定时间内确认场景。请在独立窗口检查运行时状态。");
    }
  }, RUNTIME_TIMEOUT_MS);
}

function clearRuntimeTimeout() {
  if (timeoutId !== null) window.clearTimeout(timeoutId);
  timeoutId = null;
}

function scheduleRuntimeRetry() {
  clearRuntimeRetry();
  retryId = window.setInterval(() => {
    if (!hasSceneRequest.value || runtimeState.value !== "connecting") {
      clearRuntimeRetry();
      return;
    }
    postSceneRequest();
  }, RUNTIME_RETRY_INTERVAL_MS);
}

function clearRuntimeRetry() {
  if (retryId !== null) window.clearInterval(retryId);
  retryId = null;
}

function sceneRequestType(): RuntimeRequestType | null {
  if (props.caseId) return "load_case";
  if (props.referenceId) return "load_reference";
  return null;
}

function requestId(): string {
  return `${props.caseId || props.referenceId}-${runtimeKey.value}`;
}

function recreateRuntime(message: string) {
  clearRuntimeTimeout();
  clearRuntimeRetry();
  runtimeKey.value += 1;
  activeRequestId.value = requestId();
  runtimeState.value = "connecting";
  runtimeMessage.value = message;
  scheduleRuntimeTimeout();
  scheduleRuntimeRetry();
}

function currentTheme(): "light" | "dark" {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

function observeTheme() {
  themeObserver = new MutationObserver(() => postTheme());
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
}

function numberOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
</script>

<style scoped>
.three-d-runtime-embed {
  --three-d-viewer-height: clamp(520px, 62vh, 680px);
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  min-height: calc(var(--three-d-viewer-height) + 74px);
  overflow: hidden;
  border: 1px solid var(--ov-border);
  border-radius: 7px;
  background: var(--ov-bg-panel);
  box-shadow: var(--ov-shadow-card);
}

.three-d-runtime-embed__header {
  display: flex;
  gap: 16px;
  align-items: center;
  justify-content: space-between;
  min-height: 74px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--ov-border);
}

.three-d-runtime-embed__header > div:first-child {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.three-d-runtime-embed__header span,
.three-d-runtime-embed__header small {
  color: var(--ov-text-muted);
  font-size: 12px;
  line-height: 1.45;
}

.three-d-runtime-embed__header strong {
  color: var(--ov-text);
  font-size: 16px;
  line-height: 1.35;
}

.three-d-runtime-embed__actions {
  display: flex;
  flex: 0 0 auto;
  gap: 8px;
  align-items: center;
}

.three-d-runtime-embed__actions a,
.three-d-runtime-embed__actions button {
  border: 1px solid var(--ov-border-strong);
  border-radius: 5px;
  padding: 7px 10px;
  color: var(--ov-text);
  background: var(--ov-bg-elevated);
  font: inherit;
  font-size: 13px;
  line-height: 1.25;
  text-decoration: none;
  cursor: pointer;
}

.three-d-runtime-embed__actions a:hover,
.three-d-runtime-embed__actions a:focus-visible,
.three-d-runtime-embed__actions button:hover,
.three-d-runtime-embed__actions button:focus-visible {
  border-color: var(--ov-accent);
  outline: none;
}

.three-d-runtime-embed__viewport {
  position: relative;
  height: 100%;
  min-height: var(--three-d-viewer-height);
  background-color: var(--ov-bg-subtle);
  background-image:
    linear-gradient(var(--ov-grid-line) 1px, transparent 1px),
    linear-gradient(90deg, var(--ov-grid-line) 1px, transparent 1px);
  background-size: 28px 28px;
}

.three-d-runtime-embed__frame {
  display: block;
  width: 100%;
  height: 100%;
  min-height: var(--three-d-viewer-height);
  border: 0;
  background: transparent;
}

.three-d-runtime-embed__state,
.three-d-runtime-embed__empty {
  display: grid;
  gap: 8px;
  padding: 28px;
  color: var(--ov-text-muted);
  text-align: center;
}

.three-d-runtime-embed__state {
  position: absolute;
  right: 16px;
  bottom: 16px;
  left: 16px;
  min-height: 0;
  border: 1px solid var(--ov-border-strong);
  border-left: 3px solid var(--ov-primary);
  padding: 10px 12px;
  background: color-mix(in srgb, var(--ov-bg-elevated) 92%, transparent);
  box-shadow: var(--ov-shadow);
  pointer-events: none;
}

.three-d-runtime-embed[data-state="connecting"] .three-d-runtime-embed__state {
  top: 50%;
  right: auto;
  bottom: auto;
  left: 50%;
  width: min(440px, calc(100% - 48px));
  transform: translate(-50%, -50%);
}

.three-d-runtime-embed__viewport.is-degraded .three-d-runtime-embed__state {
  inset: 0;
  place-content: center;
  min-height: var(--three-d-viewer-height);
  border: 0;
  padding: 28px;
  background: color-mix(in srgb, var(--ov-bg-subtle) 87%, transparent);
}

.three-d-runtime-embed__empty {
  place-content: center;
  height: 100%;
  min-height: var(--three-d-viewer-height);
}

.three-d-runtime-embed__state strong,
.three-d-runtime-embed__empty strong {
  color: var(--ov-text);
  font-size: 17px;
}

.three-d-runtime-embed__empty p {
  max-width: 440px;
  margin: 0;
  line-height: 1.65;
}

.three-d-runtime-embed__fallback {
  margin: 0;
  padding: 12px 18px;
  border-top: 1px solid var(--ov-border);
  color: var(--ov-warning-text);
  background: var(--ov-warning-bg);
  font-size: 13px;
  line-height: 1.55;
}

</style>
