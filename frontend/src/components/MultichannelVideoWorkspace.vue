<template>
  <section class="multichannel-workspace" aria-label="多通道视频配准与融合工作区">
    <header class="multichannel-header">
      <div>
        <AppIcon name="layers" />
        <strong>{{ workspaceTitle }}</strong>
        <span>{{ clockLabel }} · {{ synchronizationLabel }}</span>
      </div>
      <span class="session-state" :class="sessionStateClass">
        {{ sessionStateLabel }}
      </span>
    </header>

    <div class="multichannel-grid">
      <article class="channel-card">
        <header>
          <span>{{ whiteChannelTitle }}</span>
          <strong>{{ whiteChannelBadge }}</strong>
        </header>
        <div class="media-viewport">
          <video
            v-if="hasWhiteSource"
            ref="whiteVideoRef"
            :src="whiteVideoSrc || undefined"
            :class="{ 'media-source-pending': mediaStatus.white !== 'ready' }"
            :controls="!browserCameraMode"
            :autoplay="browserCameraMode"
            :muted="browserCameraMode"
            preload="metadata"
            playsinline
            crossorigin="anonymous"
            @loadstart="markMediaLoading('white')"
            @loadedmetadata="handleMasterClockUpdate"
            @loadeddata="handleMasterFrameReady"
            @canplay="markMediaReady('white')"
            @error="handleMediaError('white', $event)"
            @play="handleMasterPlay"
            @pause="handleMasterPause"
            @seeking="handleMasterSeek"
            @seeked="handleMasterSeek"
            @ratechange="handleMasterRateChange"
            @timeupdate="handleMasterTimeUpdate"
            @ended="handleMasterPause"
          ></video>
          <div
            v-if="hasWhiteSource && mediaStatus.white !== 'ready'"
            class="media-state"
            :class="{ error: mediaStatus.white === 'error' }"
            :role="mediaStatus.white === 'error' ? 'alert' : 'status'"
          >
            <AppIcon :name="mediaStatus.white === 'error' ? 'alert' : 'load'" />
            <strong>{{ mediaStatus.white === "error" ? "白光视频加载失败" : "正在加载白光视频" }}</strong>
            <span>{{ mediaStatus.white === "error" ? mediaError.white : whiteLoadingHint }}</span>
            <button v-if="mediaStatus.white === 'error'" type="button" @click="reloadMedia('white')">
              <AppIcon name="load" />
              重新载入
            </button>
          </div>
          <div v-if="!hasWhiteSource" class="empty-channel">
            <AppIcon :name="browserCameraMode ? 'camera' : 'video'" />
            <strong>{{ browserCameraMode ? "等待白光摄像头" : "等待白光视频" }}</strong>
            <span>{{ browserCameraMode ? "请在左侧控制栏连接白光摄像头" : effectiveMode === "composite_layout" ? "完成三视图拆分后将在此显示白光画面" : "请从病例输入中选择白光 MP4" }}</span>
          </div>
        </div>
        <footer>{{ browserCameraMode ? `白光实时画面 · ${formatTime(currentTimeSec)}` : `连续主视频 · ${formatTime(currentTimeSec)} / ${formatTime(durationSec)}` }}</footer>
      </article>

      <article class="channel-card">
        <header>
          <span>荧光通道</span>
          <div class="compact-switch" role="group" aria-label="荧光配准显示模式">
            <button type="button" :class="{ active: fluorescenceView === 'raw' }" @click="fluorescenceView = 'raw'">
              连续原始
            </button>
            <button
              type="button"
              :class="{ active: fluorescenceView === 'registered' }"
              :disabled="!registeredFluorescenceSrc"
              @click="fluorescenceView = 'registered'"
            >
              配准后
            </button>
          </div>
        </header>
        <div class="media-viewport">
          <video
            v-if="hasFluorescenceSource"
            v-show="fluorescenceView === 'raw'"
            ref="fluorescenceVideoRef"
            :src="fluorescenceVideoSrc || undefined"
            :class="{ 'media-source-pending': mediaStatus.fluorescence !== 'ready' }"
            muted
            :autoplay="browserCameraMode"
            preload="metadata"
            playsinline
            crossorigin="anonymous"
            @loadstart="markMediaLoading('fluorescence')"
            @loadeddata="handleFollowerFrameReady"
            @canplay="markMediaReady('fluorescence')"
            @error="handleMediaError('fluorescence', $event)"
          ></video>
          <span
            v-if="fluorescenceView === 'raw' && hasFluorescenceSource && mediaStatus.fluorescence === 'ready'"
            class="refresh-badge continuous"
          >
            连续同步 · 漂移 {{ formatDrift(fluorescenceDriftMs) }}
          </span>
          <div
            v-if="fluorescenceView === 'raw' && hasFluorescenceSource && mediaStatus.fluorescence !== 'ready'"
            class="media-state"
            :class="{ error: mediaStatus.fluorescence === 'error' }"
            :role="mediaStatus.fluorescence === 'error' ? 'alert' : 'status'"
          >
            <AppIcon :name="mediaStatus.fluorescence === 'error' ? 'alert' : 'load'" />
            <strong>{{ mediaStatus.fluorescence === "error" ? "荧光视频加载失败" : "正在加载荧光视频" }}</strong>
            <span>{{ mediaStatus.fluorescence === "error" ? mediaError.fluorescence : fluorescenceLoadingHint }}</span>
            <button v-if="mediaStatus.fluorescence === 'error'" type="button" @click="reloadMedia('fluorescence')">
              <AppIcon name="load" />
              重新载入
            </button>
          </div>
          <div v-if="fluorescenceView === 'raw' && !hasFluorescenceSource" class="empty-channel">
            <AppIcon :name="browserCameraMode ? 'camera' : 'video'" />
            <strong>{{ browserCameraMode ? "等待荧光摄像头" : "等待荧光视频" }}</strong>
            <span>{{ browserCameraMode ? "请在左侧控制栏连接荧光摄像头" : effectiveMode === "composite_layout" ? "完成三视图拆分后将在此显示荧光画面" : "请从病例输入中选择荧光 MP4" }}</span>
          </div>
          <img
            v-if="fluorescenceView === 'registered' && registeredFluorescenceSrc"
            :src="registeredFluorescenceSrc"
            alt="当前播放位置的配准后荧光图"
          />
          <span
            v-if="fluorescenceView === 'registered' && registeredFluorescenceSrc"
            class="refresh-badge keyframe"
          >
            {{ liveRegisteredFluorescenceSrc ? "当前播放帧" : `离线关键帧 · ${keyframeDeltaLabel}` }}
          </span>
        </div>
        <footer>
          偏移 {{ formatOffset(channelOffset("fluorescence")) }} ·
          {{ fluorescenceView === "registered" ? nearestFrameLabel : "跟随白光连续时钟" }}
        </footer>
      </article>

      <article class="channel-card">
        <header>
          <span>配准融合结果</span>
          <div v-if="hasDeviceOverlay" class="compact-switch" role="group" aria-label="融合结果比较模式">
            <button type="button" :class="{ active: fusionView === 'software' }" @click="fusionView = 'software'">
              软件融合
            </button>
            <button type="button" :class="{ active: fusionView === 'device' }" @click="fusionView = 'device'">
              设备叠加
            </button>
            <button
              v-if="nearestFrame?.device_overlay_difference_path"
              type="button"
              :class="{ active: fusionView === 'difference' }"
              @click="fusionView = 'difference'"
            >
              差异热图
            </button>
          </div>
        </header>
        <div class="media-viewport">
          <img
            v-if="liveFusionSrc && fusionView === 'software'"
            :src="liveFusionSrc"
            alt="当前播放位置的实时配准融合结果"
          />
          <img
            v-else-if="nearestFrame?.overlay_path"
            v-show="fusionView === 'software'"
            :src="apiClient.filePreviewUrl(nearestFrame.overlay_path)"
            alt="最近关键帧的软件配准融合结果"
          />
          <video
            v-if="hasDeviceOverlay"
            v-show="fusionView === 'device'"
            ref="deviceOverlayVideoRef"
            :src="deviceOverlayVideoSrc"
            :class="{ 'media-source-pending': mediaStatus.deviceOverlay !== 'ready' }"
            muted
            preload="metadata"
            playsinline
            crossorigin="anonymous"
            @loadstart="markMediaLoading('deviceOverlay')"
            @loadeddata="markMediaReady('deviceOverlay')"
            @canplay="markMediaReady('deviceOverlay')"
            @error="handleMediaError('deviceOverlay', $event)"
          ></video>
          <img
            v-if="nearestFrame?.device_overlay_difference_path"
            v-show="fusionView === 'difference'"
            :src="apiClient.filePreviewUrl(nearestFrame.device_overlay_difference_path)"
            alt="设备叠加与软件融合差异热图"
          />
          <span v-if="liveFusionSrc && fusionView === 'software'" class="refresh-badge continuous">
            {{ liveFusionStatus || "当前时钟帧配准融合" }}
          </span>
          <span v-else-if="activeFusionContentAvailable" class="refresh-badge" :class="fusionRefreshClass">
            {{ fusionRefreshLabel }}
          </span>
          <div
            v-if="fusionView === 'device' && hasDeviceOverlay && mediaStatus.deviceOverlay !== 'ready'"
            class="media-state"
            :class="{ error: mediaStatus.deviceOverlay === 'error' }"
            :role="mediaStatus.deviceOverlay === 'error' ? 'alert' : 'status'"
          >
            <AppIcon :name="mediaStatus.deviceOverlay === 'error' ? 'alert' : 'load'" />
            <strong>{{ mediaStatus.deviceOverlay === "error" ? "设备叠加视频加载失败" : "正在加载设备叠加视频" }}</strong>
            <span>{{ mediaStatus.deviceOverlay === "error" ? mediaError.deviceOverlay : "正在读取设备叠加视频的元数据与首帧" }}</span>
            <button v-if="mediaStatus.deviceOverlay === 'error'" type="button" @click="reloadMedia('deviceOverlay')">
              <AppIcon name="load" />
              重新载入
            </button>
          </div>
          <div v-if="!activeFusionContentAvailable" class="empty-channel">
            <AppIcon name="layers" />
            <strong>{{ browserCameraMode ? "等待实时融合结果" : "等待配准融合结果" }}</strong>
            <span>{{ browserCameraMode ? "开启双通道实时分析后显示当前帧融合画面" : "完成双通道同步分析后显示最近关键帧结果" }}</span>
          </div>
        </div>
        <footer>{{ nearestFrameLabel }}</footer>
      </article>

      <article class="channel-card">
        <header>
          <span>AI 分割与风险提示</span>
          <div class="ai-channel-meta">
            <span class="ai-input-semantics">{{ aiInputSemanticsLabel }}</span>
            <strong>{{ aiExecutionLabel }}</strong>
          </div>
        </header>
        <div class="media-viewport inference-viewport">
          <InferenceViewSwitcher
            :sources="activeAiViewSources"
            :source-mode="liveAiAvailable ? 'continuous' : offlineAiAvailable ? 'keyframe' : 'waiting'"
            :status-label="aiViewStatusLabel"
            :empty-message="browserCameraMode ? '开启双通道连续分析后显示' : '完成融合帧推理后显示'"
          />
        </div>
        <footer>{{ aiFooterLabel }}</footer>
      </article>
    </div>

    <dl class="registration-strip" aria-label="当前帧配准证据">
      <div>
        <dt>同步时间差</dt>
        <dd>{{ pairDeltaLabel }}</dd>
      </div>
      <div>
        <dt>配准方法</dt>
        <dd>{{ registrationText("method", "等待分析") }}</dd>
      </div>
      <div>
        <dt>平移 / 局部变换</dt>
        <dd>{{ transformLabel }}</dd>
      </div>
      <div>
        <dt>响应值</dt>
        <dd>{{ registrationNumber("response") }}</dd>
      </div>
      <div>
        <dt>质量门</dt>
        <dd>{{ qualityGateLabel }}</dd>
      </div>
      <div>
        <dt>当前帧</dt>
        <dd>{{ nearestFrameLabel }}</dd>
      </div>
    </dl>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from "vue";

