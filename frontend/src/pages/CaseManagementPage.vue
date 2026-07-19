<template>
  <main class="case-management-shell">
    <header class="management-header">
      <div class="management-title">
        <h1>病例建立、加载与基础质控</h1>
      </div>
      <RouterLink class="intake-link" to="/intake">
        <AppIcon name="upload" />
        <span>医院数据准入</span>
      </RouterLink>
    </header>

    <section class="management-grid">
      <section class="management-card">
        <SectionHeading icon="case" title="病例 / 建立与加载" />
        <label class="field">
          <span>病例标题</span>
          <input v-model="caseTitle" type="text" placeholder="请输入病例标题" />
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
        <label class="field">
          <span>病例 ID / 既有病例载入</span>
          <input v-model="loadCaseId" type="text" placeholder="请输入病例 ID" />
        </label>
        <AppButton
          variant="secondary"
          icon="load"
          block
          :disabled="store.loading || !canLoadCase"
          :title="store.loading ? '病例请求处理中，请稍候' : canLoadCase ? '载入指定病例' : '请输入病例 ID'"
          @click="loadCase"
        >
          加载病例
        </AppButton>
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
        <ul v-if="inputRows.length" class="asset-stack">
          <li v-for="asset in inputRows" :key="asset.id">
            <AppIcon class="file-icon" name="file" variant="tile" tone="cyan" />
            <div>
              <strong>{{ asset.channel }}</strong>
              <p>{{ asset.path }}</p>
              <small>{{ asset.meta }}</small>
            </div>
          </li>
        </ul>
        <p v-else class="empty-inline">暂无输入记录。请回到病例工作台写入白光、ICG 或摄像头输入。</p>
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
      </section>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";

import AppButton from "@/components/AppButton.vue";
import AppIcon from "@/components/AppIcon.vue";
import SectionHeading from "@/components/SectionHeading.vue";
import { useOperationMessage } from "@/composables/useOperationMessage";
import { useCaseStore } from "@/stores/caseStore";
import {
  caseStatusLabel,
  disclaimerVersionLabel,
  inputChannelLabel,
  inputMetaLabel,
  normalizeWarning,
} from "@/utils/caseDisplay";

const store = useCaseStore();

const caseTitle = ref("颌骨骨髓炎术中演示病例");
const loadCaseId = ref("");
const { operationMessage, operationMessageType, setOperationMessage } = useOperationMessage();

const latestRun = computed(() => store.currentCase?.analysis_runs.at(-1) ?? null);
const canLoadCase = computed(() => Boolean(loadCaseId.value.trim() || store.currentCase?.case_id));
const currentStatusLabel = computed(() => caseStatusLabel(store.currentCase?.status));
const displayCaseTitle = computed(() => store.currentCase?.title ?? "未载入病例");
const displayCaseId = computed(() => store.currentCase?.case_id ?? "待创建或加载");
const displayCaseVersion = computed(() => (store.currentCase ? `v${store.currentCase.version}` : "待创建"));
const displayRunId = computed(() => latestRun.value?.run_id ?? "暂无运行记录");

const inputRows = computed(() =>
  (store.currentCase?.inputs ?? []).map((asset) => ({
    id: asset.input_id,
    channel: inputChannelLabel(asset.channel),
    path: asset.path,
    meta: inputMetaLabel(asset),
  })),
);

const warningRows = computed(() => {
  const caseWarnings = store.currentCase?.warnings ?? [];
  const caseQualityFlags = store.currentCase?.quality_flags ?? [];
  const runWarnings = latestRun.value?.warnings ?? [];
  const inputWarnings = (store.currentCase?.inputs ?? []).flatMap((asset) => asset.quality_flags ?? []);
  return [...caseWarnings, ...caseQualityFlags, ...runWarnings, ...inputWarnings].map((warning, index) =>
    normalizeWarning(warning, index),
  );
});

async function createCase() {
  setOperationMessage("正在创建病例...");
  const createdCase = await store.createCase(caseTitle.value.trim() || "颌骨骨髓炎术中演示病例");
  if (createdCase) {
    loadCaseId.value = createdCase.case_id;
    setOperationMessage(`病例已创建：${createdCase.case_id}`);
  } else if (store.error) {
    setOperationMessage(store.error, "error");
  }
}

async function loadCase() {
  const caseId = loadCaseId.value.trim() || store.currentCase?.case_id;
  if (!caseId) return;
  setOperationMessage("正在加载病例...");
  const loadedCase = await store.loadCase(caseId);
  setOperationMessage(loadedCase ? `病例已加载：${loadedCase.case_id}` : store.error, loadedCase ? "info" : "error");
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

.management-title h1 {
  margin: 0;
  color: var(--ov-text);
  font-size: var(--ov-font-page-title);
  line-height: 1.15;
  letter-spacing: 0;
}

.management-grid {
  display: grid;
  grid-template-columns: minmax(360px, 0.75fr) minmax(0, 1.25fr);
  gap: 20px;
  align-items: start;
}

.management-card {
  min-width: 0;
  border: 1px solid var(--ov-border);
  border-radius: 6px;
  padding: 20px;
  background: var(--ov-bg-elevated);
  box-shadow: var(--ov-shadow);
}

.management-card :deep(.ov-section-heading) {
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--ov-border-subtle);
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

.field span {
  color: var(--ov-text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.field input {
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

.field input:focus {
  outline: 2px solid var(--ov-focus-ring);
  border-color: var(--ov-border-accent);
}

.operation-message {
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

.empty-inline {
  margin: 0;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 5px;
  padding: 10px 12px;
  background: var(--ov-bg-soft);
  color: var(--ov-text-secondary);
  font-size: 13px;
  line-height: 1.5;
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
