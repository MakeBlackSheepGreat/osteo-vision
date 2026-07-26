<template>
  <AppPageShell class="data-library-page" width="large">
    <header class="library-header">
      <div class="ov-title-lead">
        <AppIcon name="database" variant="badge" tone="cyan" />
        <div>
          <h1>公开代理视频库</h1>
          <p>{{ statusMessage }}</p>
        </div>
      </div>
      <AppMetricStrip class="library-metrics" :items="summaryItems" aria-label="视频库概览" />
    </header>

    <AppToolbar class="library-toolbar" aria-label="视频库筛选">
      <AppButton
        variant="primary"
        size="sm"
        icon="load"
        :disabled="interactionBusy"
        :title="interactionBusy ? '请等待当前视频库操作完成' : '重新读取本地公开视频清单'"
        @click="loadCandidates"
      >
        刷新视频库
      </AppButton>
      <label>
        <span>通道</span>
        <select v-model="fluorescenceFilter" :disabled="interactionBusy">
          <option v-for="option in videoCandidateFluorescenceFilterOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </label>
      <label>
        <span>用途</span>
        <select v-model="trainingFilter" :disabled="interactionBusy">
          <option v-for="option in videoCandidateTrainingFilterOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </label>
      <div class="current-case-state">
        <span>当前病例</span>
        <strong>{{ currentCaseLabel }}</strong>
      </div>
    </AppToolbar>

    <AppFeedbackBanner v-if="error" class="library-alert" tone="error" :message="error" />
    <AppFeedbackBanner v-if="operationMessage" class="library-status" tone="success" :message="operationMessage" />

    <section class="candidate-grid" aria-label="公开视频候选列表">
      <article v-for="candidate in paginatedCandidates" :key="candidate.record_id" class="candidate-card">
        <header class="candidate-card__header">
          <div>
            <h2>{{ videoCandidateDisplayTitle(candidate) }}</h2>
            <span>{{ candidate.record_id }}</span>
          </div>
          <span class="candidate-badge" :class="{ fluorescent: candidate.fluorescence === true }">
            {{ videoCandidateFluorescenceLabel(candidate) }}
          </span>
        </header>

        <figure v-if="candidate.preview_path || previewingRecordId === candidate.record_id" class="candidate-preview">
          <img v-if="candidate.preview_path" :src="apiClient.filePreviewUrl(candidate.preview_path)" alt="视频关键帧预览" />
          <figcaption v-else>正在生成关键帧预览...</figcaption>
        </figure>

        <div class="candidate-actions">
          <AppButton
            variant="secondary"
            size="sm"
            icon="video"
            :disabled="interactionBusy || !candidate.system_readable"
            :title="
              !candidate.system_readable
                ? '本地视频当前不可读取'
                : interactionBusy
                  ? '请等待当前视频库操作完成'
                  : '生成或刷新该视频的关键帧预览'
            "
            @click="createPreview(candidate.record_id)"
          >
            {{ previewingRecordId === candidate.record_id ? "生成中" : "预览" }}
          </AppButton>
          <AppButton
            variant="secondary"
            size="sm"
            icon="upload"
            :disabled="
              interactionBusy ||
              !store.currentCase ||
              !candidate.system_readable ||
              importedRecordIds.has(candidate.record_id)
            "
            :title="importButtonTitle(candidate)"
            @click="importCandidate(candidate.record_id)"
          >
            {{ importButtonLabel(candidate.record_id) }}
          </AppButton>
          <a v-if="videoCandidateSourceUrl(candidate)" :href="videoCandidateSourceUrl(candidate)" target="_blank" rel="noreferrer">
            <AppIcon name="externalLink" />
            原始来源
          </a>
        </div>
      </article>
    </section>

    <nav v-if="pageCount > 1" class="library-pagination" aria-label="视频库分页">
      <AppButton
        variant="secondary"
        size="sm"
        icon="arrowLeft"
        :disabled="interactionBusy || currentPage <= 1"
        :title="interactionBusy ? '请等待当前视频库操作完成' : currentPage <= 1 ? '当前已是第一页' : '查看上一页'"
        @click="currentPage -= 1"
      >
        上一页
      </AppButton>
      <span aria-live="polite">第 {{ currentPage }} / {{ pageCount }} 页 · 每页 {{ pageSize }} 条</span>
      <AppButton
        variant="secondary"
        size="sm"
        icon="arrowRight"
        :disabled="interactionBusy || currentPage >= pageCount"
        :title="interactionBusy ? '请等待当前视频库操作完成' : currentPage >= pageCount ? '当前已是最后一页' : '查看下一页'"
        @click="currentPage += 1"
      >
        下一页
      </AppButton>
    </nav>

    <AppEmptyState
      v-if="!loading && !filteredCandidates.length"
      class="empty-state"
      compact
      icon="video"
      title="暂无可显示视频"
      description="当前筛选条件下没有可显示的公开视频候选。"
    />
  </AppPageShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import AppButton from "@/components/AppButton.vue";