import AppIcon from "@/components/AppIcon.vue";
import InferenceViewSwitcher from "@/components/InferenceViewSwitcher.vue";
import type { InferenceViewSources } from "@/components/inferenceViews";
import { apiClient } from "@/services/apiClient";
import {
  captureVideoFrameAsJpeg,
  LIVE_FRAME_JPEG_QUALITY,
  LIVE_FRAME_MAX_LONG_SIDE,
} from "@/utils/browserFrameCapture";
import type {
  MultichannelVideoMode,
  MultichannelVideoRole,
  MultichannelVideoSession,
} from "@/types/case";

type Task2Frame = {
  frame_index?: number;
  white_timestamp_ms?: number | null;
  pair_delta_ms?: number | null;
  synchronization_verified?: boolean;
  registered_fluorescence_path?: string;
  pseudocolor_path?: string;
  overlay_path?: string;
  device_overlay_difference_path?: string;
  registration?: Record<string, unknown>;
};

type MediaSurface = "white" | "fluorescence" | "deviceOverlay";
type MediaLoadStatus = "idle" | "loading" | "ready" | "error";

const props = withDefaults(
  defineProps<{
    mode?: MultichannelVideoMode;
    session?: MultichannelVideoSession | null;
    channelPaths?: Partial<Record<MultichannelVideoRole, string>>;
    task2Result?: Record<string, unknown> | null;
    aiPreviewSrc?: string;
    aiViewSources?: InferenceViewSources;
    liveFrameRecord?: Record<string, unknown> | null;
    liveFusionSrc?: string;
    liveRegisteredFluorescenceSrc?: string;
    liveFusionStatus?: string;
    realtimeAnalysisEnabled?: boolean;
    realtimeAnalysisBusy?: boolean;
    liveOverlaySrc?: string;
    liveInferenceViewSources?: InferenceViewSources;
    liveFrameStatus?: string;
    whiteCameraStream?: MediaStream | null;
    fluorescenceCameraStream?: MediaStream | null;
  }>(),
  {
    mode: "paired_videos",
    session: null,
    channelPaths: () => ({}),
    task2Result: null,
    aiPreviewSrc: "",
    aiViewSources: () => ({}),
    liveFrameRecord: null,
    liveFusionSrc: "",
    liveRegisteredFluorescenceSrc: "",
    liveFusionStatus: "",
    realtimeAnalysisEnabled: false,
    realtimeAnalysisBusy: false,
    liveOverlaySrc: "",
    liveInferenceViewSources: () => ({}),
    liveFrameStatus: "",
    whiteCameraStream: null,
    fluorescenceCameraStream: null,
  },
);

