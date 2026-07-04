<template>
  <aside class="left-sidebar" aria-label="输入与分析控制">
    <section class="control-card">
      <SectionHeading icon="layers" title="官方 4K MP4 / JPEG 输入" />
      <label class="field file-field">
        <span>白光图像路径</span>
        <div class="path-input">
          <input
            :value="whiteLightPath"
            type="text"
            placeholder="D:\\data\\case_001\\white.jpg"
            @input="emitPath('white', $event)"
          />
          <AppButton
            class="file-picker-button"
            variant="ghost"
            size="sm"
            icon="folder"
            icon-only
            :disabled="isUploadingWhite"
            :title="isUploadingWhite ? '正在上传白光图像' : '选择并上传白光图像'"
            aria-label="选择白光图像"
            @click="openFilePicker('white_light')"
          />
        </div>
      </label>
      <label class="field file-field">
        <span>ICG 荧光图像路径</span>
        <div class="path-input">
          <input
            :value="fluorescencePath"
            type="text"
            placeholder="D:\\data\\case_001\\icg.jpg"
            @input="emitPath('fluorescence', $event)"
          />
          <AppButton
            class="file-picker-button"
            variant="ghost"
            size="sm"
            icon="folder"
            icon-only
            :disabled="isUploadingFluorescence"
            :title="isUploadingFluorescence ? '正在上传 ICG 荧光图像' : '选择并上传 ICG 荧光图像'"
            aria-label="选择 ICG 荧光图像"
            @click="openFilePicker('fluorescence')"
          />
        </div>
      </label>
      <label class="field file-field">
        <span>官方 MP4 视频路径</span>
        <div class="path-input">
          <input
            :value="videoPath"
            type="text"
            placeholder="D:\\data\\case_001\\official_4k.mp4"
            @input="emitPath('video', $event)"
          />
          <AppButton
            class="file-picker-button"
            variant="ghost"
            size="sm"
            icon="folder"
            icon-only
            :disabled="isUploadingVideo"
            :title="isUploadingVideo ? '正在上传 MP4 视频' : '选择并上传官方 MP4 视频'"
            aria-label="选择官方 MP4 视频"
            @click="openFilePicker('video')"
          />
        </div>
      </label>
      <label class="field">
        <span>关键时间点（秒）</span>
        <input
          :value="videoTimepoints"
          type="text"
          inputmode="decimal"
          placeholder="例：0, 1.5, 3.0"
          @input="emit('update:videoTimepoints', ($event.target as HTMLInputElement).value)"
        />
      </label>
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

      <div class="camera-input-panel">
        <div class="camera-panel-header">
          <AppIcon name="camera" variant="tile" tone="cyan" />
          <div class="camera-panel-copy">
            <strong>摄像头输入</strong>
            <span>{{ cameraStatusLabel }}</span>
          </div>
        </div>
        <div class="camera-action-row">
          <AppButton
            variant="secondary"
            size="sm"
            icon="camera"
            :disabled="isOpeningCamera"
            @click="emit('startCamera')"
          >
            打开摄像头
          </AppButton>
          <AppButton variant="ghost" size="sm" :disabled="!cameraActive" @click="emit('stopCamera')">停止</AppButton>
          <AppButton variant="ghost" size="sm" :disabled="loading || !hasCase || !cameraActive" @click="emit('importCamera')">
            写入
          </AppButton>
        </div>
      </div>

      <div class="input-action-row">
        <AppButton variant="secondary" size="sm" icon="upload" :disabled="loading || !hasCase" @click="emit('importInputs')">
          写入双通道
        </AppButton>
        <AppButton
          variant="secondary"
          size="sm"
          icon="video"
          :disabled="loading || !hasCase || !videoPath.trim()"
          @click="emit('importVideo')"
        >
          写入 MP4
        </AppButton>
      </div>
      <p v-if="operationMessage" class="operation-message" :class="{ error: operationMessageType === 'error' }">
        {{ operationMessage }}
      </p>
      <input
        ref="whiteLightFileInput"
        class="hidden-file-input"
        type="file"
        accept="image/*"
        @change="emit('filePicked', 'white_light', $event)"
      />
      <input
        ref="fluorescenceFileInput"
        class="hidden-file-input"
        type="file"
        accept="image/*"
        @change="emit('filePicked', 'fluorescence', $event)"
      />
      <input
        ref="videoFileInput"
        class="hidden-file-input"
        type="file"
        accept="video/mp4,.mp4"
        @change="emit('filePicked', 'video', $event)"
      />
    </section>

    <section class="control-card">
      <SectionHeading icon="target" icon-tone="cyan" title="融合参数 / 伪彩与阈值" />
      <label class="field range-field">
        <span>融合透明度</span>
        <div class="range-row">
          <input
            :value="alpha"
            type="range"
            min="0"
            max="1"
            step="0.05"
            @input="emitNumber('alpha', $event)"
          />
          <output>{{ alpha.toFixed(2) }}</output>
        </div>
      </label>
      <label class="field range-field">
        <span>荧光阈值</span>
        <div class="range-row">
          <input
            :value="threshold"
            type="range"
            min="0"
            max="1"
            step="0.05"
            @input="emitNumber('threshold', $event)"
          />
          <output>{{ threshold.toFixed(2) }}</output>
        </div>
      </label>
      <label class="field">
        <span>伪彩方案</span>
        <select :value="colormap" @change="emitColormap">
          <option value="green">绿色</option>
          <option value="amber">琥珀色</option>
          <option value="magenta">品红色</option>
        </select>
      </label>
      <div class="analysis-action-row">
        <AppButton variant="primary" size="sm" icon="play" :disabled="loading || !hasCase" @click="emit('runAnalysis')">
          双通道分析
        </AppButton>
        <AppButton
          variant="secondary"
          size="sm"
          icon="video"
          :disabled="loading || !hasCase || !videoPath.trim()"
          @click="emit('runVideoFileAnalysis')"
        >
          MP4关键帧
        </AppButton>
        <AppButton
          variant="secondary"
          size="sm"
          icon="video"
          :disabled="loading || !hasCase || isOpeningCamera"
          @click="emit('runRealtimeVideo')"
        >
          实时预览
        </AppButton>
      </div>
      <p v-if="realtimeVideoActive" class="realtime-status">实时预览通道已登记，当前流式 AI 推理仍为接口预留。</p>
    </section>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";

