<template>
  <aside class="left-sidebar" aria-label="官方输入与分析控制">
    <section class="control-card">
      <SectionHeading icon="upload" title="官方设备输入" />
      <div class="input-mode-tabs" role="tablist" aria-label="输入类型">
        <button
          type="button"
          :class="{ active: inputMode === 'video' }"
          role="tab"
          :aria-selected="inputMode === 'video'"
          @click="emit('update:inputMode', 'video')"
        >
          MP4 视频
        </button>
        <button
          type="button"
          :class="{ active: inputMode === 'images' }"
          role="tab"
          :aria-selected="inputMode === 'images'"
          @click="emit('update:inputMode', 'images')"
        >
          JPEG 图像
        </button>
      </div>

      <div v-if="inputMode === 'video'" class="input-mode-panel" role="tabpanel">
        <div class="input-mode-heading">
          <strong>术中 MP4 视频</strong>
          <span>{{ videoReady ? "已导入病例" : "待选择文件" }}</span>
        </div>
        <AppButton
          class="input-picker-action"
          variant="primary"
          size="sm"
          icon="folder"
          block
          :disabled="loading || !hasCase || isUploadingVideo"
          :title="videoActionHint"
          @click="openFilePicker('video')"
        >
          {{ isUploadingVideo ? "正在导入 MP4" : videoPath ? "更换 MP4 视频" : "选择 MP4 视频" }}
        </AppButton>
        <p class="selected-input-path">{{ videoPath || "尚未选择 MP4 文件" }}</p>
        <label class="field compact-field">
          <span>重点复核时间点（秒，可选）</span>
          <input
            :value="videoTimepoints"
            type="text"
            inputmode="decimal"
            placeholder="例如 0, 1.5, 3.0"
            @input="emit('update:videoTimepoints', ($event.target as HTMLInputElement).value)"
          />
        </label>
        <AppButton
          variant="primary"
          size="sm"
          icon="play"
          block
          :disabled="loading || analysisJobPolling || !hasCase || !videoReady"
          :title="videoActionHint"
          @click="emit('runVideoFileAnalysis')"
        >
          启动离线关键帧分析
        </AppButton>
        <details class="video-example-details">
          <summary>导入公开视频示例</summary>
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
        </details>
      </div>

      <div v-else class="input-mode-panel" role="tabpanel">
        <div class="input-mode-heading">
          <strong>白光与 ICG JPEG 图像对</strong>
          <span>{{ imagePairReady ? "已导入病例" : "待选择图像" }}</span>
        </div>
        <label v-if="imagePairOptions.length" class="field compact-field image-pair-selector">
          <span>已准入同步图像对</span>
          <select
            :value="selectedImagePairKey"
            aria-label="已准入同步 JPEG 图像对"
            @change="emitSelectedImagePair"
          >
            <option value="" disabled>选择 pair_id</option>
            <option v-for="pair in imagePairOptions" :key="pair.key" :value="pair.key">
              {{ pair.label }}
            </option>
          </select>
        </label>
        <div class="image-pair-actions">
          <AppButton
            variant="secondary"
            size="sm"
            icon="folder"
            :disabled="loading || !hasCase || isUploadingWhite"
            :title="imageActionHint"
            @click="openFilePicker('white_light')"
          >
            {{ isUploadingWhite ? "正在导入白光" : whiteLightPath ? "更换白光 JPEG" : "选择白光 JPEG" }}
          </AppButton>
          <AppButton
            variant="secondary"
            size="sm"
            icon="folder"
            :disabled="loading || !hasCase || isUploadingFluorescence"
            :title="imageActionHint"
            @click="openFilePicker('fluorescence')"
          >
            {{ isUploadingFluorescence ? "正在导入 ICG" : fluorescencePath ? "更换 ICG JPEG" : "选择 ICG JPEG" }}
          </AppButton>
          <AppButton
            variant="secondary"
            size="sm"
            icon="folder"
            :disabled="loading || !hasCase || isUploadingDeviceOverlay"
            title="设备叠加图仅用于显示、质控和证据核对，不参与模型推理。"
            @click="openFilePicker('device_overlay')"
          >
            {{ isUploadingDeviceOverlay ? "正在导入叠加图" : deviceOverlayPath ? "更换设备叠加 JPEG" : "选择设备叠加 JPEG" }}
          </AppButton>
        </div>
        <dl class="image-pair-status">
          <div>
            <dt>白光</dt>
            <dd>{{ shortInputPath(whiteLightPath) }}</dd>
          </div>
          <div>
            <dt>ICG 荧光</dt>
            <dd>{{ shortInputPath(fluorescencePath) }}</dd>
          </div>
          <div>
            <dt>设备叠加</dt>
            <dd>{{ shortInputPath(deviceOverlayPath) }}</dd>
          </div>
        </dl>
        <AppButton
          variant="primary"
          size="sm"
          icon="play"
          block
          :disabled="loading || analysisJobPolling || !hasCase || !imagePairReady"
          :title="imageActionHint"
          @click="emit('runAnalysis')"
        >
          开始图像融合分析
        </AppButton>
      </div>

      <p v-if="operationMessage" class="operation-message" :class="{ error: operationMessageType === 'error' }">
        {{ operationMessage }}
      </p>
      <input
        ref="whiteLightFileInput"
        class="hidden-file-input"
        type="file"
        accept=".jpg,.jpeg,image/jpeg"
        @change="emit('filePicked', 'white_light', $event)"
      />
      <input
        ref="fluorescenceFileInput"
        class="hidden-file-input"
        type="file"
        accept=".jpg,.jpeg,image/jpeg"
        @change="emit('filePicked', 'fluorescence', $event)"
      />
      <input
        ref="deviceOverlayFileInput"
        class="hidden-file-input"
        type="file"
        accept=".jpg,.jpeg,image/jpeg"
        @change="emit('filePicked', 'device_overlay', $event)"
      />
      <input
        ref="videoFileInput"
        class="hidden-file-input"
        type="file"
        accept="video/mp4,.mp4"
        @change="emit('filePicked', 'video', $event)"
      />
    </section>

    <section class="control-card analysis-parameter-card">
      <SectionHeading icon="target" icon-tone="cyan" title="分析参数" />
      <label v-if="inputMode === 'images'" class="field range-field">
        <span>融合透明度</span>
        <div class="range-row">
          <input :value="alpha" type="range" min="0" max="1" step="0.05" @input="emitNumber('alpha', $event)" />
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
    </section>

    <section class="control-card live-stream-control-card">
      <SectionHeading icon="camera" icon-tone="cyan" title="实时视频流控制" />
      <div class="camera-control-status" aria-live="polite">
        <strong>{{ cameraActive ? "摄像头已连接" : "摄像头未连接" }}</strong>
        <span>{{ cameraStatusLabel }}</span>
      </div>
      <div class="camera-control-actions">
        <AppButton
          v-if="!cameraActive"
          variant="secondary"
          size="sm"
          icon="camera"
          block
          :disabled="cameraOpening"
          @click="emit('startCamera')"
        >
          {{ cameraOpening ? "请求摄像头权限中" : "开启摄像头" }}
        </AppButton>
        <template v-if="cameraActive && !fileVideoActive">
          <AppButton
            variant="ghost"
            size="sm"
            icon="close"
            block
            @click="emit('stopCamera')"
          >
            关闭摄像头
          </AppButton>
          <AppButton
            variant="secondary"
            size="sm"
            icon="play"
            block
            :disabled="manualCameraAnalysisDisabled"
            :title="manualCameraAnalysisHint"
            :aria-busy="cameraManualAnalysisBusy"
            @click="emit('captureCameraFrame')"
          >
            {{ manualCameraAnalysisLabel }}
          </AppButton>
          <label class="field compact-field camera-interval-control">
            <span>下一帧等待</span>
            <select
              :value="cameraAnalysisIntervalSec"
              :disabled="cameraContinuousAnalysisActive"
              aria-label="连续关键帧采样间隔"
              @change="emitCameraAnalysisInterval"
            >
              <option :value="0">推理完成后立即继续</option>
              <option :value="1">1 秒</option>
              <option :value="2">2 秒</option>
              <option :value="3">3 秒</option>
              <option :value="5">5 秒</option>
              <option :value="10">10 秒</option>
            </select>
          </label>
          <AppButton
            v-if="!cameraContinuousAnalysisActive"
            variant="primary"
            size="sm"
            icon="play"
            block
            :disabled="continuousCameraAnalysisStartDisabled"
            :title="continuousCameraAnalysisHint"
            :aria-busy="cameraContinuousAnalysisStarting"
            @click="emit('startContinuousCameraAnalysis')"
          >
            开始实时分割
          </AppButton>
          <AppButton
            v-else
            variant="ghost"
            size="sm"
            icon="close"
            block
            @click="emit('stopContinuousCameraAnalysis')"
          >
            停止实时分割
          </AppButton>
          <p class="camera-control-note">{{ cameraContinuousAnalysisStatus }}</p>
        </template>
        <template v-else-if="cameraActive && fileVideoActive">
          <AppButton
            variant="ghost"
            size="sm"
            icon="close"
            block
            @click="emit('stopCamera')"
          >
            关闭摄像头
          </AppButton>
          <p class="camera-control-note">
            {{ videoRealtimeAnalysisStatus || "MP4 播放后将自动启动逐帧实时分割。" }}
          </p>
        </template>
        <template v-else-if="fileVideoActive">
          <p class="camera-control-note">
            {{ videoRealtimeAnalysisStatus || "MP4 播放后将自动启动逐帧实时分割。" }}
          </p>
        </template>
        <p v-else class="camera-control-note">连接摄像头后可抓取关键帧或启动连续实时分割。</p>
      </div>
    </section>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";