const emit = defineEmits<{
  liveFrame: [payload: { timeSec: number; reason: string; whiteFrame?: Blob; fluorescenceFrame?: Blob }];
}>();

const whiteVideoRef = ref<HTMLVideoElement | null>(null);
const fluorescenceVideoRef = ref<HTMLVideoElement | null>(null);
const deviceOverlayVideoRef = ref<HTMLVideoElement | null>(null);
const mediaStatus = reactive<Record<MediaSurface, MediaLoadStatus>>({
  white: "idle",
  fluorescence: "idle",
  deviceOverlay: "idle",
});
const mediaError = reactive<Record<MediaSurface, string>>({
  white: "",
  fluorescence: "",
  deviceOverlay: "",
});
const currentTimeSec = ref(0);
const durationSec = ref(0);
const fluorescenceView = ref<"raw" | "registered">("raw");
const fusionView = ref<"software" | "device" | "difference">("software");
const fluorescenceDriftMs = ref(0);
const deviceOverlayDriftMs = ref(0);
let animationFrameId: number | null = null;
let liveFrameRetryTimer: number | null = null;
let cameraClockStartedAtMs: number | null = null;
const pendingLiveReason = ref("");
let liveFrameDispatching = false;
const effectiveMode = computed<MultichannelVideoMode>(() => props.session?.mode ?? props.mode);
const browserCameraMode = computed(() => effectiveMode.value === "browser_cameras");
const workspaceTitle = computed(() =>
  effectiveMode.value === "composite_layout"
    ? "合成三视图拆分与配准"
    : browserCameraMode.value
      ? "双通道摄像头实时配准"
      : "双通道同步配准",
);
const clockLabel = computed(() =>
  effectiveMode.value === "composite_layout"
    ? "三视图受控拆分"
    : browserCameraMode.value
      ? "浏览器本地采集时钟"
      : "白光主时钟",
);
const sessionStateClass = computed(() => props.session?.synchronization_status ?? "pending");
const sessionStateLabel = computed(() => {
  if (!props.session) return "等待准备";
  if (props.session.status === "ready") return "会话就绪";
  if (props.session.status === "degraded") return "降级可用";
  return "会话受阻";
});
const whiteChannelTitle = computed(() => {
  if (degradedComposite.value) return "原始合成视频";
  if (browserCameraMode.value) return "白光摄像头";
  return effectiveMode.value === "composite_layout" ? "白光拆分视图" : "白光原始视频";
});
const whiteChannelBadge = computed(() => {
  if (degradedComposite.value) return "单路降级";
  if (browserCameraMode.value) return props.whiteCameraStream ? "实时" : "未连接";
  return props.session ? "主时钟" : "待同步";
});

