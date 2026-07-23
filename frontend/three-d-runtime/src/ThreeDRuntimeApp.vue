<template>
  <main class="runtime-shell" :data-theme="theme">
    <header class="runtime-shell__header">
      <div class="runtime-shell__title">
        <span>Osteo Vision</span>
        <h1>独立三维渲染运行时</h1>
        <p>{{ sceneLabel }}</p>
      </div>
      <div class="runtime-shell__actions">
        <label class="runtime-theme-toggle" :title="themeActionLabel">
          <input :checked="theme === 'dark'" type="checkbox" aria-label="夜间主题" @change="toggleTheme" />
          <span>夜间主题</span>
        </label>
        <a :href="platformUrl" target="_top">返回平台</a>
        <button type="button" :disabled="loading" title="重新读取受控三维场景快照" @click="reloadSnapshot">
          {{ loading ? "正在刷新" : "刷新场景" }}
        </button>
      </div>
    </header>

    <section class="runtime-status" :class="`is-${statusTone}`" aria-label="三维运行时安全状态">
      <div>
        <span>空间状态</span>
        <strong>{{ safetyLabel }}</strong>
      </div>
      <div>
        <span>模型状态</span>
        <strong>{{ modelLabel }}</strong>
      </div>
      <div>
        <span>复核状态</span>
        <strong>{{ reviewLabel }}</strong>
      </div>
      <p>{{ boundaryLabel }}</p>
    </section>

    <section class="runtime-workbench">
      <ThreeDViewport
        :snapshot="snapshot"
        :auto-rotate="autoRotate"
        @candidate-selected="selectCandidate"
        @state="handleViewportState"
      />

      <aside class="runtime-inspector" aria-label="三维场景检查">
        <section class="runtime-inspector__section">
          <header>
            <span>场景快照</span>
            <strong>{{ snapshot?.schema_version || "等待快照" }}</strong>
          </header>
          <dl>
            <div><dt>版本</dt><dd>{{ snapshotVersionLabel }}</dd></div>
            <div><dt>模型格式</dt><dd>{{ modelFormatLabel }}</dd></div>
            <div><dt>模型校验</dt><dd>{{ checksumLabel }}</dd></div>
            <div><dt>配准等级</dt><dd>{{ navigationLevelLabel }}</dd></div>
          </dl>
        </section>

        <section class="runtime-inspector__section">
          <header>
            <span>显示控制</span>
            <strong>检查视图</strong>
          </header>
          <label class="runtime-switch">
            <input v-model="autoRotate" type="checkbox" />
            <span>自动旋转</span>
          </label>
          <p class="runtime-inspector__note">{{ viewportMessage }}</p>
        </section>

        <section class="runtime-inspector__section runtime-inspector__candidates">
          <header>
            <span>视频候选区</span>
            <strong>{{ candidates.length }} 个</strong>
          </header>
          <ol v-if="candidates.length">
            <li v-for="candidate in candidates" :key="candidate.candidate_id">
              <button
                type="button"
                :class="{ 'is-selected': selectedCandidateId === candidate.candidate_id }"
                :title="candidateTitle(candidate)"
                @click="selectCandidate(candidateSelection(candidate))"
              >
                <span :class="`is-${candidateTone(candidate)}`"></span>
                <div>
                  <strong>{{ candidate.risk_type || "候选区" }}</strong>
                  <small>{{ candidateFrameLabel(candidate) }}</small>
                </div>
                <em>{{ candidateConfidence(candidate) }}</em>
              </button>
            </li>
          </ol>
          <p v-else class="runtime-inspector__note">当前场景没有可联动的视频候选区。</p>
        </section>

        <section v-if="errorMessage" class="runtime-inspector__error" role="status">
          <strong>运行时状态</strong>
          <span>{{ errorMessage }}</span>
        </section>
      </aside>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import ThreeDViewport from "./components/ThreeDViewport.vue";
import { fetchCaseSnapshot, fetchReferenceSnapshot } from "./services/threeDRuntimeClient";
import type { RuntimeBridgeMessage, RuntimeCandidate, SelectedCandidate, ThreeDRuntimeSnapshot } from "./types";

const BRIDGE_PROTOCOL = "osteo-vision-three-d-runtime-bridge-v1";
const DEFAULT_PARENT_ORIGINS = ["http://127.0.0.1:5174", "http://localhost:5174"];
const THEME_STORAGE_KEY = "osteo-vision-theme";
type ThemeName = "light" | "dark";