import AppEmptyState from "@/components/AppEmptyState.vue";
import AppFeedbackBanner from "@/components/AppFeedbackBanner.vue";
import AppIcon from "@/components/AppIcon.vue";
import AppMetricStrip from "@/components/AppMetricStrip.vue";
import AppPageShell from "@/components/AppPageShell.vue";
import AppToolbar from "@/components/AppToolbar.vue";
import { apiClient } from "@/services/apiClient";
import { useCaseStore } from "@/stores/caseStore";
import type { VideoCandidate } from "@/types/case";
import { errorMessage } from "@/utils/caseDisplay";
import {
  filterVideoCandidates,
  formatBytes,
  videoCandidateDisplayTitle,
  videoCandidateFilterSummary,
  videoCandidateFluorescenceFilterOptions,
  videoCandidateFluorescenceLabel,
  videoCandidateSourceUrl,
  videoCandidateTrainingBucket,
  videoCandidateTrainingFilterOptions,
  type VideoCandidateFluorescenceFilter,
  type VideoCandidateTrainingFilter,
} from "@/utils/videoCandidates";

const store = useCaseStore();
const loading = ref(false);
const error = ref("");
const candidates = ref<VideoCandidate[]>([]);
const fluorescenceFilter = ref<VideoCandidateFluorescenceFilter>("all");
const trainingFilter = ref<VideoCandidateTrainingFilter>("all");
const previewingRecordId = ref("");
const importingRecordId = ref("");
const importedRecordIds = computed(() => {
  const recordIds = new Set<string>();
  for (const asset of store.currentCase?.inputs ?? []) {
    const recordId = asset.channel === "video" ? asset.metadata?.record_id : undefined;
    if (typeof recordId === "string" && recordId.trim()) recordIds.add(recordId);
  }
  return recordIds;
});
const operationMessage = ref("");
const pageSize = 12;
const currentPage = ref(1);

const filteredCandidates = computed(() =>
  filterVideoCandidates(candidates.value, {
    fluorescence: fluorescenceFilter.value,
    training: trainingFilter.value,
  }),
);
const pageCount = computed(() => Math.max(1, Math.ceil(filteredCandidates.value.length / pageSize)));
const paginatedCandidates = computed(() => {
  const start = (currentPage.value - 1) * pageSize;
  return filteredCandidates.value.slice(start, start + pageSize);
});

watch([fluorescenceFilter, trainingFilter], () => {
  currentPage.value = 1;
});
watch(pageCount, (count) => {
  if (currentPage.value > count) currentPage.value = count;
});

const statusMessage = computed(() =>
  loading.value
    ? "正在读取本地公开视频清单..."
    : `已显示 ${videoCandidateFilterSummary(candidates.value.length, filteredCandidates.value.length)}候选。`,
);

const currentCaseLabel = computed(() => store.currentCase?.title || store.currentCase?.case_id || "未载入");
const interactionBusy = computed(
  () => loading.value || Boolean(previewingRecordId.value) || Boolean(importingRecordId.value),
);

const summaryItems = computed(() => {
  const fluorescenceCount = candidates.value.filter((candidate) => candidate.fluorescence === true).length;
  const nonFluorescenceCount = candidates.value.filter((candidate) => candidate.fluorescence === false).length;
  const enhancementCount = candidates.value.filter(
    (candidate) => videoCandidateTrainingBucket(candidate) === "enhancement_or_self_supervised",
  ).length;
  const demoCount = candidates.value.filter(
    (candidate) => videoCandidateTrainingBucket(candidate) === "demo_or_self_supervised",
  ).length;
  const totalBytes = candidates.value.reduce((sum, candidate) => sum + (candidate.size_bytes || 0), 0);
  return [
    { label: "总候选", value: String(candidates.value.length), icon: "database" as const },
    { label: "荧光", value: String(fluorescenceCount), icon: "target" as const },
    { label: "非荧光", value: String(nonFluorescenceCount), icon: "video" as const },
    { label: "增强/自监督", value: String(enhancementCount), icon: "layers" as const },
    { label: "演示/自监督", value: String(demoCount), icon: "play" as const },
    { label: "本地体量", value: formatBytes(totalBytes), icon: "folder" as const },
  ];
});