const frames = computed<Task2Frame[]>(() => {
  if (browserCameraMode.value) return [];
  return Array.isArray(props.task2Result?.frames) ? (props.task2Result.frames as Task2Frame[]) : [];
});
const liveEvidenceFrame = computed<Task2Frame | null>(() => (
  browserCameraMode.value && isRecord(props.liveFrameRecord)
    ? props.liveFrameRecord as Task2Frame
    : null
));
const nearestFrame = computed<Task2Frame | null>(() => {
  if (!frames.value.length) return null;
  return frames.value.reduce((nearest, frame) => {
    const nearestTime = Number(nearest.white_timestamp_ms ?? 0) / 1000;
    const frameTime = Number(frame.white_timestamp_ms ?? 0) / 1000;
    return Math.abs(frameTime - currentTimeSec.value) < Math.abs(nearestTime - currentTimeSec.value)
      ? frame
      : nearest;
  });
});
const nearestFrameTimeSec = computed(() => Number(nearestFrame.value?.white_timestamp_ms ?? 0) / 1000);
const evidenceFrame = computed(() => liveEvidenceFrame.value ?? nearestFrame.value);
const keyframePlaybackDeltaMs = computed(() =>
  nearestFrame.value ? Math.abs(nearestFrameTimeSec.value - currentTimeSec.value) * 1000 : null,
);
const keyframeDeltaLabel = computed(() =>
  keyframePlaybackDeltaMs.value === null ? "等待时间戳" : `距播放 ${formatLatency(keyframePlaybackDeltaMs.value)}`,
);
const nearestFrameLabel = computed(() =>
  browserCameraMode.value
    ? props.liveFusionSrc
      ? `当前摄像头帧实时结果 · ${formatTimePrecise(currentTimeSec.value)}`
      : "等待当前双通道摄像头帧"
    : nearestFrame.value
      ? `关键帧同步结果 · 第 ${Number(nearestFrame.value.frame_index ?? 0) + 1} 帧 · ${formatTimePrecise(nearestFrameTimeSec.value)} · ${keyframeDeltaLabel.value}`
      : "尚无关键帧同步结果",
);
const whiteVideoSrc = computed(() => channelVideoUrl("white_light") || channelVideoUrl("video"));
const fluorescenceVideoSrc = computed(() => channelVideoUrl("fluorescence"));
const deviceOverlayVideoSrc = computed(() => channelVideoUrl("device_overlay"));
const hasWhiteSource = computed(() => Boolean(whiteVideoSrc.value || props.whiteCameraStream));
const hasFluorescenceSource = computed(() => Boolean(fluorescenceVideoSrc.value || props.fluorescenceCameraStream));
const whiteLoadingHint = computed(() =>
  browserCameraMode.value ? "正在等待白光摄像头首帧" : "正在读取白光 MP4 的元数据与首帧",
);
const fluorescenceLoadingHint = computed(() =>
  browserCameraMode.value ? "正在等待荧光摄像头首帧" : "正在读取荧光 MP4 的元数据与首帧",
);
const hasDeviceOverlay = computed(() => Boolean(deviceOverlayVideoSrc.value));
const registeredFluorescenceSrc = computed(() =>
  props.liveRegisteredFluorescenceSrc ||
  (!browserCameraMode.value && nearestFrame.value?.registered_fluorescence_path
    ? apiClient.filePreviewUrl(nearestFrame.value.registered_fluorescence_path)
    : ""),
);
const degradedComposite = computed(() => !channel("white_light") && Boolean(channel("video")));
const activeFusionContentAvailable = computed(() => {
  if (fusionView.value === "software" && props.liveFusionSrc) return true;
  if (browserCameraMode.value) return false;
  if (fusionView.value === "software") return Boolean(nearestFrame.value?.overlay_path);
  if (fusionView.value === "device") return hasDeviceOverlay.value;
  return Boolean(nearestFrame.value?.device_overlay_difference_path);
});
const fusionRefreshClass = computed(() => (fusionView.value === "device" ? "continuous" : "keyframe"));
const fusionRefreshLabel = computed(() =>
  fusionView.value === "device"
    ? `连续同步 · 漂移 ${formatDrift(deviceOverlayDriftMs.value)}`
    : `离线关键帧 · ${keyframeDeltaLabel.value}`,
);
const aiSourceFrameIndex = computed(() => {
  const value = Number(props.task2Result?.ai_source_frame_index);
  return Number.isFinite(value) ? value : null;
});
const aiSourceTimestampSec = computed(() => {
  const value = Number(props.task2Result?.ai_source_timestamp_ms);
  return Number.isFinite(value) ? value / 1000 : null;
});
const aiSourceFrameLabel = computed(() =>
  aiSourceFrameIndex.value === null ? "时间戳待确认" : `第 ${aiSourceFrameIndex.value + 1} 帧`,
);
const aiPlaybackDeltaLabel = computed(() => {
  if (aiSourceTimestampSec.value === null) return "时间差待确认";
  return `距播放 ${formatLatency(Math.abs(aiSourceTimestampSec.value - currentTimeSec.value) * 1000)}`;
});
const aiInferenceMs = computed(() => {
  const value = Number(props.task2Result?.ai_inference_ms);
  return Number.isFinite(value) && value >= 0 ? value : null;
});
const offlineAiViewSources = computed<InferenceViewSources>(() => (
  browserCameraMode.value
    ? {}
    : {
        ...props.aiViewSources,
        signal: props.aiViewSources.signal || props.aiPreviewSrc,
      }
));
const liveAiViewSources = computed<InferenceViewSources>(() => ({
  ...props.liveInferenceViewSources,
  signal: props.liveInferenceViewSources.signal || props.liveOverlaySrc,
}));
const liveAiAvailable = computed(() => Object.values(liveAiViewSources.value).some(Boolean));
const offlineAiAvailable = computed(() => Object.values(offlineAiViewSources.value).some(Boolean));
const activeAiViewSources = computed<InferenceViewSources>(() =>
  liveAiAvailable.value ? liveAiViewSources.value : offlineAiViewSources.value,
);
const aiInputSemanticsLabel = computed(() => liveAiAvailable.value ? "当前融合 RGB 帧" : "融合 RGB 关键帧");
const aiExecutionLabel = computed(() => {
  if (liveAiAvailable.value) return "逐帧连续推理";
  if (offlineAiAvailable.value) return "关键帧离线推理";
  return "等待 AI 输出";
});
const aiViewStatusLabel = computed(() => {
  if (liveAiAvailable.value) return `当前时钟帧 AI · ${props.liveFrameStatus || "正在刷新"}`;
  if (offlineAiAvailable.value) return `AI 关键帧 ${aiSourceFrameLabel.value} · ${aiPlaybackDeltaLabel.value}`;
  return "";
});
const aiFooterLabel = computed(() => {
  if (liveAiAvailable.value) {
    return browserCameraMode.value
      ? "当前双通道摄像头融合帧 AI 提示 · 浏览器采集同步需复核 · 医生复核必需"
      : "当前双通道同步预融合帧 AI 提示 · 任务2正式配准证据单独记录 · 医生复核必需";
  }
  if (browserCameraMode.value) return "等待当前双通道摄像头融合帧 AI 输出 · 医生复核必需";
  const latency = aiInferenceMs.value === null ? "推理耗时待记录" : `模型推理 ${formatLatency(aiInferenceMs.value)}`;
  return `输入语义：融合 RGB 关键帧 · ${latency} · 医生复核必需`;
});
const synchronizationLabel = computed(() => {
  if (!props.session) return "等待同步预览";
  if (props.session.synchronization_status === "aligned") return "同步已对齐";
  if (props.session.synchronization_status === "review_required") return "同步需要复核";
  return "同步不可用";
});
const pairDeltaLabel = computed(() => {
  const value = evidenceFrame.value?.pair_delta_ms;
  if (browserCameraMode.value) {
    return typeof value === "number"
      ? `${value.toFixed(2)} ms · 浏览器采集同步需复核`
      : "浏览器采集时钟 · 需复核";
  }
  return typeof value === "number" ? `${value.toFixed(2)} ms` : "等待关键帧证据";
});
const transformLabel = computed(() => {
  const registration = evidenceFrame.value?.registration;
  if (!registration) return "等待分析";
  const translation = registration.translation_xy;
  const local = registration.local_deformation;
  const translationText =
    Array.isArray(translation) && translation.length >= 2
      ? `${Number(translation[0]).toFixed(2)}, ${Number(translation[1]).toFixed(2)} px`
      : "无平移记录";
  const localApplied = isRecord(local) && local.applied === true;
  return `${translationText} · 局部${localApplied ? "已应用" : "未应用"}`;
});
const qualityGateLabel = computed(() => {
  const registration = evidenceFrame.value?.registration;
  if (!registration) return "等待分析";
  if (registration.applied === true && evidenceFrame.value?.synchronization_verified === true) {
    return browserCameraMode.value ? "配准通过 · 采集同步需复核" : "通过";
  }
  return String(registration.reason || "需要复核");
});

