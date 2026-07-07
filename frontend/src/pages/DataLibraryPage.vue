<template>
  <main class="data-library-page">
    <header class="library-header">
      <div>
        <h1>公开代理视频库</h1>
        <p>{{ statusMessage }}</p>
      </div>
      <div class="library-metrics" aria-label="视频库概览">
        <div v-for="item in summaryItems" :key="item.label" class="metric-tile">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </div>
      </div>
    </header>

    <section class="library-toolbar" aria-label="视频库筛选">
      <AppButton variant="primary" size="sm" icon="load" :disabled="loading" @click="loadCandidates">
        刷新视频库
      </AppButton>
      <label>
        <span>通道</span>
        <select v-model="fluorescenceFilter">
          <option v-for="option in videoCandidateFluorescenceFilterOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </label>
      <label>
        <span>用途</span>
        <select v-model="trainingFilter">
          <option v-for="option in videoCandidateTrainingFilterOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </label>
      <div class="current-case-state">
        <span>当前病例</span>
        <strong>{{ currentCaseLabel }}</strong>
      </div>
    </section>

    <section v-if="error" class="library-alert" role="alert">{{ error }}</section>

    <section class="candidate-grid" aria-label="公开视频候选列表">
      <article v-for="candidate in filteredCandidates" :key="candidate.record_id" class="candidate-card">
        <header class="candidate-card__header">
          <div>
            <h2>{{ candidate.title || candidate.record_id }}</h2>
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

        <dl class="candidate-details">
          <template v-for="detail in videoCandidateDetails(candidate)" :key="detail.label">
            <dt>{{ detail.label }}</dt>
            <dd>{{ detail.value }}</dd>
          </template>
        </dl>

        <div class="candidate-actions">
          <AppButton
            variant="secondary"
            size="sm"
            icon="video"
            :disabled="previewingRecordId === candidate.record_id || !candidate.system_readable"
            @click="createPreview(candidate.record_id)"
          >
            预览
          </AppButton>
          <AppButton
            variant="secondary"
            size="sm"
            icon="upload"
            :disabled="!store.currentCase || !candidate.system_readable || importingRecordId === candidate.record_id"
            @click="importCandidate(candidate.record_id)"
          >
            导入病例
          </AppButton>
          <a v-if="videoCandidateSourceUrl(candidate)" :href="videoCandidateSourceUrl(candidate)" target="_blank" rel="noreferrer">
            原始来源
          </a>
        </div>
      </article>
    </section>

    <p v-if="!loading && !filteredCandidates.length" class="empty-state">当前筛选下没有可显示的视频候选。</p>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import AppButton from "@/components/AppButton.vue";
import { apiClient } from "@/services/apiClient";
import { useCaseStore } from "@/stores/caseStore";
import type { VideoCandidate } from "@/types/case";
import { errorMessage } from "@/utils/caseDisplay";
import {
  filterVideoCandidates,
  formatBytes,
  videoCandidateDetails,
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

const filteredCandidates = computed(() =>
  filterVideoCandidates(candidates.value, {
    fluorescence: fluorescenceFilter.value,
    training: trainingFilter.value,
  }),
);

const statusMessage = computed(() =>
  loading.value
    ? "正在读取本地公开视频 manifest..."
    : `已显示 ${videoCandidateFilterSummary(candidates.value.length, filteredCandidates.value.length)}候选。`,
);

const currentCaseLabel = computed(() => store.currentCase?.title || store.currentCase?.case_id || "未载入");

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
    { label: "总候选", value: String(candidates.value.length) },
    { label: "荧光", value: String(fluorescenceCount) },
    { label: "非荧光", value: String(nonFluorescenceCount) },
    { label: "增强/自监督", value: String(enhancementCount) },
    { label: "演示/自监督", value: String(demoCount) },
    { label: "本地体量", value: formatBytes(totalBytes) },
  ];
});

async function loadCandidates() {
  loading.value = true;
  error.value = "";
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
  previewingRecordId.value = recordId;
  error.value = "";
  try {
    const updated = await apiClient.createVideoCandidatePreview(recordId);
    candidates.value = candidates.value.map((candidate) =>
      candidate.record_id === recordId ? { ...candidate, ...updated } : candidate,
    );
  } catch (previewError) {
    error.value = errorMessage(previewError);
  } finally {
    previewingRecordId.value = "";
  }
}

async function importCandidate(recordId: string) {
  if (!store.currentCase) return;
  importingRecordId.value = recordId;
  error.value = "";
  try {
    store.currentCase = await apiClient.importVideoCandidate(store.currentCase.case_id, recordId);
  } catch (importError) {
    error.value = errorMessage(importError);
  } finally {
    importingRecordId.value = "";
  }
}

onMounted(() => {
  void loadCandidates();
});
</script>

