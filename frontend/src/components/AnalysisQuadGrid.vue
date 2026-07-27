<template>
  <div :class="gridClass" aria-label="术中影像与分析结果">
    <article class="analysis-quad-card analysis-quad-card--camera">
      <header>
        <AppIcon name="camera" />
        <span>{{ streamTitle }}</span>
        <strong :class="{ active: streamActive }">{{ streamBadge }}</strong>
      </header>
      <div
        class="analysis-quad-viewport camera-viewport"
        :class="{
          active: streamActive,
          'has-file-video': fileVideoActive,
          'has-live-overlay': Boolean(liveOverlaySrc) && !hasLiveInference,
          'is-empty': !streamActive,
        }"
      >
        <video v-show="!fileVideoActive" ref="cameraVideoRef" class="camera-live-player" muted autoplay playsinline></video>
        <video
          v-if="fileVideoActive"
          ref="playbackVideoRef"
          class="video-stream-player"
          :src="videoPlayback?.videoSrc"
          controls
          preload="metadata"
          playsinline
          crossorigin="anonymous"
          @loadedmetadata="emitPlaybackState"
          @timeupdate="emitPlaybackState"
          @seeked="handlePlaybackSeeked"
          @play="emit('playbackStarted')"
          @pause="handlePlaybackPaused"
          @ended="emit('playbackEnded')"
        ></video>
        <img
          v-if="liveOverlaySrc && !hasLiveInference"
          class="live-segmentation-overlay"
          :src="liveOverlaySrc"
          alt="当前实时分割叠加"
        />
        <div v-if="liveFrameStatus && !hasLiveInference" class="live-frame-status" aria-live="polite">
          <strong>{{ liveFrameStatus }}</strong>
          <span v-if="liveModelLatencyMs !== null">模型 {{ Math.round(liveModelLatencyMs) }} ms</span>
          <span v-if="liveEndToEndLatencyMs !== null">端到端 {{ Math.round(liveEndToEndLatencyMs) }} ms</span>
        </div>
        <div v-if="!streamActive" class="empty-preview-copy">
          <strong>等待视频流</strong>
          <span>{{ cameraStatusLabel }}</span>
        </div>
      </div>
      <p>{{ streamFooterLabel }}</p>
    </article>

    <article v-if="hasLiveInference" class="analysis-quad-card analysis-quad-card--inference">
      <header>
        <AppIcon name="target" />
        <span>AI 逐帧连续推理</span>
        <strong class="active">连续刷新</strong>
      </header>
      <div class="analysis-quad-viewport output-viewport inference-output-viewport">
        <InferenceViewSwitcher
          :sources="effectiveLiveInferenceViewSources"
          source-mode="continuous"
          :status-label="liveFrameStatus || '正在刷新当前帧'"
        />
      </div>
      <div class="preview-panel-meta">
        <p>{{ liveInferenceFooterLabel }}</p>
      </div>
    </article>

    <article v-for="panel in visiblePanels" :key="panel.title" class="analysis-quad-card">
      <header>
        <AppIcon :name="panelIcon(panel.title)" />
        <span>{{ panel.title }}</span>
      </header>
      <div
        class="analysis-quad-viewport output-viewport"
        :class="{ 'has-image': panel.previewSrc, 'is-empty': !panel.previewSrc }"
      >
        <img v-if="panel.previewSrc" :src="panel.previewSrc" :alt="panel.title" />
        <svg
          v-if="panel.previewSrc && panel.overlays?.length"
          class="preview-overlay"
          viewBox="0 0 1 1"
          preserveAspectRatio="none"
          aria-label="ROI 与候选区叠加"
        >
          <rect
            v-for="overlay in panel.overlays"
            :key="overlay.key"
            :class="['preview-overlay-rect', `preview-overlay-rect--${overlay.tone}`]"
            :x="overlay.x"
            :y="overlay.y"
            :width="overlay.width"
            :height="overlay.height"
            vector-effect="non-scaling-stroke"
          >
            <title>{{ overlay.label }}</title>
          </rect>
        </svg>
        <div v-if="!panel.previewSrc" class="empty-preview-copy">
          <strong>等待{{ panel.title }}输出</strong>
          <span>运行分析后显示</span>
        </div>
      </div>
      <div class="preview-panel-meta">
        <p>{{ panel.tag }} / {{ panel.label }} / {{ panel.scale }}</p>
        <details v-if="panel.path" class="preview-path-details">
          <summary :title="panel.path">文件：{{ fileName(panel.path) }}</summary>
          <code>{{ panel.path }}</code>
        </details>
      </div>
    </article>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";

