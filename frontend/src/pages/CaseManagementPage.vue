<template>
  <AppPageShell class="case-management-shell" width="standard">
    <AppPageHeader
      eyebrow="病例工作流"
      icon="case"
      icon-tone="blue"
      title="病例建立、加载与基础质控"
      class="management-header"
    >
      <template #actions>
        <RouterLink class="intake-link" to="/intake">
          <AppIcon name="upload" />
          <span>医院数据准入</span>
        </RouterLink>
      </template>
    </AppPageHeader>

    <section class="management-grid">
      <section class="management-card">
        <SectionHeading icon="case" title="病例 / 建立与加载" />
        <label class="field">
          <span>全部病例（{{ cases.length }}）</span>
          <select v-model="selectedCaseId" :disabled="loadingCatalog || store.loading">
            <option v-for="item in cases" :key="item.case_id" :value="item.case_id">
              {{ item.title }} · {{ caseStatusLabel(item.status) }}
            </option>
          </select>
        </label>
        <AppButton
          variant="secondary"
          icon="load"
          block
          :disabled="loadingCatalog || store.loading || !selectedCaseId"
          :title="store.loading ? '病例请求处理中，请稍候' : '加载选中的病例'"
          @click="loadSelectedCase"
        >
          加载病例
        </AppButton>
        <details class="create-case">
          <summary>新建病例</summary>
          <label class="field">
            <span>病例标题</span>
            <input v-model="caseTitle" type="text" placeholder="请输入病例标题" :disabled="store.loading" />
          </label>
          <AppButton
            variant="primary"
            icon="plus"
            block
            :disabled="store.loading"
            :title="store.loading ? '病例请求处理中，请稍候' : '建立新的病例记录'"
            @click="createCase"
          >
            新建病例
          </AppButton>
        </details>
        <p v-if="operationMessage" class="operation-message" :class="{ error: operationMessageType === 'error' }">
          {{ operationMessage }}
        </p>
      </section>

      <section class="management-card current-case-card">
        <SectionHeading icon="clipboard" icon-tone="cyan" title="当前病例" />
        <h2>{{ displayCaseTitle }}</h2>
        <dl class="case-summary">
          <div>
            <dt>病例 ID</dt>
            <dd>{{ displayCaseId }}</dd>
          </div>
          <div>
            <dt>病例状态</dt>
            <dd>{{ currentStatusLabel }}</dd>
          </div>
          <div>
            <dt>病例版本</dt>
            <dd>{{ displayCaseVersion }}</dd>
          </div>
          <div>
            <dt>复核版本</dt>
            <dd>{{ disclaimerVersionLabel(store.currentCase?.disclaimer_version) }}</dd>
          </div>
          <div>
            <dt>最近运行</dt>
            <dd>{{ displayRunId }}</dd>
          </div>
        </dl>
      </section>

      <section class="management-card">
        <SectionHeading icon="layers" icon-tone="cyan" title="输入清单 / 通道记录" />
        <ul class="asset-stack">
          <li v-for="asset in inputRows" :key="asset.id">
            <AppIcon class="file-icon" name="file" variant="tile" tone="cyan" />
            <div>
              <strong>{{ asset.channel }}</strong>
              <p>{{ asset.name }}</p>
              <small>{{ asset.meta }}</small>
            </div>
          </li>
        </ul>
        <p v-if="!inputRows.length" class="compact-state">当前病例暂无输入素材</p>
        <p v-else-if="inputCount > inputRows.length" class="compact-state">另有 {{ inputCount - inputRows.length }} 项输入素材</p>
      </section>

      <section class="management-card">
        <SectionHeading icon="check" icon-tone="green" title="质控 / 运行提示" />
        <ul v-if="warningRows.length" class="warning-stack">
          <li v-for="warning in warningRows" :key="warning.key" :class="{ blocking: warning.blocking }">
            <AppIcon
              class="qc-icon"
              :name="warning.blocking ? 'alert' : 'check'"
              variant="badge"
              :tone="warning.blocking ? 'red' : 'green'"
            />
            <div>
              <strong>{{ warning.code }}</strong>
              <p>{{ warning.message }}</p>
            </div>
          </li>
        </ul>
        <div v-else class="qc-empty">
          <AppIcon class="qc-icon" name="check" variant="badge" tone="green" />
          <p>暂无阻断性提示</p>
        </div>
        <p v-if="warningCount > warningRows.length" class="compact-state">另有 {{ warningCount - warningRows.length }} 条提示</p>
      </section>
    </section>
  </AppPageShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import AppButton from "@/components/AppButton.vue";