<style scoped>
.data-library-page {
  min-height: 100dvh;
  padding: 86px 28px 28px;
  background:
    radial-gradient(circle at 12% 4%, rgba(44, 126, 192, 0.28), transparent 28%),
    radial-gradient(circle at 86% 0%, rgba(58, 211, 255, 0.16), transparent 30%),
    linear-gradient(rgba(103, 222, 255, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(103, 222, 255, 0.035) 1px, transparent 1px),
    linear-gradient(180deg, #07131f, #091724 360px, #06101b);
  background-size: auto, auto, 28px 28px, 28px 28px, auto;
  color: #d8edf7;
}

.library-header,
.library-toolbar,
.library-alert,
.candidate-grid,
.empty-state {
  width: min(100%, 1540px);
  margin-right: auto;
  margin-left: auto;
}

.library-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(420px, 0.88fr);
  gap: 18px;
  align-items: end;
  margin-bottom: 14px;
}

.library-header h1 {
  margin: 0;
  color: #f2fbff;
  font-size: 30px;
  line-height: 1.15;
  letter-spacing: 0;
  text-shadow: 0 0 22px rgba(103, 222, 255, 0.22);
}

.library-header p {
  margin: 8px 0 0;
  color: #9dbccc;
  font-size: 14px;
  font-weight: 800;
}

.library-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.metric-tile {
  min-width: 0;
  border: 1px solid rgba(123, 215, 255, 0.26);
  border-radius: 6px;
  padding: 8px 10px;
  background:
    linear-gradient(180deg, rgba(13, 34, 52, 0.94), rgba(7, 20, 34, 0.94)),
    #081624;
  box-shadow:
    0 0 0 1px rgba(71, 208, 255, 0.07) inset,
    0 14px 34px rgba(0, 0, 0, 0.18);
}

.metric-tile span,
.metric-tile strong {
  display: block;
}

.metric-tile span {
  color: #9dbccc;
  font-size: 11px;
  font-weight: 900;
}

.metric-tile strong {
  margin-top: 4px;
  color: #f2fbff;
  font-size: 18px;
  line-height: 1.15;
  overflow-wrap: anywhere;
}

.library-toolbar {
  display: grid;
  grid-template-columns: 148px repeat(2, minmax(140px, 190px)) minmax(180px, 1fr);
  gap: 10px;
  align-items: end;
  margin-bottom: 12px;
  border: 1px solid rgba(123, 215, 255, 0.26);
  border-radius: 6px;
  padding: 10px;
  background:
    linear-gradient(180deg, rgba(13, 34, 52, 0.94), rgba(7, 20, 34, 0.94)),
    #081624;
  box-shadow:
    0 0 0 1px rgba(71, 208, 255, 0.07) inset,
    0 14px 34px rgba(0, 0, 0, 0.18);
}

.library-toolbar label,
.current-case-state {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.library-toolbar span,
.current-case-state span {
  color: #9dbccc;
  font-size: 11px;
  font-weight: 900;
}

.library-toolbar select {
  width: 100%;
  min-height: 34px;
  border: 1px solid rgba(123, 215, 255, 0.28);
  border-radius: 5px;
  padding: 6px 8px;
  background: rgba(3, 14, 25, 0.78);
  color: #eefaff;
  font: inherit;
  font-size: 13px;
}

.current-case-state strong {
  min-height: 34px;
  border: 1px solid rgba(123, 215, 255, 0.22);
  border-radius: 5px;
  padding: 7px 9px;
  background: rgba(255, 255, 255, 0.045);
  color: #bdefff;
  font-size: 13px;
  line-height: 1.4;
  overflow-wrap: anywhere;
}

.library-alert,
.empty-state {
  border: 1px solid rgba(255, 116, 122, 0.42);
  border-radius: 6px;
  padding: 10px 12px;
  background: rgba(68, 19, 25, 0.68);
  color: #ffd3d6;
  font-size: 13px;
  font-weight: 800;
}

.candidate-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.candidate-card {
  display: grid;
  gap: 9px;
  min-width: 0;
  border: 1px solid rgba(123, 215, 255, 0.26);
  border-radius: 6px;
  padding: 11px;
  background:
    linear-gradient(180deg, rgba(13, 34, 52, 0.94), rgba(7, 20, 34, 0.94)),
    #081624;
  box-shadow:
    0 0 0 1px rgba(71, 208, 255, 0.07) inset,
    0 14px 34px rgba(0, 0, 0, 0.18);
}

.candidate-card__header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: start;
}

.candidate-card h2 {
  margin: 0;
  color: #f2fbff;
  font-size: 14px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.candidate-card__header div > span {
  display: block;
  margin-top: 3px;
  color: #9dbccc;
  font-size: 11px;
  font-weight: 800;
  overflow-wrap: anywhere;
}

.candidate-badge {
  border: 1px solid rgba(123, 215, 255, 0.24);
  border-radius: 999px;
  padding: 3px 7px;
  background: rgba(255, 255, 255, 0.045);
  color: #d8edf7;
  font-size: 11px;
  font-weight: 900;
  white-space: nowrap;
}

.candidate-badge.fluorescent {
  border-color: rgba(87, 223, 174, 0.5);
  background: rgba(43, 203, 145, 0.14);
  color: #c5ffed;
}

.candidate-preview {
  display: grid;
  margin: 0;
  overflow: hidden;
  border: 1px solid rgba(123, 215, 255, 0.22);
  border-radius: 5px;
  background: #07131f;
}

.candidate-preview img {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  object-fit: cover;
}

.candidate-preview figcaption {
  display: grid;
  min-height: 94px;
  place-items: center;
  color: #9dbccc;
  font-size: 12px;
  font-weight: 800;
}

.candidate-details {
  display: grid;
  grid-template-columns: 88px minmax(0, 1fr);
  gap: 4px 8px;
  margin: 0;
}

.candidate-details dt,
.candidate-details dd {
  min-width: 0;
  font-size: 12px;
  line-height: 1.45;
}

.candidate-details dt {
  color: #9dbccc;
  font-weight: 900;
}

.candidate-details dd {
  margin: 0;
  color: #d8edf7;
  overflow-wrap: anywhere;
}

.candidate-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr)) auto;
  gap: 8px;
  align-items: center;
}

.candidate-actions a {
  color: #9be9ff;
  font-size: 12px;
  font-weight: 900;
  text-decoration: none;
  white-space: nowrap;
}

.candidate-actions a:hover {
  text-decoration: underline;
}

.empty-state {
  margin-top: 12px;
  border-color: rgba(123, 215, 255, 0.22);
  background: rgba(255, 255, 255, 0.045);
  color: #bdefff;
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
