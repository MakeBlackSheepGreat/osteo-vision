<template>
  <div class="video-library-panel">
    <select
      :value="selectedVideoCandidateId"
      :disabled="isLoadingVideoCandidates || !filteredVideoCandidates.length"
      aria-label="公开视频候选"
      @change="emit('selectVideoCandidate', ($event.target as HTMLSelectElement).value)"
    >
      <option value="">公开视频候选（{{ videoCandidateListSummary }}）</option>
      <option v-for="candidate in filteredVideoCandidates" :key="candidate.record_id" :value="candidate.record_id">
        {{ candidate.record_id }} · {{ candidate.medical_scene || candidate.title }}
      </option>
    </select>
    <div class="video-library-actions">
      <AppButton
        variant="ghost"
        size="sm"
        icon="video"
        :disabled="isLoadingVideoCandidates"
        @click="emit('loadVideoCandidates')"
      >
        加载
      </AppButton>
      <AppButton
        variant="ghost"
        size="sm"
        icon="upload"
        :disabled="loading || !hasCase || !selectedVideoCandidateId"
        @click="emit('importVideoCandidate')"
      >
        导入
      </AppButton>
    </div>
  </div>
  <div class="video-library-filters" aria-label="公开视频筛选">
    <label>
      <span>通道</span>
      <select v-model="videoFluorescenceFilter">
        <option
          v-for="option in videoCandidateFluorescenceFilterOptions"
          :key="option.value"
          :value="option.value"
        >
          {{ option.label }}
        </option>
      </select>
    </label>
    <label>
      <span>用途</span>
      <select v-model="videoTrainingFilter">
        <option v-for="option in videoCandidateTrainingFilterOptions" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
    </label>
  </div>
  <article v-if="selectedVideoCandidate" class="video-candidate-card" aria-label="公开视频候选详情">
    <header class="candidate-card-header">
      <div>
        <strong>{{ selectedVideoCandidate.title || selectedVideoCandidate.record_id }}</strong>
        <span>{{ selectedVideoCandidate.record_id }}</span>
      </div>
      <span class="candidate-badge" :class="{ fluorescent: selectedVideoCandidate.fluorescence === true }">
        {{ selectedVideoCandidateFluorescenceLabel }}
      </span>
    </header>
    <figure v-if="selectedVideoCandidatePreviewSrc || isLoadingVideoPreview" class="candidate-preview">
      <img
        v-if="selectedVideoCandidatePreviewSrc"
        :src="selectedVideoCandidatePreviewSrc"
        alt="公开视频候选关键帧预览"
      />
      <figcaption v-else>正在生成关键帧预览...</figcaption>
    </figure>
    <dl class="candidate-detail-grid">
      <template v-for="detail in selectedVideoCandidateDetails" :key="detail.label">
        <dt>{{ detail.label }}</dt>
        <dd>{{ detail.value }}</dd>
      </template>
    </dl>
    <a
      v-if="selectedVideoCandidateSourceUrl"
      class="candidate-source-link"
      :href="selectedVideoCandidateSourceUrl"
      target="_blank"
      rel="noreferrer"
    >
      打开原始来源
    </a>
  </article>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";

import AppButton from "@/components/AppButton.vue";
import type { VideoCandidate } from "@/types/case";
import {
  filterVideoCandidates,
  findVideoCandidate,
  videoCandidateDetails,
  videoCandidateFilterSummary,
  videoCandidateFluorescenceFilterOptions,
  videoCandidateFluorescenceLabel,
  videoCandidateSourceUrl,
  videoCandidateTrainingFilterOptions,
  type VideoCandidateFluorescenceFilter,
  type VideoCandidateTrainingFilter,
} from "@/utils/videoCandidates";

const props = defineProps<{
  loading: boolean;
  hasCase: boolean;
  isLoadingVideoCandidates: boolean;
  isLoadingVideoPreview: boolean;
  selectedVideoCandidateId: string;
  selectedVideoCandidatePreviewSrc: string;
  videoCandidates: VideoCandidate[];
}>();

const emit = defineEmits<{
  loadVideoCandidates: [];
  selectVideoCandidate: [recordId: string];
  importVideoCandidate: [];
}>();