import AppButton from "@/components/AppButton.vue";
import AppIcon from "@/components/AppIcon.vue";
import SectionHeading from "@/components/SectionHeading.vue";
import type { VideoCandidate } from "@/types/case";
import {
  filterVideoCandidates,
  findVideoCandidate,
  videoCandidateFilterSummary,
  videoCandidateFluorescenceFilterOptions,
  videoCandidateDetails,
  videoCandidateFluorescenceLabel,
  videoCandidateSourceUrl,
  videoCandidateTrainingFilterOptions,
  type VideoCandidateFluorescenceFilter,
  type VideoCandidateTrainingFilter,
} from "@/utils/videoCandidates";

// 本组件只负责左侧输入和参数 UI；真正的病例写入、分析和上传动作由父页面执行。
type ImageChannel = "white_light" | "fluorescence";
type UploadChannel = ImageChannel | "video";
type Colormap = "green" | "amber" | "magenta";

const emit = defineEmits<{
  "update:whiteLightPath": [value: string];
  "update:fluorescencePath": [value: string];
  "update:videoPath": [value: string];
  "update:videoTimepoints": [value: string];
  "update:alpha": [value: number];
  "update:threshold": [value: number];
  "update:colormap": [value: Colormap];
  filePicked: [channel: UploadChannel, event: Event];
  importInputs: [];
  importVideo: [];
  loadVideoCandidates: [];
  selectVideoCandidate: [recordId: string];
  importVideoCandidate: [];
  startCamera: [];
  stopCamera: [];
  importCamera: [];
  runAnalysis: [];
  runVideoFileAnalysis: [];
  runRealtimeVideo: [];
}>();