async function loadCandidates() {
  if (interactionBusy.value) return;
  loading.value = true;
  error.value = "";
  operationMessage.value = "";
  try {
    const payload = await apiClient.listVideoCandidates(true);
    candidates.value = payload.items;
  } catch (loadError) {
    error.value = errorMessage(loadError);
  } finally {
    loading.value = false;
  }
}

async function createPreview(recordId: string) {
  if (interactionBusy.value) return;
  previewingRecordId.value = recordId;
  error.value = "";
  operationMessage.value = "";
  try {
    const updated = await apiClient.createVideoCandidatePreview(recordId);
    candidates.value = candidates.value.map((candidate) =>
      candidate.record_id === recordId ? { ...candidate, ...updated } : candidate,
    );
    operationMessage.value = `关键帧预览已更新：${recordId}`;
  } catch (previewError) {
    error.value = errorMessage(previewError);
  } finally {
    previewingRecordId.value = "";
  }
}

async function importCandidate(recordId: string) {
  if (!store.currentCase || interactionBusy.value || importedRecordIds.value.has(recordId)) return;
  const targetCaseId = store.currentCase.case_id;
  importingRecordId.value = recordId;
  error.value = "";
  operationMessage.value = "";
  try {
    store.currentCase = await apiClient.importVideoCandidate(targetCaseId, recordId);
    operationMessage.value = `视频已导入病例 ${targetCaseId}：${recordId}`;
  } catch (importError) {
    error.value = errorMessage(importError);
  } finally {
    importingRecordId.value = "";
  }
}

function importButtonLabel(recordId: string): string {
  if (importingRecordId.value === recordId) return "导入中";
  return importedRecordIds.value.has(recordId) ? "已导入" : "导入病例";
}

function importButtonTitle(candidate: VideoCandidate): string {
  if (!store.currentCase) return "请先载入病例";
  if (!candidate.system_readable) return "本地视频当前不可读取";
  if (importedRecordIds.value.has(candidate.record_id)) return "该视频已导入当前病例";
  if (interactionBusy.value) return "请等待当前视频库操作完成";
  return `导入到当前病例：${store.currentCase.case_id}`;
}

onMounted(() => {
  void loadCandidates();
});
</script>

<style scoped>
.data-library-page {
  min-height: 100dvh;
  padding: var(--ov-page-top) var(--ov-page-inline) var(--ov-page-bottom);
  background: var(--ov-shell-background);
  color: var(--ov-text);
}

.library-header,
.library-toolbar,
.library-alert,
.library-status,
.candidate-grid,
.library-pagination,
.empty-state {
  width: min(100%, var(--ov-content-standard));
  margin-right: auto;
  margin-left: auto;
}

.library-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(420px, 0.88fr);
  gap: 24px;
  align-items: end;
  margin-bottom: 24px;
}

.library-header h1 {
  margin: 0;
  color: var(--ov-text);
  font-size: var(--ov-font-page-title);
  line-height: 1.15;
  letter-spacing: 0;
}

.library-header p {
  margin: 8px 0 0;
  color: var(--ov-text-secondary);
  font-size: 14px;
  font-weight: 800;
}

.library-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.metric-tile {
  min-width: 0;
  border: 1px solid var(--ov-border);
  border-radius: 6px;
  padding: 12px 14px;
  background: var(--ov-bg-elevated);
  box-shadow: none;
}

.metric-tile span,
.metric-tile strong {
  display: block;
}

.metric-tile span {
  color: var(--ov-text-muted);
  font-size: 11px;
  font-weight: 900;
}

.metric-tile strong {
  margin-top: 4px;
  color: var(--ov-text);
  font-size: 18px;
  line-height: 1.15;
  overflow-wrap: anywhere;
}

.library-toolbar {
  display: grid;
  grid-template-columns: 148px repeat(2, minmax(140px, 190px)) minmax(180px, 1fr);
  gap: 14px;
  align-items: end;
  margin-bottom: 20px;
  border: 1px solid var(--ov-border);
  border-radius: 6px;
  padding: 16px;
  background: var(--ov-bg-elevated);
  box-shadow: var(--ov-shadow);
}