import AppIcon from "@/components/AppIcon.vue";
import AppPageHeader from "@/components/AppPageHeader.vue";
import AppPageShell from "@/components/AppPageShell.vue";
import SectionHeading from "@/components/SectionHeading.vue";
import { useOperationMessage } from "@/composables/useOperationMessage";
import { apiClient } from "@/services/apiClient";
import { useCaseStore } from "@/stores/caseStore";
import type { CaseInputAsset, CaseRecord } from "@/types/case";
import {
  caseStatusLabel,
  disclaimerVersionLabel,
  inputChannelLabel,
  normalizeWarning,
} from "@/utils/caseDisplay";

const store = useCaseStore();
const cases = ref<CaseRecord[]>([]);
const selectedCaseId = ref("");
const caseTitle = ref("");
const loadingCatalog = ref(false);
const { operationMessage, operationMessageType, setOperationMessage } = useOperationMessage();

const latestRun = computed(() => store.currentCase?.analysis_runs.at(-1) ?? null);
const currentStatusLabel = computed(() => caseStatusLabel(store.currentCase?.status));
const displayCaseTitle = computed(() => store.currentCase?.title ?? "正在加载病例");
const displayCaseId = computed(() => store.currentCase?.case_id ?? "--");
const displayCaseVersion = computed(() => (store.currentCase ? `v${store.currentCase.version}` : "--"));
const displayRunId = computed(() => latestRun.value?.run_id ?? "暂无运行记录");
const inputCount = computed(() => store.currentCase?.inputs.length ?? 0);

const inputRows = computed(() =>
  (store.currentCase?.inputs ?? []).slice(0, 3).map((asset) => ({
    id: asset.input_id,
    channel: inputChannelLabel(asset.channel),
    name: inputDisplayName(asset),
    meta: inputDisplayMeta(asset),
  })),
);

const allWarnings = computed(() => {
  const caseWarnings = store.currentCase?.warnings ?? [];
  const caseQualityFlags = store.currentCase?.quality_flags ?? [];
  const runWarnings = latestRun.value?.warnings ?? [];
  const inputWarnings = (store.currentCase?.inputs ?? []).flatMap((asset) => asset.quality_flags ?? []);
  return [...caseWarnings, ...caseQualityFlags, ...runWarnings, ...inputWarnings].map((warning, index) =>
    normalizeWarning(warning, index),
  );
});
const warningRows = computed(() => allWarnings.value.slice(0, 3));
const warningCount = computed(() => allWarnings.value.length);

onMounted(() => {
  void initializeCatalog();
});

async function initializeCatalog() {
  if (loadingCatalog.value) return;
  loadingCatalog.value = true;
  try {
    const demoCatalog = await apiClient.ensureDemoCases();
    const listedCases = await apiClient.listCases();
    cases.value = orderCases(demoCatalog, listedCases);
    const preferredCaseId = store.currentCase?.case_id || selectedCaseId.value || cases.value[0]?.case_id;
    if (preferredCaseId && cases.value.some((item) => item.case_id === preferredCaseId)) {
      selectedCaseId.value = preferredCaseId;
      await loadSelectedCase(false);
    }
  } catch (error) {
    setOperationMessage(error instanceof Error ? error.message : "病例目录加载失败", "error");
  } finally {
    loadingCatalog.value = false;
  }
}

function orderCases(demoCatalog: CaseRecord[], listedCases: CaseRecord[]) {
  const demoCaseIds = new Set(demoCatalog.map((item) => item.case_id));
  return [...demoCatalog, ...listedCases.filter((item) => !demoCaseIds.has(item.case_id))];
}

async function loadSelectedCase(announce = true) {
  if (!selectedCaseId.value || store.loading) return;
  const loadedCase = await store.loadCase(selectedCaseId.value);
  if (loadedCase) {
    const index = cases.value.findIndex((item) => item.case_id === loadedCase.case_id);
    if (index >= 0) cases.value.splice(index, 1, loadedCase);
    if (announce) setOperationMessage(`病例已加载：${loadedCase.case_id}`);
  } else if (store.error) {
    setOperationMessage(store.error, "error");
  }
}

async function createCase() {
  const createdCase = await store.createCase(caseTitle.value.trim() || "颌骨骨髓炎术中演示病例");
  if (createdCase) {
    cases.value = [createdCase, ...cases.value];
    selectedCaseId.value = createdCase.case_id;
    caseTitle.value = "";
    setOperationMessage(`病例已创建：${createdCase.case_id}`);
  } else if (store.error) {
    setOperationMessage(store.error, "error");
  }
}

function inputDisplayName(asset: CaseInputAsset) {
  const originalName = asset.metadata.original_filename;
  if (typeof originalName === "string" && originalName) return originalName;
  return asset.path.replace(/^.*[\\/]/, "");
}

function inputDisplayMeta(asset: CaseInputAsset) {
  const [width, height] = asset.dimensions;
  return width && height ? `${width} x ${height}` : asset.mime_type || "已载入";
}
</script>