import AppButton from "@/components/AppButton.vue";
import SectionHeading from "@/components/SectionHeading.vue";
import VideoCandidateSelectorPanel from "@/components/VideoCandidateSelectorPanel.vue";
import type { VideoCandidate } from "@/types/case";

type ImageChannel = "white_light" | "fluorescence" | "device_overlay";
type UploadChannel = ImageChannel | "video";
type Colormap = "green" | "amber" | "magenta";
type InputMode = "video" | "images";

const emit = defineEmits<{
  "update:inputMode": [value: InputMode];
  "update:videoTimepoints": [value: string];
  "update:alpha": [value: number];
  "update:threshold": [value: number];
  "update:colormap": [value: Colormap];
  filePicked: [channel: UploadChannel, event: Event];
  loadVideoCandidates: [];
  selectVideoCandidate: [recordId: string];
  importVideoCandidate: [];
  runAnalysis: [];
  runVideoFileAnalysis: [];
  startCamera: [];
  stopCamera: [];
  captureCameraFrame: [];
  startContinuousCameraAnalysis: [];
  stopContinuousCameraAnalysis: [];
  updateCameraAnalysisInterval: [intervalSec: number];
  selectImagePair: [pairKey: string];
}>();

const props = withDefaults(defineProps<{
  inputMode: InputMode;
  whiteLightPath: string;
  fluorescencePath: string;
  deviceOverlayPath?: string;
  videoPath: string;
  videoTimepoints: string;
  alpha: number;
  threshold: number;
  colormap: Colormap;
  loading: boolean;
  hasCase: boolean;
  isUploadingWhite: boolean;
  isUploadingFluorescence: boolean;
  isUploadingDeviceOverlay?: boolean;
  isUploadingVideo: boolean;
  isLoadingVideoCandidates: boolean;
  isLoadingVideoPreview: boolean;
  selectedVideoCandidateId: string;
  selectedVideoCandidatePreviewSrc: string;
  videoCandidates: VideoCandidate[];
  operationMessage: string;
  operationMessageType: "info" | "error";
  imagePairReady: boolean;
  imagePairOptions: Array<{ key: string; label: string }>;
  selectedImagePairKey: string;
  analysisJobPolling: boolean;
  videoReady: boolean;
  cameraActive: boolean;
  cameraOpening: boolean;
  cameraManualAnalysisBusy: boolean;
  cameraAnalysisRunning: boolean;
  cameraContinuousAnalysisStarting: boolean;
  cameraContinuousAnalysisActive: boolean;
  cameraAnalysisIntervalSec: number;
  cameraContinuousAnalysisStatus: string;
  cameraStatusLabel: string;
  fileVideoActive: boolean;
  videoRealtimeAnalysisStatus?: string;
  liveSessionReady: boolean;
}>(), { deviceOverlayPath: "", isUploadingDeviceOverlay: false });

