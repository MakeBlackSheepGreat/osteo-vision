<template>
  <aside class="left-sidebar" aria-label="官方输入与分析控制">
    <section class="control-card">
      <SectionHeading icon="upload" title="官方设备输入" />
      <div class="input-source-tabs" role="tablist" aria-label="视频输入来源">
        <button
          type="button"
          :class="{ active: videoInputSource === 'file' }"
          role="tab"
          :aria-selected="videoInputSource === 'file'"
          @click="emit('update:videoInputSource', 'file')"
        >
          文件输入
        </button>
        <button
          type="button"
          :class="{ active: videoInputSource === 'camera' }"
          role="tab"
          :aria-selected="videoInputSource === 'camera'"
          @click="emit('update:videoInputSource', 'camera')"
        >
          浏览器摄像头
        </button>
      </div>

      <div v-show="videoInputSource === 'file'" class="input-mode-tabs" role="tablist" aria-label="输入类型">
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

      <div v-if="videoInputSource === 'file' && inputMode === 'video'" class="input-mode-panel" role="tabpanel">
        <div class="input-mode-heading">
          <strong>术中 MP4 视频</strong>
          <span>{{ multichannelSession ? "同步会话已准备" : videoReady ? "已导入病例" : "待选择文件" }}</span>
        </div>
        <div class="video-mode-tabs" role="tablist" aria-label="MP4 视频模式">
          <button
            v-for="mode in videoModes"
            :key="mode.value"
            type="button"
            role="tab"
            :class="{ active: videoMode === mode.value }"
            :aria-selected="videoMode === mode.value"
            @click="emit('update:videoMode', mode.value)"
          >
            {{ mode.label }}
          </button>
        </div>

        <template v-if="videoMode === 'single_video'">
          <div class="single-video-workspace">
            <div class="single-video-actions">
              <AppButton
                class="input-picker-action"
                variant="secondary"
                size="sm"
                icon="folder"
                block
                :disabled="loading || !hasCase || isUploadingVideo"
                :title="videoActionHint"
                @click="openFilePicker('video')"
              >
                {{ isUploadingVideo ? "正在导入 MP4" : videoPath ? "更换 MP4 视频" : "选择 MP4 视频" }}
              </AppButton>
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
            </div>
            <div class="selected-input-path" :title="videoPath || '尚未选择 MP4 文件'">
              <span>当前视频</span>
              <strong>{{ shortInputPath(videoPath) }}</strong>
            </div>
            <label class="field compact-field single-video-timepoints">
              <span>重点复核时间点（秒，可选）</span>
              <input
                :value="videoTimepoints"
                type="text"
                inputmode="decimal"
                placeholder="例如 0, 1.5, 3.0"
                @input="emit('update:videoTimepoints', ($event.target as HTMLInputElement).value)"
              />
            </label>
          </div>
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
        </template>

        <template v-else-if="videoMode === 'paired_videos'">
          <div class="multichannel-file-actions">
            <AppButton
              variant="secondary"
              size="sm"
              icon="folder"
              :disabled="loading || !hasCase || isUploadingVideo"
              @click="openFilePicker('video_white_light')"
            >
              {{ multichannelWhitePath ? "更换白光 MP4" : "选择白光 MP4" }}
            </AppButton>
            <AppButton
              variant="secondary"
              size="sm"
              icon="folder"
              :disabled="loading || !hasCase || isUploadingVideo"
              @click="openFilePicker('video_fluorescence')"
            >
              {{ multichannelFluorescencePath ? "更换荧光 MP4" : "选择荧光 MP4" }}
            </AppButton>
            <AppButton
              variant="secondary"
              size="sm"
              icon="folder"
              :disabled="loading || !hasCase || isUploadingVideo"
              @click="openFilePicker('video_device_overlay')"
            >
              {{ multichannelDeviceOverlayPath ? "更换设备叠加 MP4" : "可选设备叠加 MP4" }}
            </AppButton>
          </div>
          <dl class="image-pair-status">
            <div><dt>白光</dt><dd>{{ shortInputPath(multichannelWhitePath) }}</dd></div>
            <div><dt>荧光</dt><dd>{{ shortInputPath(multichannelFluorescencePath) }}</dd></div>
            <div><dt>设备叠加</dt><dd>{{ shortInputPath(multichannelDeviceOverlayPath) }}</dd></div>
          </dl>
        </template>

        <template v-else>
          <p class="multichannel-boundary">
            OFDVDnet 为公开非目标域荧光手术代理，三视图将受控拆分为白光、荧光和设备叠加视频。
          </p>
          <VideoCandidateSelectorPanel
            :loading="loading"
            :has-case="hasCase"
            :is-loading-video-candidates="isLoadingVideoCandidates"
            :is-loading-video-preview="isLoadingVideoPreview"
            :selected-video-candidate-id="selectedVideoCandidateId"
            :selected-video-candidate-preview-src="selectedVideoCandidatePreviewSrc"
            :video-candidates="compositeVideoCandidates"
            @load-video-candidates="emit('loadVideoCandidates')"
            @select-video-candidate="emit('selectVideoCandidate', $event)"
            @import-video-candidate="emit('importVideoCandidate')"
          />
        </template>

        <template v-if="videoMode !== 'single_video'">
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
          <div class="offset-grid">
            <label class="field compact-field">
              <span>荧光偏移（ms）</span>
              <input
                :value="fluorescenceOffsetMs"
                type="number"
                step="1"
                @input="emit('update:fluorescenceOffsetMs', Number(($event.target as HTMLInputElement).value))"
              />
            </label>
            <label class="field compact-field">
              <span>设备叠加偏移（ms）</span>
              <input
                :value="deviceOverlayOffsetMs"
                type="number"
                step="1"
                :disabled="!multichannelDeviceOverlayPath && videoMode !== 'composite_layout'"
                @input="emit('update:deviceOverlayOffsetMs', Number(($event.target as HTMLInputElement).value))"
              />
            </label>
          </div>
          <AppButton variant="ghost" size="sm" icon="load" block @click="emit('resetMultichannelOffsets')">
            复位自动偏移
          </AppButton>
          <dl v-if="multichannelSession" class="multichannel-session-status">
            <div><dt>同步状态</dt><dd>{{ synchronizationStatusLabel }}</dd></div>
            <div><dt>共同区间</dt><dd>{{ commonIntervalLabel }}</dd></div>
            <div><dt>起始时间差</dt><dd>{{ initialDeltaLabel }}</dd></div>
            <div><dt>配准可用</dt><dd>{{ multichannelSession.analysis_allowed ? "可运行" : "不可运行" }}</dd></div>
          </dl>
          <AppButton
            variant="secondary"
            size="sm"
            icon="layers"
            block
            :disabled="multichannelPrepareDisabled"
            @click="emit('prepareMultichannelSession')"
          >
            {{ multichannelPreparing ? "正在准备同步预览" : "准备同步预览" }}
          </AppButton>
          <AppButton
            variant="primary"
            size="sm"
            icon="play"
            block
            :disabled="loading || analysisJobPolling || !multichannelSession?.analysis_allowed"
            @click="emit('runMultichannelAnalysis')"
          >
            运行双通道融合分析
          </AppButton>
        </template>
      </div>

      <div v-else-if="videoInputSource === 'file'" class="input-mode-panel" role="tabpanel">
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
        data-testid="single-video-file-input"
        class="hidden-file-input"
        type="file"
        accept="video/mp4,.mp4"
        @change="emit('filePicked', 'video', $event)"
      />
      <input
        ref="whiteVideoFileInput"
        data-testid="white-light-video-file-input"
        class="hidden-file-input"
        type="file"
        accept="video/mp4,.mp4"
        @change="emit('filePicked', 'video_white_light', $event)"
      />
      <input
        ref="fluorescenceVideoFileInput"
        data-testid="fluorescence-video-file-input"
        class="hidden-file-input"
        type="file"
        accept="video/mp4,.mp4"
        @change="emit('filePicked', 'video_fluorescence', $event)"
      />
      <input
        ref="deviceOverlayVideoFileInput"
        data-testid="device-overlay-video-file-input"
        class="hidden-file-input"
        type="file"
        accept="video/mp4,.mp4"
        @change="emit('filePicked', 'video_device_overlay', $event)"
      />
    </section>

    <section v-if="videoInputSource === 'camera'" class="control-card live-stream-control-card">
      <SectionHeading icon="camera" icon-tone="cyan" title="单路浏览器摄像头" />
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
        <template v-if="cameraActive">
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
        <p v-else class="camera-control-note">连接摄像头后可抓取关键帧或启动连续实时分割。</p>
      </div>
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
  </aside>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";