watch(
  () => [whiteVideoSrc.value, props.whiteCameraStream, browserCameraMode.value] as const,
  () => resetMediaForSource("white", hasWhiteSource.value),
  { immediate: true },
);

watch(
  () => [fluorescenceVideoSrc.value, props.fluorescenceCameraStream, browserCameraMode.value] as const,
  () => resetMediaForSource("fluorescence", hasFluorescenceSource.value),
  { immediate: true },
);

watch(
  deviceOverlayVideoSrc,
  () => resetMediaForSource("deviceOverlay", hasDeviceOverlay.value),
  { immediate: true },
);

watch(
  () => [props.whiteCameraStream, props.fluorescenceCameraStream, browserCameraMode.value] as const,
  async ([whiteStream, fluorescenceStream, cameraMode]) => {
    await nextTick();
    if (!cameraMode) return;
    await bindCameraStream(whiteVideoRef.value, whiteStream, "white");
    await bindCameraStream(fluorescenceVideoRef.value, fluorescenceStream, "fluorescence");
    if (whiteStream && fluorescenceStream) {
      cameraClockStartedAtMs = performance.now();
      currentTimeSec.value = 0;
      durationSec.value = 0;
      requestLiveFrame("双通道摄像头已就绪");
      startClockLoop();
      return;
    }
    stopClockLoop();
  },
  { immediate: true, flush: "post" },
);

async function bindCameraStream(
  video: HTMLVideoElement | null,
  stream: MediaStream | null,
  surface: Extract<MediaSurface, "white" | "fluorescence">,
) {
  if (!video) return;
  video.srcObject = stream;
  if (!stream) return;
  markMediaLoading(surface);
  await video.play().catch(() => {
    mediaStatus[surface] = "error";
    mediaError[surface] = "摄像头画面无法播放，请检查设备权限后重新连接。";
  });
}

function resetMediaForSource(surface: MediaSurface, hasSource: boolean) {
  mediaStatus[surface] = hasSource ? "loading" : "idle";
  mediaError[surface] = "";
}