const props = defineProps<{
  whiteLightPath: string;
  fluorescencePath: string;
  videoPath: string;
  videoTimepoints: string;
  alpha: number;
  threshold: number;
  colormap: Colormap;
  loading: boolean;
  hasCase: boolean;
  isUploadingWhite: boolean;
  isUploadingFluorescence: boolean;
  isUploadingVideo: boolean;
  isLoadingVideoCandidates: boolean;
  isLoadingVideoPreview: boolean;
  selectedVideoCandidateId: string;
  selectedVideoCandidatePreviewSrc: string;
  videoCandidates: VideoCandidate[];
  cameraActive: boolean;
  cameraStatusLabel: string;
  isOpeningCamera: boolean;
  operationMessage: string;
  operationMessageType: "info" | "error";
  realtimeVideoActive: boolean;
}>();

const whiteLightFileInput = ref<HTMLInputElement | null>(null);
const fluorescenceFileInput = ref<HTMLInputElement | null>(null);
const videoFileInput = ref<HTMLInputElement | null>(null);
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

function openFilePicker(channel: UploadChannel) {
  if (channel === "white_light") {
    whiteLightFileInput.value?.click();
    return;
  }
  if (channel === "video") {
    videoFileInput.value?.click();
    return;
  }
  fluorescenceFileInput.value?.click();
}

function emitPath(kind: "white" | "fluorescence" | "video", event: Event) {
  const value = (event.target as HTMLInputElement).value;
  if (kind === "white") {
    emit("update:whiteLightPath", value);
    return;
  }
  if (kind === "fluorescence") {
    emit("update:fluorescencePath", value);
    return;
  }
  emit("update:videoPath", value);
}

function emitNumber(kind: "alpha" | "threshold", event: Event) {
  const value = Number((event.target as HTMLInputElement).value);
  if (kind === "alpha") {
    emit("update:alpha", value);
    return;
  }
  emit("update:threshold", value);
}

function emitColormap(event: Event) {
  emit("update:colormap", (event.target as HTMLSelectElement).value as Colormap);
}
</script>

<style scoped>
.left-sidebar {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.control-card {
  min-width: 0;
  border: 1px solid #d6e0eb;
  border-radius: 6px;
  padding: 9px 12px;
  background: #ffffff;
  box-shadow: 0 2px 12px rgba(39, 74, 106, 0.06);
}

.control-card :deep(.ov-section-heading) {
  margin-bottom: 8px;
  padding-bottom: 7px;
  border-bottom: 1px solid #e3ebf3;
}

.control-card :deep(.ov-section-heading__title) {
  color: #102136;
  font-size: 13px;
}

.control-card :deep(.ov-section-heading__eyebrow) {
  display: none;
}

.field {
  display: grid;
  gap: 4px;
  margin-bottom: 7px;
}

.field span {
  color: #6a7a8a;
  font-size: 12px;
  font-weight: 700;
}

.field input,
.field select {
  width: 100%;
  min-height: 30px;
  border: 1px solid #ccd8e5;
  border-radius: 5px;
  padding: 5px 8px;
  background: #fbfdff;
  color: #162020;
  font: inherit;
  font-size: 13px;
}

.field input:focus,
.field select:focus {
  outline: 2px solid rgba(30, 111, 166, 0.22);
  border-color: #2980b9;
}

.path-input {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 32px;
  gap: 6px;
}

.file-picker-button:disabled {
  cursor: progress;
}

.hidden-file-input {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  clip-path: inset(50%);
  white-space: nowrap;
}

.camera-input-panel {
  display: grid;
  gap: 6px;
  margin: 8px 0 7px;
  border: 1px solid #c7dceb;
  border-radius: 6px;
  padding: 7px 8px;
  background:
    linear-gradient(180deg, rgba(247, 252, 255, 0.98), rgba(236, 247, 255, 0.98)),
    #eef8ff;
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.9) inset,
    0 8px 18px rgba(20, 86, 138, 0.08);
}

.video-library-panel {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 116px;
  gap: 6px;
  align-items: center;
  margin: -1px 0 8px;
}