import AppButton from "@/components/AppButton.vue";
import SectionHeading from "@/components/SectionHeading.vue";
import VideoCandidateSelectorPanel from "@/components/VideoCandidateSelectorPanel.vue";
import type { MultichannelVideoMode, MultichannelVideoSession, VideoCandidate } from "@/types/case";

type ImageChannel = "white_light" | "fluorescence" | "device_overlay";
type UploadChannel = ImageChannel | "video" | "video_white_light" | "video_fluorescence" | "video_device_overlay";
type Colormap = "green" | "amber" | "magenta";
type InputMode = "video" | "images";
type VideoInputSource = "file" | "camera";

const emit = defineEmits<{
  "update:videoInputSource": [value: VideoInputSource];
  "update:inputMode": [value: InputMode];
  "update:videoMode": [value: MultichannelVideoMode];
  "update:videoTimepoints": [value: string];
  "update:fluorescenceOffsetMs": [value: number];
  "update:deviceOverlayOffsetMs": [value: number];
  "update:alpha": [value: number];
  "update:threshold": [value: number];
  "update:colormap": [value: Colormap];
  filePicked: [channel: UploadChannel, event: Event];
  loadVideoCandidates: [];
  selectVideoCandidate: [recordId: string];
  importVideoCandidate: [];
  runAnalysis: [];
  runVideoFileAnalysis: [];
  prepareMultichannelSession: [];
  runMultichannelAnalysis: [];
  resetMultichannelOffsets: [];
  startCamera: [];
  stopCamera: [];
  captureCameraFrame: [];
  startContinuousCameraAnalysis: [];
  stopContinuousCameraAnalysis: [];
  updateCameraAnalysisInterval: [intervalSec: number];
  selectImagePair: [pairKey: string];
}>();