const whiteLightFileInput = ref<HTMLInputElement | null>(null);
const fluorescenceFileInput = ref<HTMLInputElement | null>(null);
const deviceOverlayFileInput = ref<HTMLInputElement | null>(null);
const videoFileInput = ref<HTMLInputElement | null>(null);
const imageActionHint = computed(() => {
  if (!props.hasCase) return "请先在“病例档案”中新建或加载病例。";
  if (!props.whiteLightPath || !props.fluorescencePath) return "请依次选择白光 JPEG 与 ICG 荧光 JPEG。";
  if (!props.imagePairReady) return "图像上传完成后正在写入病例。";
  return "运行白光与 ICG 图像融合分析。";
});
const videoActionHint = computed(() => {
  if (!props.hasCase) return "请先在“病例档案”中新建或加载病例。";
  if (!props.videoPath) return "请选择显微镜导出的 MP4 视频。";
  if (!props.videoReady) return "MP4 上传完成后正在写入病例。";
  return "运行 MP4 离线关键帧分析；播放 MP4 时会自动启动逐帧实时分割。";
});
const manualCameraAnalysisDisabled = computed(
  () =>
    props.cameraManualAnalysisBusy ||
    props.cameraContinuousAnalysisStarting ||
    props.cameraContinuousAnalysisActive ||
    props.cameraAnalysisRunning,
);
const manualCameraAnalysisLabel = computed(() => {
  if (props.cameraManualAnalysisBusy) return "关键帧分析中";
  if (props.cameraContinuousAnalysisStarting) return "实时分割启动中";
  if (props.cameraContinuousAnalysisActive || props.cameraAnalysisRunning) return "连续分析运行中";
  return "抓取关键帧分析";
});
const manualCameraAnalysisHint = computed(() => {
  if (props.cameraManualAnalysisBusy) return "当前手工关键帧请求仍在处理，请等待完成。";
  if (props.cameraContinuousAnalysisStarting) return "连续实时分割正在启动，暂时无法手工抓帧。";
  if (props.cameraContinuousAnalysisActive || props.cameraAnalysisRunning) {
    return "请先停止连续实时分割，再抓取手工关键帧。";
  }
  return "抓取当前摄像头画面并运行一次分割分析。";
});
const continuousCameraAnalysisStartDisabled = computed(
  () => props.cameraManualAnalysisBusy || props.cameraContinuousAnalysisStarting || props.cameraAnalysisRunning,
);
const continuousCameraAnalysisHint = computed(() => {
  if (props.cameraManualAnalysisBusy) return "当前手工关键帧请求仍在处理，完成后可启动连续实时分割。";
  if (props.cameraContinuousAnalysisStarting) return "连续实时分割正在启动。";
  if (props.cameraAnalysisRunning) return "当前连续帧仍在处理中。";
  return props.liveSessionReady ? "开始连续实时分割。" : "点击后将自动建立实时视频会话并开始连续分割。";
});