.video-library-panel select {
  width: 100%;
  min-height: 30px;
  border: 1px solid #ccd8e5;
  border-radius: 5px;
  padding: 5px 8px;
  background: #fbfdff;
  color: #162020;
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
  color: #6a7a8a;
  font-size: 11px;
  font-weight: 900;
}

.video-library-filters select {
  width: 100%;
  min-height: 28px;
  border: 1px solid #ccd8e5;
  border-radius: 5px;
  padding: 4px 7px;
  background: #fbfdff;
  color: #162020;
  font: inherit;
  font-size: 12px;
}

.video-candidate-card {
  display: grid;
  gap: 7px;
  margin: 0 0 8px;
  border: 1px solid #d2e2ef;
  border-radius: 6px;
  padding: 8px;
  background: #f8fcff;
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
  color: #102136;
  font-size: 12px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.candidate-card-header div > span {
  margin-top: 2px;
  color: #6a7a8a;
  font-size: 11px;
  overflow-wrap: anywhere;
}

.candidate-badge {
  border: 1px solid #d6e0eb;
  border-radius: 999px;
  padding: 3px 7px;
  background: #ffffff;
  color: #506070;
  font-size: 11px;
  font-weight: 900;
  white-space: nowrap;
}

.candidate-badge.fluorescent {
  border-color: #9bd7c2;
  background: #effcf8;
  color: #11724e;
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
  border: 1px solid #d6e0eb;
  border-radius: 5px;
  background: #eef5fa;
}

.candidate-preview img {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  object-fit: cover;
}

.candidate-preview figcaption {
  display: grid;
  min-height: 58px;
  place-items: center;
  color: #5f7080;
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
  color: #748494;
  font-weight: 900;
}

.candidate-detail-grid dd {
  margin: 0;
  color: #314151;
  overflow-wrap: anywhere;
}

.candidate-source-link {
  justify-self: start;
  color: #1e6fa6;
  font-size: 11px;
  font-weight: 900;
  text-decoration: none;
}

.candidate-source-link:hover {
  text-decoration: underline;
}

.camera-panel-header {
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr);
  gap: 8px;
  align-items: center;
}

.camera-panel-header :deep(.app-icon--tile) {
  width: 28px;
  height: 28px;
}

.camera-panel-copy strong,
.camera-panel-copy span {
  display: block;
  min-width: 0;
}

.camera-panel-copy strong {
  color: #102136;
  font-size: 12px;
  line-height: 1.3;
}

.camera-panel-copy span {
  margin-top: 2px;
  color: #5a6a7a;
  font-size: 11px;
  line-height: 1.35;
}

.camera-action-row {
  display: grid;
  grid-template-columns: 1fr 0.72fr 0.72fr;
  gap: 6px;
}

.input-action-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 0.86fr);
  gap: 7px;
}

.camera-action-row :deep(.app-button),
.camera-input-panel > :deep(.app-button) {
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.88) inset;
}

.analysis-action-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 7px;
  margin-top: 7px;
}

.camera-action-row :deep(.app-button),
.input-action-row :deep(.app-button),
.analysis-action-row :deep(.app-button) {
  min-width: 0;
  padding-right: 7px;
  padding-left: 7px;
}

.realtime-status,
.operation-message {
  border-radius: 5px;
  padding: 7px 9px;
  font-size: 11px;
  line-height: 1.45;
}

.realtime-status {
  margin: 6px 0 0;
  border: 1px solid #b8d9ed;
  background: #f2fbff;
  color: #285c7c;
}

.operation-message {
  margin: 8px 0 0;
  border: 1px solid #c7d8ea;
  background: #f6fbff;
  color: #315f86;
  overflow-wrap: anywhere;
}

.operation-message.error {
  border-color: #e7b7ab;
  background: #fff4f1;
  color: #a23b25;
}

.range-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 48px;
  gap: 7px;
  align-items: center;
}

.range-row input {
  accent-color: #1e6fa6;
}

.range-row output {
  min-height: 26px;
  border: 1px solid #d8e2ed;
  border-radius: 5px;
  padding: 4px 7px;
  background: #f8fbfe;
  color: #5a6a7a;
  font-size: 12px;
  text-align: center;
}
</style>