import AppIcon from "@/components/AppIcon.vue";
import type { AnalysisPreviewPanel, VideoPlaybackAnalysis } from "@/components/analysisPreview";
import type { AppIconName } from "@/components/appIcons";
import InferenceViewSwitcher from "@/components/InferenceViewSwitcher.vue";
import type { InferenceViewSources } from "@/components/inferenceViews";
import {
  captureVideoFrameAsJpeg,
  LIVE_FRAME_JPEG_QUALITY,
  LIVE_FRAME_MAX_LONG_SIDE,
} from "@/utils/browserFrameCapture";

const props = withDefaults(
  defineProps<{
    panels: AnalysisPreviewPanel[];
    cameraStream: MediaStream | null;
    cameraActive: boolean;
    cameraStatusLabel: string;
    videoPlayback?: VideoPlaybackAnalysis | null;
    currentPlaybackTime?: number;
    playbackDuration?: number;
    playbackSeekTimeSec?: number | null;
    playbackSeekToken?: number;
    liveOverlaySrc?: string;
    liveInferenceViewSources?: InferenceViewSources;
    liveFrameStatus?: string;
    liveModelLatencyMs?: number | null;
    liveEndToEndLatencyMs?: number | null;
    fullscreen?: boolean;
  }>(),
  {
    currentPlaybackTime: 0,
    playbackDuration: 0,
    playbackSeekTimeSec: null,
    playbackSeekToken: 0,
    fullscreen: false,
    liveOverlaySrc: "",
    liveInferenceViewSources: () => ({}),
    liveFrameStatus: "",
    liveModelLatencyMs: null,
    liveEndToEndLatencyMs: null,
  },
);

const emit = defineEmits<{
  playbackStateChange: [timeSec: number, durationSec: number];
  playbackStarted: [];
  playbackPaused: [];
  playbackEnded: [];
  playbackFrameRequested: [reason: "暂停位置" | "拖动位置"];
}>();

const cameraVideoRef = ref<HTMLVideoElement | null>(null);
const playbackVideoRef = ref<HTMLVideoElement | null>(null);

// 文件视频与摄像头共用同一主视口，由页面层传入当前选中的互斥输入源。
const fileVideoActive = computed(() => Boolean(props.videoPlayback?.videoSrc));
const streamActive = computed(() => props.cameraActive || fileVideoActive.value);
const effectiveLiveInferenceViewSources = computed<InferenceViewSources>(() => ({
  ...props.liveInferenceViewSources,
  signal: props.liveInferenceViewSources.signal || props.liveOverlaySrc,
}));
const hasLiveInference = computed(() => Object.values(effectiveLiveInferenceViewSources.value).some(Boolean));
const visiblePanels = computed(() => props.panels.slice(0, hasLiveInference.value ? 2 : 3));
const hasVisualContent = computed(
  () =>
    streamActive.value
    || hasLiveInference.value
    || visiblePanels.value.some((panel) => Boolean(panel.previewSrc)),
);
const hasOutputVisualContent = computed(() => visiblePanels.value.some((panel) => Boolean(panel.previewSrc)));
const gridClass = computed(() => [
  "analysis-quad-grid",
  {
    "analysis-quad-grid--fullscreen": props.fullscreen,
    "analysis-quad-grid--empty": !props.fullscreen && !hasVisualContent.value,
    "analysis-quad-grid--stream-empty-with-outputs":
      !props.fullscreen && !streamActive.value && hasOutputVisualContent.value,
  },
]);
const streamTitle = computed(() => "视频流输入");
const streamBadge = computed(() => {
  if (fileVideoActive.value) return "MP4";
  if (props.cameraActive) return "LIVE";
  return "未连接";
});
const streamFooterLabel = computed(() => {
  if (fileVideoActive.value && props.videoPlayback) {
    return `${formatPlaybackTime(props.currentPlaybackTime)} / ${formatPlaybackTime(props.playbackDuration)} · ${props.videoPlayback.sourceLabel}`;
  }
  return props.cameraStatusLabel;
});
const liveInferenceFooterLabel = computed(() => {
  const model = props.liveModelLatencyMs === null ? "模型耗时待记录" : `模型 ${Math.round(props.liveModelLatencyMs)} ms`;
  const total = props.liveEndToEndLatencyMs === null
    ? "端到端耗时待记录"
    : `端到端 ${Math.round(props.liveEndToEndLatencyMs)} ms`;
  return `${model} / ${total} / 医生复核必需`;
});