function openFilePicker(channel: UploadChannel) {
  if (channel === "white_light") {
    whiteLightFileInput.value?.click();
    return;
  }
  if (channel === "fluorescence") {
    fluorescenceFileInput.value?.click();
    return;
  }
  if (channel === "device_overlay") {
    deviceOverlayFileInput.value?.click();
    return;
  }
  videoFileInput.value?.click();
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

function emitCameraAnalysisInterval(event: Event) {
  emit("updateCameraAnalysisInterval", Number((event.target as HTMLSelectElement).value));
}

function emitSelectedImagePair(event: Event) {
  emit("selectImagePair", (event.target as HTMLSelectElement).value);
}

function shortInputPath(path: string): string {
  if (!path) return "未选择";
  const normalized = path.replace(/\\/g, "/");
  return normalized.split("/").at(-1) || path;
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
  border: 1px solid var(--ov-border);
  border-radius: 6px;
  padding: 12px;
  background: var(--ov-bg-elevated);
  box-shadow: var(--ov-shadow);
}

.control-card :deep(.ov-section-heading) {
  margin-bottom: 8px;
  padding-bottom: 7px;
  border-bottom: 1px solid var(--ov-border-subtle);
}

.control-card :deep(.ov-section-heading__title) {
  color: var(--ov-text);
  font-size: 14px;
}

.control-card :deep(.ov-section-heading__eyebrow) {
  display: none;
}

.input-mode-tabs {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 5px;
  margin-bottom: 10px;
}

.input-mode-tabs button {
  min-height: 34px;
  border: 1px solid var(--ov-border-strong);
  border-radius: 5px;
  background: var(--ov-bg-soft);
  color: var(--ov-text-secondary);
  font: inherit;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

.input-mode-tabs button.active {
  border-color: var(--ov-border-accent);
  background: var(--ov-bg-info);
  color: var(--ov-primary);
}

.input-mode-tabs button:focus-visible,
.video-example-details summary:focus-visible {
  outline: 2px solid var(--ov-border-accent);
  outline-offset: 2px;
}

.input-mode-panel {
  display: grid;
  gap: 9px;
}

.input-mode-heading {
  display: flex;
  gap: 8px;
  align-items: baseline;
  justify-content: space-between;
  min-width: 0;
}

.input-mode-heading strong {
  min-width: 0;
  color: var(--ov-text);
  font-size: 13px;
}

.input-mode-heading span {
  color: var(--ov-text-muted);
  font-size: 11px;
  font-weight: 700;
  text-align: right;
}

.input-picker-action {
  justify-content: flex-start;
}

.selected-input-path {
  min-height: 33px;
  margin: -2px 0 0;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 5px;
  padding: 7px 8px;
  background: var(--ov-bg-soft);
  color: var(--ov-text-secondary);
  font-size: 11px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.image-pair-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
}

.image-pair-actions :deep(.app-button) {
  min-height: 46px;
  align-items: flex-start;
  justify-content: flex-start;
  text-align: left;
}

.image-pair-status {
  display: grid;
  gap: 5px;
  margin: 0;
}

.image-pair-status div {
  display: grid;
  grid-template-columns: 74px minmax(0, 1fr);
  gap: 7px;
  min-width: 0;
  border-bottom: 1px solid var(--ov-border-subtle);
  padding: 4px 0;
}

.image-pair-status dt,
.image-pair-status dd {
  margin: 0;
}

.image-pair-status dt {
  color: var(--ov-text-muted);
  font-size: 11px;
  font-weight: 800;
}

.image-pair-status dd {
  min-width: 0;
  color: var(--ov-text-secondary);
  font-size: 11px;
  font-weight: 700;
  overflow-wrap: anywhere;
}

.field {
  display: grid;
  gap: 5px;
}

.field span {
  color: var(--ov-text-muted);
  font-size: 12px;
  font-weight: 700;
}

.field input,
.field select {
  width: 100%;
  min-height: 36px;
  border: 1px solid var(--ov-border-strong);
  border-radius: 5px;
  padding: 5px 8px;
  background: var(--ov-bg-elevated);
  color: var(--ov-text);
  font: inherit;
  font-size: 13px;
}

.field input:focus,
.field select:focus {
  outline: 2px solid var(--ov-border-accent);
  border-color: var(--ov-border-accent);
}

.compact-field {
  margin-top: 1px;
}

.range-field {
  margin-bottom: 10px;
}

.analysis-parameter-card .range-field:last-child {
  margin-bottom: 0;
}

.range-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 44px;
  gap: 8px;
  align-items: center;
}

.range-row output {
  border: 1px solid var(--ov-border-subtle);
  border-radius: 5px;
  padding: 5px;
  color: var(--ov-primary);
  font-size: 12px;
  font-weight: 800;
  text-align: center;
}

.video-example-details {
  border-top: 1px solid var(--ov-border-subtle);
  padding-top: 8px;
}

.video-example-details summary {
  cursor: pointer;
  color: var(--ov-primary-strong);
  font-size: 12px;
  font-weight: 800;
  list-style: none;
}

.video-example-details summary::after {
  float: right;
  color: var(--ov-text-muted);
  content: "展开";
}

.video-example-details[open] summary {
  margin-bottom: 8px;
}

.video-example-details[open] summary::after {
  content: "收起";
}

.operation-message {
  margin: 9px 0 0;
  border-left: 3px solid var(--ov-border-accent);
  padding: 5px 0 5px 8px;
  color: var(--ov-text-secondary);
  font-size: 12px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.operation-message.error {
  border-color: var(--ov-danger);
  color: var(--ov-danger);
}

.hidden-file-input {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  clip-path: inset(50%);
}

.live-stream-control-card {
  display: grid;
  gap: 9px;
}

.camera-control-status {
  display: grid;
  gap: 3px;
  min-width: 0;
  border-left: 3px solid var(--ov-border-accent);
  padding: 3px 0 3px 8px;
}

.camera-control-status strong {
  color: var(--ov-text);
  font-size: 12px;
}

.camera-control-status span,
.camera-control-note {
  min-width: 0;
  margin: 0;
  color: var(--ov-text-secondary);
  font-size: 11px;
  font-weight: 700;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.camera-control-actions {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.camera-interval-control {
  gap: 5px;
}
</style>