const snapshot = ref<ThreeDRuntimeSnapshot | null>(null);
const loading = ref(false);
const autoRotate = ref(false);
const errorMessage = ref("");
const viewportMessage = ref("等待模型加载。");
const selectedCandidateId = ref("");
const verifiedParentOrigin = ref("");
const activeCaseId = ref(queryValue("caseId"));
const activeReferenceId = ref(queryValue("referenceId"));
const activeRequestId = ref("");
const theme = ref<ThemeName>(initialTheme());
let snapshotRequestGeneration = 0;

const candidates = computed(() => snapshot.value?.candidate_regions ?? []);
const parentOrigins = configuredParentOrigins();
const sceneLabel = computed(() => {
  if (activeCaseId.value) return `病例 ${activeCaseId.value} 的受控三维场景`;
  if (activeReferenceId.value) return `公开参考 ${activeReferenceId.value.toUpperCase()} 的只读三维场景`;
  return "等待病例或公开参考场景";
});
const platformUrl = computed(() => {
  const root = verifiedParentOrigin.value || parentOrigins[0] || "http://127.0.0.1:5174";
  const url = new URL(activeReferenceId.value ? "/showcase" : "/navigation", root);
  if (activeCaseId.value) url.searchParams.set("caseId", activeCaseId.value);
  return url.toString();
});
const themeActionLabel = computed(() => (theme.value === "dark" ? "切换到日间主题" : "切换到夜间主题"));
const safetyLabel = computed(() => {
  const safety = snapshot.value?.safety;
  if (!snapshot.value) return "等待场景";
  if (safety?.navigation_ready) return `${safety.navigation_level || "L1"} 工程状态待复核`;
  return `${safety?.navigation_level || "L0"} 参考状态`;
});
const modelLabel = computed(() => {
  const asset = snapshot.value?.model_asset;
  if (!asset) return "未提供模型";
  if (asset.rendering_status === "unsupported_format" || asset.format === "gltf") return "安全降级";
  return viewportMessage.value.startsWith("模型校验完成") ? "已校验加载" : "待检查";
});
const reviewLabel = computed(() => snapshot.value?.safety?.doctor_review_status || "review_required");
const boundaryLabel = computed(
  () => snapshot.value?.safety?.boundary || "三维内容用于工程参考，需保留医生复核边界。",
);
const statusTone = computed(() => {
  if (!snapshot.value) return "neutral";
  if (snapshot.value?.safety?.navigation_ready) return "ready";
  return "guarded";
});
const snapshotVersionLabel = computed(() => {
  if (!snapshot.value) return "未载入";
  return String(snapshot.value.case_version ?? "公开参考");
});
const modelFormatLabel = computed(() => snapshot.value?.model_asset?.format?.toUpperCase() || "未提供");
const checksumLabel = computed(() => {
  const checksum = snapshot.value?.model_asset?.sha256;
  return checksum ? `${checksum.slice(0, 12)}...` : "未提供";
});
const navigationLevelLabel = computed(() => snapshot.value?.safety?.navigation_level || "L0");

onMounted(() => {
  applyTheme(theme.value);
  window.addEventListener("message", handleBridgeMessage);
  if (window.parent === window && (activeCaseId.value || activeReferenceId.value)) void loadSnapshot();
});

onBeforeUnmount(() => {
  snapshotRequestGeneration += 1;
  window.removeEventListener("message", handleBridgeMessage);
});

async function loadSnapshot() {
  const requestGeneration = ++snapshotRequestGeneration;
  const caseId = activeCaseId.value;
  const referenceId = activeReferenceId.value;
  if (!caseId && !referenceId) {
    if (requestGeneration === snapshotRequestGeneration) {
      snapshot.value = null;
      loading.value = false;
    }
    return;
  }
  loading.value = true;
  errorMessage.value = "";
  try {
    const nextSnapshot = caseId ? await fetchCaseSnapshot(caseId) : await fetchReferenceSnapshot(referenceId);
    if (requestGeneration !== snapshotRequestGeneration) return;
    snapshot.value = nextSnapshot;
    notifyParent("scene_loaded", "受控三维场景快照已载入。");
  } catch (error) {
    if (requestGeneration !== snapshotRequestGeneration) return;
    snapshot.value = null;
    errorMessage.value = error instanceof Error ? error.message : "三维场景快照读取失败。";
    notifyParent("scene_failed", errorMessage.value);
  } finally {
    if (requestGeneration === snapshotRequestGeneration) loading.value = false;
  }
}

function reloadSnapshot() {
  void loadSnapshot();
}