function markMediaLoading(surface: MediaSurface) {
  mediaStatus[surface] = "loading";
  mediaError[surface] = "";
}

function markMediaReady(surface: MediaSurface) {
  mediaStatus[surface] = "ready";
  mediaError[surface] = "";
}

function handleMediaError(surface: MediaSurface, event: Event) {
  const video = event.currentTarget instanceof HTMLVideoElement ? event.currentTarget : mediaElement(surface);
  mediaStatus[surface] = "error";
  mediaError[surface] = describeMediaError(surface, video?.error?.code ?? 0);
}

function describeMediaError(surface: MediaSurface, code: number): string {
  if (browserCameraMode.value && surface !== "deviceOverlay") {
    return "摄像头视频流已中断，请检查设备连接与浏览器权限。";
  }
  if (code === 1) return "视频加载已中止，请重新载入。";
  if (code === 2) return "视频文件读取失败，请确认病例输入仍可访问。";
  if (code === 3) return "视频编码无法解码，请重新导入标准 MP4。";
  if (code === 4) return "当前视频来源或格式无法播放，请重新导入标准 MP4。";
  return "视频首帧未能加载，请重新载入或重新导入该输入。";
}

function mediaElement(surface: MediaSurface): HTMLVideoElement | null {
  if (surface === "white") return whiteVideoRef.value;
  if (surface === "fluorescence") return fluorescenceVideoRef.value;
  return deviceOverlayVideoRef.value;
}

async function reloadMedia(surface: MediaSurface) {
  const video = mediaElement(surface);
  if (!video) return;
  markMediaLoading(surface);
  if (browserCameraMode.value && surface !== "deviceOverlay") {
    const stream = surface === "white" ? props.whiteCameraStream : props.fluorescenceCameraStream;
    if (!stream) {
      mediaStatus[surface] = "error";
      mediaError[surface] = "摄像头尚未连接，请先在左侧控制栏连接设备。";
      return;
    }
    await bindCameraStream(video, stream, surface);
    return;
  }
  video.load();
}

function channel(role: MultichannelVideoRole) {
  return props.session?.channels.find((item) => item.role === role);
}

function channelVideoUrl(role: MultichannelVideoRole): string {
  if (browserCameraMode.value) return "";
  const value = channel(role);
  const path = value?.path || props.channelPaths[role] || "";
  return path ? apiClient.fileVideoUrl(path) : "";
}

function channelOffset(role: MultichannelVideoRole): number {
  return Number(channel(role)?.effective_offset_ms ?? 0);
}

function followerEntries(): Array<{ element: HTMLVideoElement | null; role: MultichannelVideoRole }> {
  return [
    { element: fluorescenceVideoRef.value, role: "fluorescence" },
    { element: deviceOverlayVideoRef.value, role: "device_overlay" },
  ];
}

function desiredFollowerTime(role: MultichannelVideoRole): number {
  return Math.max(0, currentTimeSec.value + channelOffset(role) / 1000);
}

function syncPlayback(action: "play" | "pause" | "seek" | "rate" | "clock") {
  if (browserCameraMode.value) return;
  const master = whiteVideoRef.value;
  if (!master) return;
  currentTimeSec.value = master.currentTime || 0;
  for (const follower of followerEntries()) {
    if (!follower.element) continue;
    follower.element.playbackRate = master.playbackRate;
    const desired = desiredFollowerTime(follower.role);
    const driftMs = (follower.element.currentTime - desired) * 1000;
    setFollowerDrift(follower.role, driftMs);
    const configuredThresholdSec = Number(props.session?.drift_correction_threshold_ms ?? 80) / 1000;
    const correctionThresholdSec = Math.min(Math.max(configuredThresholdSec, 0.016), 0.04);
    if (action !== "clock" || Math.abs(driftMs) / 1000 > correctionThresholdSec) {
      try {
        follower.element.currentTime = desired;
        setFollowerDrift(follower.role, 0);
      } catch {
        continue;
      }
    }
    if (action === "play") void follower.element.play().catch(() => undefined);
    if (action === "pause") follower.element.pause();
  }
}

function handleMasterTimeUpdate() {
  handleMasterClockUpdate();
  syncPlayback("clock");
  requestLiveFrame("播放位置更新");
}

function handleMasterClockUpdate() {
  const master = whiteVideoRef.value;
  if (!master) return;
  if (browserCameraMode.value) {
    const startedAt = cameraClockStartedAtMs ?? performance.now();
    cameraClockStartedAtMs = startedAt;
    currentTimeSec.value = Math.max(0, (performance.now() - startedAt) / 1000);
    durationSec.value = 0;
    requestLiveFrame("摄像头当前画面");
    return;
  }
  currentTimeSec.value = Number.isFinite(master.currentTime) ? master.currentTime : 0;
  durationSec.value = Number.isFinite(master.duration) ? master.duration : 0;
  requestLiveFrame("视频就绪");
}

function handleMasterFrameReady() {
  markMediaReady("white");
  handleMasterClockUpdate();
  requestLiveFrame("白光当前帧就绪");
}

function handleFollowerFrameReady() {
  markMediaReady("fluorescence");
  requestLiveFrame("荧光当前帧就绪");
}

function handleMasterPlay() {
  syncPlayback("play");
  startClockLoop();
}

function handleMasterPause() {
  stopClockLoop();
  syncPlayback("pause");
  handleMasterClockUpdate();
  requestLiveFrame("暂停位置");
}

function handleMasterSeek() {
  syncPlayback("seek");
  handleMasterClockUpdate();
  requestLiveFrame("拖动位置");
}