const props = withDefaults(defineProps<{
  videoInputSource?: VideoInputSource;
  inputMode: InputMode;
  videoMode?: MultichannelVideoMode;
  whiteLightPath: string;
  fluorescencePath: string;
  deviceOverlayPath?: string;
  videoPath: string;
  multichannelWhitePath?: string;
  multichannelFluorescencePath?: string;
  multichannelDeviceOverlayPath?: string;
  multichannelSession?: MultichannelVideoSession | null;
  multichannelPreparing?: boolean;
  fluorescenceOffsetMs?: number | null;
  deviceOverlayOffsetMs?: number | null;
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
  liveSessionReady: boolean;
}>(), {
  deviceOverlayPath: "",
  isUploadingDeviceOverlay: false,
  multichannelWhitePath: "",
  multichannelFluorescencePath: "",
  multichannelDeviceOverlayPath: "",
  multichannelSession: null,
  multichannelPreparing: false,
  fluorescenceOffsetMs: 0,
  deviceOverlayOffsetMs: 0,
  videoMode: "single_video",
  videoInputSource: "file",
});

const whiteLightFileInput = ref<HTMLInputElement | null>(null);
const fluorescenceFileInput = ref<HTMLInputElement | null>(null);
const deviceOverlayFileInput = ref<HTMLInputElement | null>(null);
const videoFileInput = ref<HTMLInputElement | null>(null);
const whiteVideoFileInput = ref<HTMLInputElement | null>(null);
const fluorescenceVideoFileInput = ref<HTMLInputElement | null>(null);
const deviceOverlayVideoFileInput = ref<HTMLInputElement | null>(null);
const videoModes: Array<{ value: MultichannelVideoMode; label: string }> = [
  { value: "single_video", label: "单路视频" },
  { value: "paired_videos", label: "双通道视频" },
  { value: "composite_layout", label: "合成三视图" },
];
const compositeVideoCandidates = computed(() =>
  props.videoCandidates.filter((candidate) => candidate.composite_layout_available),
);
const multichannelPrepareDisabled = computed(() => {
  if (props.loading || props.multichannelPreparing || !props.hasCase || props.isUploadingVideo) return true;
  if (props.videoMode === "paired_videos") {
    return !props.multichannelWhitePath || !props.multichannelFluorescencePath;
  }
  return !props.selectedVideoCandidateId || !compositeVideoCandidates.value.some(
    (candidate) => candidate.record_id === props.selectedVideoCandidateId,
  );
});
const synchronizationStatusLabel = computed(() => {
  if (!props.multichannelSession) return "未准备";
  if (props.multichannelSession.synchronization_status === "aligned") return "已对齐";
  if (props.multichannelSession.synchronization_status === "review_required") return "需要复核";
  return "不可用";
});
const commonIntervalLabel = computed(() => {
  const session = props.multichannelSession;
  if (!session || session.common_start_sec == null || session.common_end_sec == null) return "未计算";
  return `${session.common_start_sec.toFixed(2)}–${session.common_end_sec.toFixed(2)} s`;
});
const initialDeltaLabel = computed(() => {
  const value = props.multichannelSession?.initial_time_delta_ms;
  return typeof value === "number" ? `${value.toFixed(2)} ms` : "未计算";
});
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
  if (channel === "video_white_light") {
    whiteVideoFileInput.value?.click();
    return;
  }
  if (channel === "video_fluorescence") {
    fluorescenceVideoFileInput.value?.click();
    return;
  }
  if (channel === "video_device_overlay") {
    deviceOverlayVideoFileInput.value?.click();
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

.input-source-tabs,
.input-mode-tabs {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 5px;
  margin-bottom: 10px;
}

.input-source-tabs button,
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

.input-source-tabs button.active,
.input-mode-tabs button.active {
  border-color: var(--ov-border-accent);
  background: var(--ov-bg-info);
  color: var(--ov-primary);
}

.input-source-tabs button:focus-visible,
.input-mode-tabs button:focus-visible,
.video-mode-tabs button:focus-visible,
.video-example-details summary:focus-visible {
  outline: 2px solid var(--ov-border-accent);
  outline-offset: 2px;
}

.video-mode-tabs {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 4px;
  border: 1px solid var(--ov-border);
  border-radius: 5px;
  padding: 4px;
  background: var(--ov-bg-soft);
}

.video-mode-tabs button {
  min-width: 0;
  min-height: 36px;
  border: 0;
  border-radius: 3px;
  padding: 5px 6px;
  background: transparent;
  color: var(--ov-text-secondary);
  font: inherit;
  font-size: 11px;
  font-weight: 750;
  line-height: 1.3;
  white-space: normal;
  cursor: pointer;
}

.video-mode-tabs button.active {
  background: var(--ov-primary);
  color: var(--ov-text-on-primary);
  box-shadow: none;
}

.multichannel-file-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
}