function handleBridgeMessage(event: MessageEvent<RuntimeBridgeMessage>) {
  if (!isAllowedParent(event)) return;
  const message = event.data;
  if (message.protocol !== BRIDGE_PROTOCOL || typeof message.type !== "string") return;
  if (message.type === "set_theme" && (message.theme === "light" || message.theme === "dark")) {
    applyTheme(message.theme, { persist: true });
    return;
  }
  const requestId = message.request_id?.trim();
  if (!requestId) return;
  if (message.type === "load_case" && message.case_id) {
    activeRequestId.value = requestId;
    activeCaseId.value = message.case_id;
    activeReferenceId.value = "";
    if (message.theme) applyTheme(message.theme, { persist: true });
    void loadSnapshot();
    return;
  }
  if (message.type === "load_reference" && message.reference_id) {
    activeRequestId.value = requestId;
    activeReferenceId.value = message.reference_id;
    activeCaseId.value = "";
    if (message.theme) applyTheme(message.theme, { persist: true });
    void loadSnapshot();
  }
}

function isAllowedParent(event: MessageEvent<RuntimeBridgeMessage>): boolean {
  if (window.parent === window || event.source !== window.parent) return false;
  if (!parentOrigins.includes(event.origin)) return false;
  verifiedParentOrigin.value = event.origin;
  return true;
}

function notifyParent(type: string, message: string, candidate?: SelectedCandidate) {
  if (window.parent === window) return;
  const targetOrigin = verifiedParentOrigin.value;
  if (!targetOrigin) return;
  window.parent.postMessage(
    {
      protocol: BRIDGE_PROTOCOL,
      type,
      request_id: activeRequestId.value || undefined,
      message,
      ...(candidate ? { candidate } : {}),
    },
    targetOrigin,
  );
}

function handleViewportState(payload: { state: string; message: string }) {
  viewportMessage.value = payload.message;
  if (payload.state === "failed") {
    errorMessage.value = payload.message;
    notifyParent("runtime_failed", payload.message);
  }
}

function selectCandidate(candidate: SelectedCandidate) {
  selectedCandidateId.value = candidate.candidate_id;
  notifyParent("candidate_selected", "已选择视频候选区。", candidate);
}

function candidateSelection(candidate: RuntimeCandidate): SelectedCandidate {
  return {
    candidate_id: candidate.candidate_id,
    frame_key: String(candidate.frame_key ?? ""),
    frame_index: finiteNumber(candidate.frame_index),
    timestamp_sec: finiteNumber(candidate.timestamp_sec),
  };
}

function candidateFrameLabel(candidate: RuntimeCandidate): string {
  const selection = candidateSelection(candidate);
  if (selection.timestamp_sec !== null) return `${selection.timestamp_sec.toFixed(2)} s`;
  if (selection.frame_index !== null) return `帧 ${selection.frame_index}`;
  return "帧信息待补充";
}

function candidateConfidence(candidate: RuntimeCandidate): string {
  const value = candidate.confidence ?? candidate.score;
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(2) : "待复核";
}

function candidateTone(candidate: RuntimeCandidate): "high" | "medium" | "low" {
  const value = String(candidate.risk_type || "").toLowerCase();
  if (value.includes("high") || value.includes("risk")) return "high";
  if (value.includes("boundary") || value.includes("uncertain")) return "medium";
  return "low";
}

function candidateTitle(candidate: RuntimeCandidate): string {
  return `${candidate.risk_type || "候选区"}，${candidateFrameLabel(candidate)}`;
}

function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function queryValue(name: string): string {
  return new URLSearchParams(window.location.search).get(name)?.trim() || "";
}

function configuredParentOrigins(): string[] {
  const configured = import.meta.env.VITE_OSTEO_MAIN_APP_ORIGIN?.trim();
  const values: string[] = configured ? configured.split(",") : DEFAULT_PARENT_ORIGINS;
  return values.map((value: string) => value.trim()).filter((value: string) => /^https?:\/\//.test(value));
}

function toggleTheme() {
  applyTheme(theme.value === "dark" ? "light" : "dark", { persist: true });
}

function initialTheme(): ThemeName {
  const storedTheme = readStoredTheme();
  if (storedTheme) return storedTheme;
  if (typeof document !== "undefined" && document.documentElement.dataset.theme === "dark") return "dark";
  if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return "light";
}

function readStoredTheme(): ThemeName | null {
  try {
    const value = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (value === "light" || value === "dark") return value;
    if (value !== null) window.localStorage.removeItem(THEME_STORAGE_KEY);
  } catch {
    // Browser storage can be unavailable in a constrained runtime window.
  }
  return null;
}

function applyTheme(nextTheme: ThemeName, { persist = false }: { persist?: boolean } = {}) {
  theme.value = nextTheme;
  document.documentElement.dataset.theme = nextTheme;
  document.documentElement.style.colorScheme = nextTheme;
  if (persist) {
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
    } catch {
      // Keep the selected theme for this runtime window when storage is unavailable.
    }
  }
}
</script>