function requestLiveFrame(reason: string) {
  if (!props.realtimeAnalysisEnabled || !whiteVideoRef.value) return;
  if (browserCameraMode.value && !fluorescenceVideoRef.value) return;
  pendingLiveReason.value = reason;
  if (props.realtimeAnalysisBusy || liveFrameDispatching) return;
  void dispatchLiveFrame();
}

async function dispatchLiveFrame() {
  const video = whiteVideoRef.value;
  if (!video || !props.realtimeAnalysisEnabled || props.realtimeAnalysisBusy || liveFrameDispatching) return;
  liveFrameDispatching = true;
  const reason = pendingLiveReason.value || "当前播放位置";
  pendingLiveReason.value = "";
  try {
    const fluorescence = fluorescenceVideoRef.value;
    const frames = fluorescence
      ? await Promise.all([
          captureVideoFrameAsJpeg(video, LIVE_FRAME_JPEG_QUALITY, LIVE_FRAME_MAX_LONG_SIDE, "白光视频"),
          captureVideoFrameAsJpeg(fluorescence, LIVE_FRAME_JPEG_QUALITY, LIVE_FRAME_MAX_LONG_SIDE, "荧光视频"),
        ])
      : [];
    emit("liveFrame", {
      timeSec: browserCameraMode.value
        ? currentTimeSec.value
        : Number.isFinite(video.currentTime) ? video.currentTime : currentTimeSec.value,
      reason,
      whiteFrame: frames[0],
      fluorescenceFrame: frames[1],
    });
  } catch {
    // The follower video can reach a usable frame shortly after the white-light master clock.
    pendingLiveReason.value = reason;
    scheduleLiveFrameRetry();
  } finally {
    liveFrameDispatching = false;
  }
}

function scheduleLiveFrameRetry() {
  if (liveFrameRetryTimer !== null || !props.realtimeAnalysisEnabled) return;
  liveFrameRetryTimer = window.setTimeout(() => {
    liveFrameRetryTimer = null;
    void dispatchLiveFrame();
  }, 80);
}

watch(
  () => [props.realtimeAnalysisEnabled, props.realtimeAnalysisBusy] as const,
  ([enabled, busy], previous) => {
    const wasEnabled = previous?.[0] ?? false;
    if (!enabled || busy) return;
    if (!wasEnabled) pendingLiveReason.value = "实时分析已开启";
    if (!pendingLiveReason.value) return;
    void dispatchLiveFrame();
  },
  { immediate: true, flush: "post" },
);

function handleMasterRateChange() {
  syncPlayback("rate");
}

function startClockLoop() {
  if (animationFrameId !== null) return;
  animationFrameId = window.requestAnimationFrame(runClockFrame);
}

function runClockFrame() {
  animationFrameId = null;
  const master = whiteVideoRef.value;
  if (!master) return;
  if (browserCameraMode.value) {
    handleMasterClockUpdate();
    if (props.whiteCameraStream && props.fluorescenceCameraStream) {
      animationFrameId = window.requestAnimationFrame(runClockFrame);
    }
    return;
  }
  handleMasterClockUpdate();
  syncPlayback("clock");
  if (!master.paused && !master.ended) {
    animationFrameId = window.requestAnimationFrame(runClockFrame);
  }
}

function stopClockLoop() {
  if (animationFrameId === null) return;
  window.cancelAnimationFrame(animationFrameId);
  animationFrameId = null;
}

function cancelLiveFrameRetry() {
  if (liveFrameRetryTimer === null) return;
  window.clearTimeout(liveFrameRetryTimer);
  liveFrameRetryTimer = null;
}

function setFollowerDrift(role: MultichannelVideoRole, value: number) {
  if (role === "fluorescence") fluorescenceDriftMs.value = value;
  if (role === "device_overlay") deviceOverlayDriftMs.value = value;
}

function registrationText(key: string, fallback: string): string {
  const value = evidenceFrame.value?.registration?.[key];
  return typeof value === "string" && value ? value : fallback;
}

function registrationNumber(key: string): string {
  const value = evidenceFrame.value?.registration?.[key];
  return typeof value === "number" ? value.toFixed(3) : "等待分析";
}

