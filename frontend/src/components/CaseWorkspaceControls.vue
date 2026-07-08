<template>
  <aside class="left-sidebar" aria-label="输入与分析控制">
    <section class="control-card">
      <SectionHeading icon="layers" title="官方 4K MP4 / JPEG 输入" />
      <label class="field file-field">
        <span>白光图像路径</span>
        <div class="path-input">
          <textarea
            ref="whiteLightPathTextarea"
            :value="whiteLightPath"
            rows="2"
            placeholder="D:\\data\\case_001\\white.jpg"
            @input="emitPath('white', $event)"
          ></textarea>
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
          <textarea
            ref="fluorescencePathTextarea"
            :value="fluorescencePath"
            rows="2"
            placeholder="D:\\data\\case_001\\icg.jpg"
            @input="emitPath('fluorescence', $event)"
          ></textarea>
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
          <textarea
            ref="videoPathTextarea"
            :value="videoPath"
            rows="2"
            placeholder="D:\\data\\case_001\\official_4k.mp4"
            @input="emitPath('video', $event)"
          ></textarea>
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
      <p class="control-group-label">上传与公开视频示例</p>
      <VideoCandidateSelectorPanel
        :loading="loading"
        :has-case="hasCase"
        :is-loading-video-candidates="isLoadingVideoCandidates"
        :is-loading-video-preview="isLoadingVideoPreview"
        :selected-video-candidate-id="selectedVideoCandidateId"
        :selected-video-candidate-preview-src="selectedVideoCandidatePreviewSrc"
        :video-candidates="videoCandidates"
        @load-video-candidates="emit('loadVideoCandidates')"
        @select-video-candidate="emit('selectVideoCandidate', $event)"
        @import-video-candidate="emit('importVideoCandidate')"
      />

      <p class="control-group-label">写入病例输入</p>
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
      <p class="control-group-label">运行分析流程</p>
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
      </div>
    </section>
  </aside>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from "vue";

import AppButton from "@/components/AppButton.vue";
import SectionHeading from "@/components/SectionHeading.vue";
import VideoCandidateSelectorPanel from "@/components/VideoCandidateSelectorPanel.vue";
import type { VideoCandidate } from "@/types/case";

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
  runAnalysis: [];
  runVideoFileAnalysis: [];
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
  operationMessage: string;
  operationMessageType: "info" | "error";
}>();

const whiteLightPathTextarea = ref<HTMLTextAreaElement | null>(null);
const fluorescencePathTextarea = ref<HTMLTextAreaElement | null>(null);
const videoPathTextarea = ref<HTMLTextAreaElement | null>(null);
const whiteLightFileInput = ref<HTMLInputElement | null>(null);
const fluorescenceFileInput = ref<HTMLInputElement | null>(null);
const videoFileInput = ref<HTMLInputElement | null>(null);

watch(
  () => [props.whiteLightPath, props.fluorescencePath, props.videoPath],
  async () => {
    await nextTick();
    resizePathTextareas();
  },
  { immediate: true },
);

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
  const target = event.target as HTMLTextAreaElement;
  resizePathTextarea(target);
  const value = target.value;
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

function resizePathTextareas() {
  resizePathTextarea(whiteLightPathTextarea.value);
  resizePathTextarea(fluorescencePathTextarea.value);
  resizePathTextarea(videoPathTextarea.value);
}

function resizePathTextarea(textarea: HTMLTextAreaElement | null) {
  if (!textarea) return;
  textarea.style.height = "auto";
  textarea.style.height = `${Math.max(42, textarea.scrollHeight + 4)}px`;
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
.field textarea,
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

.field textarea {
  min-height: 42px;
  line-height: 1.35;
  resize: none;
  overflow: hidden;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.field input:focus,
.field textarea:focus,
.field select:focus {
  outline: 2px solid rgba(30, 111, 166, 0.22);
  border-color: #2980b9;
}

.control-group-label {
  margin: 8px 0 5px;
  color: #1e6fa6;
  font-size: 11px;
  font-weight: 900;
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
}

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
  gap: 5px;
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
  overflow-wrap: anywhere;
  white-space: normal;
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

.input-action-row {
  display: grid;
  grid-template-columns: minmax(134px, 1fr) minmax(108px, 0.86fr);
  gap: 6px;
}

.analysis-action-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 5px;
  margin-top: 7px;
}

.video-library-actions :deep(.app-button),
.input-action-row :deep(.app-button),
.analysis-action-row :deep(.app-button) {
  min-width: 0;
  gap: 5px;
  padding-right: 6px;
  padding-left: 6px;
  font-size: 12px;
}

.video-library-actions :deep(.app-button__label),
.input-action-row :deep(.app-button__label),
.analysis-action-row :deep(.app-button__label) {
  flex: 0 1 auto;
  min-width: 0;
  overflow-wrap: anywhere;
  white-space: normal;
}

.video-library-actions :deep(.app-icon),
.input-action-row :deep(.app-icon),
.analysis-action-row :deep(.app-icon) {
  flex: 0 0 auto;
  width: 14px;
  height: 14px;
}

@media (max-width: 420px) {
  .input-action-row,
  .analysis-action-row {
    grid-template-columns: 1fr;
  }

  .video-library-actions :deep(.app-button),
  .input-action-row :deep(.app-button),
  .analysis-action-row :deep(.app-button) {
    min-height: 32px;
  }
}

.operation-message {
  border-radius: 5px;
  padding: 7px 9px;
  font-size: 11px;
  line-height: 1.45;
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