watch(
  () => props.cameraStream,
  async (stream) => {
    await nextTick();
    if (!cameraVideoRef.value) return;
    cameraVideoRef.value.srcObject = stream;
    if (stream) {
      await cameraVideoRef.value.play().catch(() => undefined);
    }
  },
  { immediate: true },
);

watch(
  () => [props.playbackSeekToken, props.playbackSeekTimeSec] as const,
  async ([, timeSec]) => {
    await nextTick();
    if (!playbackVideoRef.value || timeSec === null || timeSec === undefined || !Number.isFinite(timeSec)) return;
    playbackVideoRef.value.currentTime = timeSec;
    emitPlaybackState();
  },
);

function emitPlaybackState(event?: Event) {
  const video = (event?.currentTarget as HTMLVideoElement | null) ?? playbackVideoRef.value;
  if (!video) return;
  const timeSec = Number.isFinite(video.currentTime) ? video.currentTime : 0;
  const durationSec = Number.isFinite(video.duration) ? video.duration : 0;
  emit("playbackStateChange", timeSec, durationSec);
}

function handlePlaybackSeeked(event: Event) {
  emitPlaybackState(event);
  emit("playbackFrameRequested", "拖动位置");
}

function handlePlaybackPaused() {
  emit("playbackPaused");
  emit("playbackFrameRequested", "暂停位置");
}

async function capturePlaybackFrame(): Promise<Blob> {
  if (!playbackVideoRef.value || !fileVideoActive.value) {
    throw new Error("MP4 播放器尚未就绪。");
  }
  return captureVideoFrameAsJpeg(
    playbackVideoRef.value,
    LIVE_FRAME_JPEG_QUALITY,
    LIVE_FRAME_MAX_LONG_SIDE,
    "MP4 视频",
  );
}