function formatOffset(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)} ms`;
}

function formatTime(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "0:00";
  const seconds = Math.floor(value);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

function formatTimePrecise(value: number): string {
  if (!Number.isFinite(value) || value < 0) return "0.00s";
  return `${value.toFixed(2)}s`;
}

function formatLatency(value: number): string {
  if (!Number.isFinite(value)) return "待记录";
  return value >= 1000 ? `${(value / 1000).toFixed(2)}s` : `${Math.round(value)}ms`;
}

function formatDrift(value: number): string {
  if (!Number.isFinite(value)) return "待记录";
  return `${Math.abs(value).toFixed(0)}ms`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

onBeforeUnmount(() => {
  stopClockLoop();
  cancelLiveFrameRetry();
});
</script>

<style scoped>
.multichannel-workspace {
  display: grid;
  gap: 12px;
  min-width: 0;
  margin-top: 14px;
}

.multichannel-header,
.multichannel-header > div {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.multichannel-header {
  justify-content: space-between;
}

.multichannel-header :deep(.app-icon) {
  width: 17px;
  height: 17px;
  color: var(--ov-primary-strong);
}

.multichannel-header strong {
  color: var(--ov-text);
  font-size: 14px;
}

.multichannel-header span,
.session-state {
  color: var(--ov-text-secondary);
  font-size: 12px;
}

.session-state {
  border: 1px solid var(--ov-border);
  border-radius: 5px;
  padding: 4px 7px;
  background: var(--ov-bg-soft);
  font-weight: 700;
}

.session-state.aligned {
  border-color: var(--ov-success);
  color: var(--ov-success);
}

.session-state.review_required {
  border-color: var(--ov-warning);
  color: var(--ov-warning);
}

.session-state.pending {
  border-color: var(--ov-border-accent);
  background: var(--ov-bg-info);
  color: var(--ov-primary-strong);
}

.multichannel-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-auto-rows: minmax(0, 1fr);
  gap: 12px;
  min-width: 0;
}

.channel-card {
  display: grid;
  grid-template-rows: 42px minmax(0, 1fr) 32px;
  min-width: 0;
  border: 1px solid var(--ov-border);
  border-radius: 6px;
  padding: 8px;
  background: var(--ov-bg-elevated);
}

.channel-card > header,
.channel-card > footer {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
}

.channel-card > header {
  box-sizing: border-box;
  height: 42px;
  padding-bottom: 6px;
  color: var(--ov-text);
  font-size: 13px;
  font-weight: 700;
}

.channel-card > header strong,
.channel-card > footer {
  color: var(--ov-text-muted);
  font-size: 11px;
  line-height: 1.45;
}

.ai-channel-meta {
  display: grid;
  min-width: 0;
  gap: 2px;
  justify-items: end;
  text-align: right;
}

.ai-input-semantics {
  color: var(--ov-primary-strong);
  font-size: 11px;
  font-weight: 800;
  line-height: 1.25;
  overflow-wrap: anywhere;
}

.channel-card > footer {
  box-sizing: border-box;
  height: 32px;
  padding-top: 5px;
  align-content: center;
  overflow: hidden;
  overflow-wrap: anywhere;
}

.media-viewport {
  position: relative;
  display: grid;
  place-items: center;
  min-width: 0;
  min-height: 0;
  aspect-ratio: 4 / 3;
  overflow: hidden;
  border: 1px solid var(--ov-border-strong);
  border-radius: 4px;
  background: var(--ov-bg-media);
}

.refresh-badge {
  position: absolute;
  z-index: 2;
  top: 8px;
  left: 8px;
  max-width: calc(100% - 16px);
  border: 1px solid rgb(255 255 255 / 32%);
  border-radius: 4px;
  padding: 4px 7px;
  background: rgb(8 18 28 / 78%);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  line-height: 1.35;
  overflow-wrap: anywhere;
  pointer-events: none;
}

.refresh-badge.continuous {
  border-color: rgb(64 207 151 / 72%);
}

.refresh-badge.keyframe {
  border-color: rgb(244 178 76 / 72%);
}

.media-viewport video,
.media-viewport img {
  position: absolute;
  inset: 0;
  display: block;
  width: 100%;
  height: 100%;
  max-width: 100%;
  max-height: 100%;
  min-width: 0;
  min-height: 0;
  object-fit: contain;
  object-position: center;
}

.media-viewport .media-source-pending {
  opacity: 0;
  pointer-events: none;
}

.media-state {
  position: absolute;
  z-index: 3;
  inset: 0;
  display: grid;
  place-content: center;
  justify-items: center;
  gap: 9px;
  padding: 24px;
  background: var(--ov-bg-media);
  color: #d8e7f3;
  text-align: center;
}

.media-state :deep(.app-icon) {
  width: 24px;
  height: 24px;
  color: #79b9e2;
}

.media-state:not(.error) :deep(.app-icon) {
  animation: media-loading-spin 1.1s linear infinite;
}

.media-state strong,
.empty-channel strong {
  color: #edf6fc;
  font-size: 13px;
  line-height: 1.4;
}

.media-state span,
.empty-channel span {
  max-width: 34ch;
  color: #8fa8ba;
  font-size: 12px;
  line-height: 1.55;
}

.media-state.error :deep(.app-icon) {
  color: #f2a07d;
}

.media-state button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 32px;
  border: 1px solid rgb(121 185 226 / 62%);
  border-radius: 4px;
  padding: 5px 10px;
  background: rgb(15 49 71 / 88%);
  color: #edf6fc;
  font: inherit;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.media-state button:hover {
  border-color: #9fd2f1;
  background: rgb(24 68 95 / 94%);
}

.media-state button :deep(.app-icon) {
  width: 14px;
  height: 14px;
  color: currentColor;
}

@keyframes media-loading-spin {
  to {
    transform: rotate(360deg);
  }
}

.compact-switch {
  display: inline-flex;
  border: 1px solid var(--ov-border);
  border-radius: 5px;
  padding: 2px;
  background: var(--ov-bg-soft);
}

.compact-switch button {
  min-height: 26px;
  border: 0;
  border-radius: 3px;
  padding: 3px 7px;
  background: transparent;
  color: var(--ov-text-secondary);
  font-size: 11px;
  cursor: pointer;
}

.compact-switch button.active {
  background: var(--ov-bg-elevated);
  color: var(--ov-primary-strong);
  box-shadow: var(--ov-shadow);
}

.compact-switch button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.empty-channel {
  display: grid;
  max-width: 36ch;
  justify-items: center;
  gap: 8px;
  padding: 16px;
  text-align: center;
}

.empty-channel :deep(.app-icon) {
  width: 22px;
  height: 22px;
  color: #6f9dbb;
}

.registration-strip {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 1px;
  margin: 0;
  overflow: hidden;
  border: 1px solid var(--ov-border);
  border-radius: 6px;
  background: var(--ov-border);
}

.registration-strip div {
  min-width: 0;
  padding: 8px 10px;
  background: var(--ov-bg-soft);
}

.registration-strip dt,
.registration-strip dd {
  margin: 0;
  overflow-wrap: anywhere;
}

.registration-strip dt {
  color: var(--ov-text-muted);
  font-size: 11px;
}

.registration-strip dd {
  margin-top: 3px;
  color: var(--ov-text);
  font-size: 12px;
  font-weight: 700;
  line-height: 1.4;
}

@media (max-width: 1180px) {
  .registration-strip {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
</style>