<style scoped>
.case-management-shell {
  min-height: 100dvh;
  padding: var(--ov-page-top) var(--ov-page-inline) var(--ov-page-bottom);
  background: var(--ov-shell-background);
  color: var(--ov-text);
}

.management-header,
.management-grid {
  width: min(100%, var(--ov-content-standard));
  margin-right: auto;
  margin-left: auto;
}

.management-header {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  align-items: center;
  justify-content: space-between;
  padding: 0 2px 24px;
}

.intake-link {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  min-height: 38px;
  border: 1px solid var(--ov-border-strong);
  border-radius: 6px;
  padding: 8px 12px;
  background: var(--ov-bg-info);
  color: var(--ov-primary);
  font-size: 13px;
  font-weight: 800;
  text-decoration: none;
}

.intake-link :deep(.app-icon) {
  width: 17px;
  height: 17px;
}

.management-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-template-rows: repeat(2, minmax(0, 1fr));
  gap: 20px;
  min-height: clamp(660px, calc(100dvh - 220px), 860px);
  align-items: stretch;
}

.management-card {
  min-width: 0;
  min-height: 0;
  border: 1px solid var(--ov-border);
  border-radius: 6px;
  padding: 20px;
  background: var(--ov-bg-elevated);
  box-shadow: var(--ov-shadow);
  overflow: auto;
}

.management-card :deep(.ov-section-heading) {
  margin-bottom: 12px;
  border-bottom: 1px solid var(--ov-border-subtle);
  padding-bottom: 10px;
}

.management-card :deep(.ov-section-heading__title) {
  color: var(--ov-text);
  font-size: 15px;
}

.management-card :deep(.ov-section-heading__eyebrow) {
  display: none;
}

.field {
  display: grid;
  gap: 8px;
  margin-bottom: 14px;
}

.field span,
.create-case summary {
  color: var(--ov-text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.field input,
.field select {
  width: 100%;
  min-height: 36px;
  border: 1px solid var(--ov-border-strong);
  border-radius: 5px;
  padding: 7px 10px;
  background: var(--ov-bg-control);
  color: var(--ov-text);
  font: inherit;
  font-size: 13px;
}

.field input:focus,
.field select:focus {
  outline: 2px solid var(--ov-focus-ring);
  border-color: var(--ov-border-accent);
}

.create-case {
  margin-top: 16px;
  border-top: 1px solid var(--ov-border-subtle);
  padding-top: 12px;
}

.create-case summary {
  margin-bottom: 12px;
  cursor: pointer;
}

.operation-message,
.compact-state {
  margin: 10px 0 0;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 5px;
  padding: 8px 10px;
  background: var(--ov-bg-soft);
  color: var(--ov-text-secondary);
  font-size: 12px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.operation-message.error {
  border-color: var(--ov-danger-border);
  background: var(--ov-bg-danger);
  color: var(--ov-danger);
}

.current-case-card h2 {
  margin: 0 0 12px;
  color: var(--ov-text);
  font-size: 20px;
  line-height: 1.3;
}

.case-summary {
  display: grid;
  gap: 13px;
  margin: 0;
}

.case-summary div {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr);
  gap: 12px;
}

.case-summary dt {
  color: var(--ov-text-muted);
  font-size: 13px;
  font-weight: 800;
}

.case-summary dd {
  margin: 0;
  color: var(--ov-text);
  font-size: 13px;
  font-weight: 800;
  overflow-wrap: anywhere;
}

.asset-stack,
.warning-stack {
  display: grid;
  gap: 9px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.asset-stack li {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr);
  gap: 12px;
  align-items: center;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 5px;
  padding: 10px;
  background: var(--ov-bg-soft);
}

.file-icon {
  width: 32px;
  height: 32px;
}

.asset-stack strong {
  color: var(--ov-text);
  font-size: 13px;
}

.asset-stack p,
.asset-stack small {
  display: block;
  margin: 2px 0 0;
  color: var(--ov-text-muted);
  font-size: 12px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.warning-stack li,
.qc-empty {
  display: grid;
  grid-template-columns: 26px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
}

.warning-stack li {
  border: 1px solid var(--ov-border-subtle);
  border-radius: 5px;
  padding: 9px;
}

.warning-stack li.blocking {
  border-color: var(--ov-danger-border);
  background: var(--ov-bg-danger);
}

.qc-icon {
  width: 22px;
  height: 22px;
  margin-top: 1px;
}

.warning-stack strong,
.qc-empty p {
  margin: 0;
  color: var(--ov-text);
  font-size: 13px;
}

.warning-stack p {
  margin: 3px 0 0;
  color: var(--ov-text-secondary);
  font-size: 12px;
  line-height: 1.45;
}

@media (max-width: 959px) {
  .case-management-shell {
    padding: 14px;
  }

  .management-grid,
  .case-summary div {
    grid-template-columns: 1fr;
  }
}
</style>