function currentPlaybackTime(): number | undefined {
  const value = playbackVideoRef.value?.currentTime;
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function pausePlayback() {
  playbackVideoRef.value?.pause();
}

defineExpose({
  capturePlaybackFrame,
  currentPlaybackTime,
  pausePlayback,
});

function formatPlaybackTime(value: number | undefined): string {
  if (!value || !Number.isFinite(value) || value <= 0) return "0:00";
  const totalSeconds = Math.floor(value);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function fileName(path: string): string {
  const normalized = path.replace(/\\/g, "/");
  return normalized.split("/").filter(Boolean).at(-1) || path;
}

function panelIcon(title: string): AppIconName {
  if (title.startsWith("关键帧")) return "video";
  const icons: Record<string, AppIconName> = {
    融合图: "layers",
    热图: "target",
    分割叠加: "target",
    分割掩膜: "document",
    风险图: "target",
    不确定性: "document",
    归一化图: "document",
  };
  return icons[title] ?? "file";
}
</script>

<style scoped>
.analysis-quad-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-template-rows: repeat(2, minmax(280px, 1fr));
  gap: 12px;
  min-width: 0;
  min-height: clamp(620px, 70vh, 800px);
}

.analysis-quad-card {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  min-width: 0;
  min-height: 0;
  border: 1px solid var(--ov-border);
  border-radius: 6px;
  padding: 12px;
  background: var(--ov-bg-elevated);
}

.analysis-quad-card header {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  align-items: center;
  margin-bottom: 8px;
  color: var(--ov-text);
  font-size: 13px;
  font-weight: 700;
}

.analysis-quad-card header span {
  min-width: 0;
  overflow-wrap: anywhere;
  white-space: normal;
}

.analysis-quad-card header :deep(.app-icon) {
  flex: 0 0 auto;
  width: 15px;
  height: 15px;
  color: var(--ov-primary-strong);
}

.analysis-quad-card header strong {
  max-width: 100%;
  margin-left: auto;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 999px;
  padding: 2px 7px;
  background: var(--ov-bg-soft);
  color: var(--ov-text-muted);
  font-size: 10px;
  line-height: 1.4;
  overflow-wrap: anywhere;
  white-space: normal;
}

.analysis-quad-card header strong.active {
  border-color: var(--ov-success);
  background: var(--ov-bg-success);
  color: var(--ov-success);
}

.analysis-quad-viewport {
  position: relative;
  display: grid;
  place-items: center;
  min-height: 0;
  height: 100%;
  overflow: hidden;
  border: 1px solid var(--ov-border-strong);
  border-radius: 4px;
  background: var(--ov-bg-panel);
  isolation: isolate;
}

.analysis-quad-viewport::before {
  content: none;
}

.analysis-quad-viewport::after {
  content: none;
}

.camera-viewport {
  background: var(--ov-bg-panel);
}

.camera-viewport.active,
.camera-viewport.has-file-video {
  background: var(--ov-bg-media);
}

.camera-viewport.has-live-overlay,
.output-viewport.has-image {
  background: var(--ov-bg-media);
}

.camera-live-player {
  position: absolute;
  z-index: 3;
  top: 50%;
  left: 50%;
  display: block;
  width: auto;
  height: auto;
  max-width: 100%;
  max-height: 100%;
  min-width: 0;
  min-height: 0;
  transform: translate(-50%, -50%);
}

.live-segmentation-overlay {
  position: absolute;
  z-index: 5;
  top: 50%;
  left: 50%;
  display: block;
  width: auto;
  height: auto;
  max-width: 100%;
  max-height: 100%;
  min-width: 0;
  min-height: 0;
  object-fit: contain;
  object-position: center;
  transform: translate(-50%, -50%);
  pointer-events: none;
}

.live-frame-status {
  position: absolute;
  z-index: 6;
  right: 8px;
  bottom: 8px;
  display: grid;
  gap: 1px;
  max-width: calc(100% - 16px);
  border: 1px solid rgba(178, 237, 209, 0.88);
  border-radius: 4px;
  padding: 5px 7px;
  background: rgba(7, 41, 31, 0.82);
  color: #e6fff4;
  font-size: 11px;
  font-weight: 800;
  line-height: 1.25;
}

.live-frame-status span {
  color: #b5e6d0;
}

.camera-live-player {
  object-fit: contain;
  opacity: 0;
}

.camera-viewport.active .camera-live-player {
  opacity: 1;
}

.camera-viewport.has-file-video .camera-live-player {
  position: absolute;
  pointer-events: none;
  opacity: 0;
}

.camera-viewport.has-live-overlay .camera-live-player,
.camera-viewport.has-live-overlay .video-stream-player {
  visibility: hidden;
}

.video-stream-player {
  position: absolute;
  z-index: 3;
  top: 50%;
  left: 50%;
  display: block;
  width: auto;
  height: auto;
  max-width: 100%;
  max-height: 100%;
  min-width: 0;
  min-height: 0;
  object-fit: contain;
  object-position: center;
  transform: translate(-50%, -50%);
  opacity: 1;
  background: var(--ov-bg-media);
}

.output-viewport img {
  position: absolute;
  z-index: 3;
  top: 50%;
  left: 50%;
  display: block;
  width: auto;
  height: auto;
  max-width: 100%;
  max-height: 100%;
  min-width: 0;
  min-height: 0;
  object-fit: contain;
  object-position: center;
  transform: translate(-50%, -50%);
}

.preview-overlay {
  position: absolute;
  z-index: 4;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.preview-overlay-rect {
  fill: rgba(228, 155, 63, 0.1);
  stroke-width: 2;
}

.preview-overlay-rect--candidate {
  stroke: #e49b3f;
}

.preview-overlay-rect--roi {
  fill: rgba(44, 126, 192, 0.1);
  stroke: #2c7ec0;
  stroke-dasharray: 7 5;
}

.empty-preview-copy {
  position: relative;
  z-index: 4;
  display: grid;
  gap: 4px;
  justify-items: center;
  max-width: min(78%, 280px);
  min-width: 0;
  border: 0;
  border-radius: 6px;
  padding: 8px 12px;
  background: transparent;
  color: var(--ov-text-secondary);
  text-align: center;
  box-shadow: none;
}

.empty-preview-copy strong {
  color: var(--ov-primary);
  font-size: 12px;
  line-height: 1.2;
  overflow-wrap: anywhere;
  white-space: normal;
}

.empty-preview-copy span {
  color: var(--ov-text-muted);
  font-size: 11px;
  font-weight: 800;
  line-height: 1.35;
  overflow-wrap: anywhere;
  white-space: normal;
}

.analysis-quad-card p {
  margin: 5px 0 0;
  color: var(--ov-text-secondary);
  font-size: 12px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.preview-panel-meta {
  min-width: 0;
}

.preview-path-details {
  min-width: 0;
  margin-top: 5px;
  color: var(--ov-text-secondary);
  font-size: 11px;
  line-height: 1.35;
}

.preview-path-details summary {
  min-width: 0;
  overflow-wrap: anywhere;
  color: var(--ov-text-secondary);
  cursor: pointer;
}

.preview-path-details code {
  display: block;
  max-height: 120px;
  margin-top: 5px;
  overflow: auto;
  border-top: 1px solid var(--ov-border-subtle);
  padding-top: 5px;
  color: var(--ov-text-muted);
  font-family: inherit;
  font-size: 10px;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.preview-path-details:not([open]) code {
  display: none;
}

.analysis-quad-grid--fullscreen {
  height: 100%;
  min-height: 0;
}

.analysis-quad-grid--empty:not(.analysis-quad-grid--fullscreen) {
  min-height: clamp(500px, 54vh, 620px);
}

.analysis-quad-grid--stream-empty-with-outputs:not(.analysis-quad-grid--fullscreen) {
  min-height: clamp(500px, 54vh, 620px);
}

.analysis-quad-grid--fullscreen .analysis-quad-card {
  min-height: 0;
}

.analysis-quad-grid--fullscreen .analysis-quad-viewport {
  height: 100%;
  min-height: 0;
}

.analysis-quad-grid--fullscreen .preview-panel-meta {
  display: none;
}

@media (max-width: 960px) {
  .analysis-quad-grid:not(.analysis-quad-grid--fullscreen) {
    grid-template-columns: 1fr;
    grid-template-rows: auto;
    min-height: 0;
  }

  .analysis-quad-grid:not(.analysis-quad-grid--fullscreen) .analysis-quad-card--camera {
    grid-row: auto;
  }

  .analysis-quad-grid:not(.analysis-quad-grid--fullscreen) .analysis-quad-viewport {
    height: auto;
    aspect-ratio: 16 / 9;
    min-height: 190px;
  }
}

@media (max-width: 680px) {
  .analysis-quad-grid--fullscreen {
    grid-template-columns: 1fr;
    overflow: auto;
  }

  .analysis-quad-grid--fullscreen .analysis-quad-card {
    min-height: 300px;
  }

  .analysis-quad-grid--fullscreen .analysis-quad-viewport {
    min-height: 240px;
  }
}
</style>