.library-toolbar label,
.current-case-state {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.library-toolbar span,
.current-case-state span {
  color: var(--ov-text-muted);
  font-size: 11px;
  font-weight: 900;
}

.library-toolbar select {
  width: 100%;
  min-height: 34px;
  border: 1px solid var(--ov-border-strong);
  border-radius: 5px;
  padding: 6px 8px;
  background: var(--ov-bg-control);
  color: var(--ov-text);
  font: inherit;
  font-size: 13px;
}

.library-toolbar select:disabled {
  cursor: not-allowed;
  opacity: 0.58;
}

.current-case-state strong {
  min-height: 34px;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 5px;
  padding: 7px 9px;
  background: var(--ov-bg-soft);
  color: var(--ov-primary);
  font-size: 13px;
  line-height: 1.4;
  overflow-wrap: anywhere;
}

.library-alert,
.empty-state {
  border: 1px solid var(--ov-danger-border);
  border-radius: 6px;
  padding: 10px 12px;
  background: var(--ov-bg-danger);
  color: var(--ov-danger);
  font-size: 13px;
  font-weight: 800;
}

.library-status {
  margin-bottom: 16px;
  border: 1px solid color-mix(in srgb, var(--ov-success) 45%, var(--ov-border));
  border-radius: 6px;
  padding: 10px 12px;
  background: var(--ov-bg-success);
  color: var(--ov-success);
  font-size: 13px;
  font-weight: 700;
}

.candidate-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.candidate-card {
  display: grid;
  gap: 12px;
  min-width: 0;
  border: 1px solid var(--ov-border);
  border-radius: 6px;
  padding: 16px;
  background: var(--ov-bg-elevated);
  box-shadow: none;
}

.candidate-card__header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: start;
}

.candidate-card h2 {
  margin: 0;
  color: var(--ov-text);
  font-size: 14px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.candidate-card__header div > span {
  display: block;
  margin-top: 3px;
  color: var(--ov-text-muted);
  font-size: 11px;
  font-weight: 800;
  overflow-wrap: anywhere;
}

.candidate-badge {
  border: 1px solid var(--ov-border-subtle);
  border-radius: 999px;
  padding: 3px 7px;
  background: var(--ov-bg-soft);
  color: var(--ov-text-secondary);
  font-size: 11px;
  font-weight: 900;
  overflow-wrap: anywhere;
  white-space: normal;
}

.candidate-badge.fluorescent {
  border-color: var(--ov-success);
  background: var(--ov-bg-success);
  color: var(--ov-success);
}

.candidate-preview {
  display: grid;
  margin: 0;
  overflow: hidden;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 5px;
  background: var(--ov-bg-media);
}

.candidate-preview img {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  object-fit: contain;
}

.candidate-preview figcaption {
  display: grid;
  min-height: 94px;
  place-items: center;
  color: var(--ov-text-muted);
  font-size: 12px;
  font-weight: 800;
}

.candidate-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr)) auto;
  gap: 10px;
  align-items: center;
}

.candidate-actions a {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  justify-content: center;
  min-height: 36px;
  padding: 6px 8px;
  color: var(--ov-primary-strong);
  font-size: 12px;
  font-weight: 900;
  text-decoration: none;
  overflow-wrap: anywhere;
  white-space: normal;
}

.candidate-actions a :deep(.app-icon) {
  width: 15px;
  height: 15px;
}

.library-pagination {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  justify-content: center;
  margin-top: 20px;
  padding: 14px 16px;
  border-top: 1px solid var(--ov-border-subtle);
  color: var(--ov-text-secondary);
  font-size: 13px;
  font-weight: 700;
}

.candidate-actions a:hover {
  text-decoration: underline;
}

.empty-state {
  margin-top: 12px;
  border-color: var(--ov-border-subtle);
  background: var(--ov-bg-soft);
  color: var(--ov-text-secondary);
}

@media (max-width: 1180px) {
  .library-header {
    grid-template-columns: 1fr;
  }

  .candidate-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .data-library-page {
    padding: 16px 14px 24px;
  }

  .library-header h1 {
    font-size: 24px;
  }

  .library-metrics,
  .library-toolbar,
  .candidate-grid {
    grid-template-columns: 1fr;
  }

  .candidate-actions {
    grid-template-columns: 1fr;
  }
}
</style>