// 候选库组件只管理本地筛选和详情展示，真正的下载、导入和预览生成仍由页面层编排。
const videoFluorescenceFilter = ref<VideoCandidateFluorescenceFilter>("all");
const videoTrainingFilter = ref<VideoCandidateTrainingFilter>("all");
const filteredVideoCandidates = computed(() =>
  filterVideoCandidates(props.videoCandidates, {
    fluorescence: videoFluorescenceFilter.value,
    training: videoTrainingFilter.value,
  }),
);
const videoCandidateListSummary = computed(() =>
  videoCandidateFilterSummary(props.videoCandidates.length, filteredVideoCandidates.value.length),
);
const selectedVideoCandidate = computed(() =>
  findVideoCandidate(props.videoCandidates, props.selectedVideoCandidateId),
);
const selectedVideoCandidateDetails = computed(() =>
  selectedVideoCandidate.value ? videoCandidateDetails(selectedVideoCandidate.value) : [],
);
const selectedVideoCandidateFluorescenceLabel = computed(() =>
  selectedVideoCandidate.value ? videoCandidateFluorescenceLabel(selectedVideoCandidate.value) : "未知通道",
);
const selectedVideoCandidateSourceUrl = computed(() =>
  selectedVideoCandidate.value ? videoCandidateSourceUrl(selectedVideoCandidate.value) : "",
);

watch(filteredVideoCandidates, (candidates) => {
  if (!props.selectedVideoCandidateId) return;
  if (candidates.some((candidate) => candidate.record_id === props.selectedVideoCandidateId)) return;
  emit("selectVideoCandidate", candidates[0]?.record_id ?? "");
});
</script>

<style scoped>
.video-library-panel {
  display: grid;
  grid-template-columns: 1fr;
  gap: 6px;
  align-items: stretch;
  margin: -1px 0 8px;
}

.video-library-panel select {
  width: 100%;
  min-height: 30px;
  border: 1px solid var(--ov-border-strong);
  border-radius: 5px;
  padding: 5px 8px;
  background: var(--ov-bg-elevated);
  color: var(--ov-text);
  font: inherit;
  font-size: 12px;
}

.video-library-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}

.video-library-filters {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
  margin: -2px 0 8px;
}

.video-library-filters label {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.video-library-filters span {
  color: var(--ov-text-muted);
  font-size: 11px;
  font-weight: 900;
}

.video-library-filters select {
  width: 100%;
  min-height: 28px;
  border: 1px solid var(--ov-border-strong);
  border-radius: 5px;
  padding: 4px 7px;
  background: var(--ov-bg-elevated);
  color: var(--ov-text);
  font: inherit;
  font-size: 12px;
}

.video-candidate-card {
  display: grid;
  gap: 7px;
  margin: 0 0 8px;
  border: 1px solid var(--ov-border);
  border-radius: 6px;
  padding: 8px;
  background: var(--ov-bg-soft);
}

.candidate-card-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: start;
}

.candidate-card-header strong,
.candidate-card-header span {
  display: block;
  min-width: 0;
}

.candidate-card-header strong {
  color: var(--ov-text);
  font-size: 12px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.candidate-card-header div > span {
  margin-top: 2px;
  color: var(--ov-text-muted);
  font-size: 11px;
  overflow-wrap: anywhere;
}

.candidate-badge {
  border: 1px solid var(--ov-border-subtle);
  border-radius: 999px;
  padding: 3px 7px;
  background: var(--ov-bg-elevated);
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

.candidate-detail-grid {
  display: grid;
  grid-template-columns: 76px minmax(0, 1fr);
  gap: 4px 8px;
  margin: 0;
}

.candidate-preview {
  display: grid;
  gap: 4px;
  margin: 0;
  overflow: hidden;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 5px;
  background: var(--ov-bg-panel);
}

.candidate-preview img {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  object-fit: contain;
}

.candidate-preview figcaption {
  display: grid;
  min-height: 58px;
  place-items: center;
  color: var(--ov-text-secondary);
  font-size: 11px;
  font-weight: 800;
}

.candidate-detail-grid dt,
.candidate-detail-grid dd {
  min-width: 0;
  font-size: 11px;
  line-height: 1.45;
}

.candidate-detail-grid dt {
  color: var(--ov-text-muted);
  font-weight: 900;
}

.candidate-detail-grid dd {
  margin: 0;
  color: var(--ov-text-secondary);
  overflow-wrap: anywhere;
}

.candidate-source-link {
  justify-self: start;
  color: var(--ov-primary-strong);
  font-size: 11px;
  font-weight: 900;
  text-decoration: none;
}

.candidate-source-link:hover {
  text-decoration: underline;
}
</style>