.multichannel-file-actions :deep(.app-button) {
  min-height: 44px;
  justify-content: flex-start;
  text-align: left;
}

.offset-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 7px;
}

.multichannel-boundary {
  margin: 0;
  border-left: 3px solid var(--ov-warning);
  padding: 7px 9px;
  background: var(--ov-bg-warning);
  color: var(--ov-text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.multichannel-session-status {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  margin: 0;
  overflow: hidden;
  border: 1px solid var(--ov-border);
  border-radius: 5px;
  background: var(--ov-border);
}

.multichannel-session-status div {
  min-width: 0;
  padding: 6px 7px;
  background: var(--ov-bg-soft);
}

.multichannel-session-status dt,
.multichannel-session-status dd {
  margin: 0;
  overflow-wrap: anywhere;
}

.multichannel-session-status dt {
  color: var(--ov-text-muted);
  font-size: 10px;
}

.multichannel-session-status dd {
  margin-top: 2px;
  color: var(--ov-text);
  font-size: 11px;
  font-weight: 750;
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

.single-video-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(112px, 0.78fr);
  gap: 7px;
  align-items: end;
}

.single-video-actions {
  display: grid;
  grid-column: 1 / -1;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 7px;
}

.single-video-actions :deep(.app-button) {
  min-width: 0;
  min-height: 38px;
  justify-content: center;
  padding-right: 7px;
  padding-left: 7px;
  text-align: center;
}

.selected-input-path {
  display: grid;
  gap: 3px;
  min-width: 0;
  min-height: 36px;
  margin: 0;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 5px;
  padding: 6px 8px;
  background: var(--ov-bg-soft);
  color: var(--ov-text-secondary);
  line-height: 1.35;
}

.selected-input-path span {
  color: var(--ov-text-muted);
  font-size: 10px;
  font-weight: 800;
}

.selected-input-path strong {
  min-width: 0;
  color: var(--ov-text-secondary);
  font-size: 11px;
  overflow-wrap: anywhere;
}

.single-video-timepoints {
  min-width: 0;
}

.single-video-timepoints span {
  font-size: 10px;
}

.single-video-timepoints input {
  min-height: 36px;
  font-size: 11px;
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
