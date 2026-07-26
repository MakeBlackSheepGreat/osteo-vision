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
            v-if="whiteVideoSrc"
            ref="whiteVideoRef"
            :src="whiteVideoSrc"
            controls
            preload="metadata"
            playsinline
            @loadedmetadata="handleMasterClockUpdate"
            @play="handleMasterPlay"
            @pause="handleMasterPause"
            @seeking="handleMasterSeek"
            @seeked="handleMasterSeek"
            @ratechange="handleMasterRateChange"
            @timeupdate="handleMasterTimeUpdate"
            @ended="handleMasterPause"
          ></video>
          <div v-if="!whiteVideoSrc" class="empty-channel">
            {{ effectiveMode === "composite_layout" ? "准备三视图拆分后显示白光视图" : "请选择白光 MP4" }}
          </div>
        </div>
        <footer>连续主视频 · {{ formatTime(currentTimeSec) }} / {{ formatTime(durationSec) }}</footer>
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
              :disabled="!nearestFrame?.registered_fluorescence_path"
              @click="fluorescenceView = 'registered'"
            >
              配准后
            </button>
          </div>
        </header>
        <div class="media-viewport">
          <video
            v-if="fluorescenceVideoSrc"
            v-show="fluorescenceView === 'raw'"
            ref="fluorescenceVideoRef"
            :src="fluorescenceVideoSrc"
            muted
            preload="metadata"
            playsinline
          ></video>
          <span v-if="fluorescenceView === 'raw' && fluorescenceVideoSrc" class="refresh-badge continuous">
            连续同步 · 漂移 {{ formatDrift(fluorescenceDriftMs) }}
          </span>
          <div v-if="fluorescenceView === 'raw' && !fluorescenceVideoSrc" class="empty-channel">
            {{ effectiveMode === "composite_layout" ? "准备三视图拆分后显示荧光视图" : "请选择荧光 MP4" }}
          </div>
          <img
            v-if="fluorescenceView === 'registered' && nearestFrame?.registered_fluorescence_path"
            :src="apiClient.filePreviewUrl(nearestFrame.registered_fluorescence_path)"
            alt="最近关键帧的配准后荧光图"
          />
          <span
            v-if="fluorescenceView === 'registered' && nearestFrame?.registered_fluorescence_path"
            class="refresh-badge keyframe"
          >
            离线关键帧 · {{ keyframeDeltaLabel }}
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
            v-if="nearestFrame?.overlay_path"
            v-show="fusionView === 'software'"
            :src="apiClient.filePreviewUrl(nearestFrame.overlay_path)"
            alt="最近关键帧的软件配准融合结果"
          />
          <video
            v-if="hasDeviceOverlay"
            v-show="fusionView === 'device'"
            ref="deviceOverlayVideoRef"
            :src="channelVideoUrl('device_overlay')"
            muted
            preload="metadata"
            playsinline
          ></video>
          <img
            v-if="nearestFrame?.device_overlay_difference_path"
            v-show="fusionView === 'difference'"
            :src="apiClient.filePreviewUrl(nearestFrame.device_overlay_difference_path)"
            alt="设备叠加与软件融合差异热图"
          />
          <span v-if="activeFusionContentAvailable" class="refresh-badge" :class="fusionRefreshClass">
            {{ fusionRefreshLabel }}
          </span>
          <div v-if="!activeFusionContentAvailable" class="empty-channel">
            运行双通道融合分析后显示关键帧结果
          </div>
        </div>
        <footer>{{ nearestFrameLabel }}</footer>
      </article>

      <article class="channel-card">
        <header>
          <span>AI 风险与不确定性</span>
          <div class="ai-channel-meta">
            <span class="ai-input-semantics">融合 RGB 关键帧</span>
            <strong>{{ aiPreviewSrc ? "低延迟离线推理" : "等待 AI 输出" }}</strong>
          </div>
        </header>
        <div class="media-viewport">
          <img v-if="aiPreviewSrc" :src="aiPreviewSrc" alt="融合 RGB 关键帧的 AI 风险与不确定性结果" />
          <img
            v-else-if="nearestFrame?.pseudocolor_path"
            :src="apiClient.filePreviewUrl(nearestFrame.pseudocolor_path)"
            alt="最近关键帧的荧光风险伪彩图"
          />
          <span v-if="aiPreviewSrc" class="refresh-badge keyframe">
            AI 关键帧 {{ aiSourceFrameLabel }} · {{ aiPlaybackDeltaLabel }}
          </span>
          <span v-else-if="nearestFrame?.pseudocolor_path" class="refresh-badge keyframe">
            荧光信号伪彩 · 尚无 AI 输出
          </span>
          <div v-else class="empty-channel">等待任务2融合结果进入 AI 分析</div>
        </div>
        <footer>{{ aiFooterLabel }}</footer>
      </article>
    </div>

    <dl class="registration-strip" aria-label="当前关键帧配准证据">
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
        <dt>当前关键帧</dt>
        <dd>{{ nearestFrameLabel }}</dd>
      </div>
    </dl>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from "vue";

import AppIcon from "@/components/AppIcon.vue";
import { apiClient } from "@/services/apiClient";
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

const props = withDefaults(
  defineProps<{
    mode?: MultichannelVideoMode;
    session?: MultichannelVideoSession | null;
    channelPaths?: Partial<Record<MultichannelVideoRole, string>>;
    task2Result?: Record<string, unknown> | null;
    aiPreviewSrc?: string;
  }>(),
  {
    mode: "paired_videos",
    session: null,
    channelPaths: () => ({}),
    task2Result: null,
    aiPreviewSrc: "",
  },
);

const whiteVideoRef = ref<HTMLVideoElement | null>(null);
const fluorescenceVideoRef = ref<HTMLVideoElement | null>(null);
const deviceOverlayVideoRef = ref<HTMLVideoElement | null>(null);
const currentTimeSec = ref(0);
const durationSec = ref(0);
const fluorescenceView = ref<"raw" | "registered">("raw");
const fusionView = ref<"software" | "device" | "difference">("software");
const fluorescenceDriftMs = ref(0);
const deviceOverlayDriftMs = ref(0);
let animationFrameId: number | null = null;
const effectiveMode = computed<MultichannelVideoMode>(() => props.session?.mode ?? props.mode);
const workspaceTitle = computed(() =>
  effectiveMode.value === "composite_layout" ? "合成三视图拆分与配准" : "双通道同步配准",
);
const clockLabel = computed(() =>
  effectiveMode.value === "composite_layout" ? "三视图受控拆分" : "白光主时钟",
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
  return effectiveMode.value === "composite_layout" ? "白光拆分视图" : "白光原始视频";
});
const whiteChannelBadge = computed(() => {
  if (degradedComposite.value) return "单路降级";
  return props.session ? "主时钟" : "待同步";
});

const frames = computed<Task2Frame[]>(() =>
  Array.isArray(props.task2Result?.frames) ? (props.task2Result.frames as Task2Frame[]) : [],
);
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
const keyframePlaybackDeltaMs = computed(() =>
  nearestFrame.value ? Math.abs(nearestFrameTimeSec.value - currentTimeSec.value) * 1000 : null,
);
const keyframeDeltaLabel = computed(() =>
  keyframePlaybackDeltaMs.value === null ? "等待时间戳" : `距播放 ${formatLatency(keyframePlaybackDeltaMs.value)}`,
);
const nearestFrameLabel = computed(() =>
  nearestFrame.value
    ? `关键帧同步结果 · 第 ${Number(nearestFrame.value.frame_index ?? 0) + 1} 帧 · ${formatTimePrecise(nearestFrameTimeSec.value)} · ${keyframeDeltaLabel.value}`
    : "尚无关键帧同步结果",
);
const whiteVideoSrc = computed(() => channelVideoUrl("white_light") || channelVideoUrl("video"));
const fluorescenceVideoSrc = computed(() => channelVideoUrl("fluorescence"));
const hasDeviceOverlay = computed(() =>
  Boolean(channel("device_overlay") || props.channelPaths.device_overlay),
);
const degradedComposite = computed(() => !channel("white_light") && Boolean(channel("video")));
const activeFusionContentAvailable = computed(() => {
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
const aiFooterLabel = computed(() => {
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
  const value = nearestFrame.value?.pair_delta_ms;
  return typeof value === "number" ? `${value.toFixed(2)} ms` : "等待关键帧证据";
});
const transformLabel = computed(() => {
  const registration = nearestFrame.value?.registration;
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
  const registration = nearestFrame.value?.registration;
  if (!registration) return "等待分析";
  if (registration.applied === true && nearestFrame.value?.synchronization_verified === true) return "通过";
  return String(registration.reason || "需要复核");
});

function channel(role: MultichannelVideoRole) {
  return props.session?.channels.find((item) => item.role === role);
}

function channelVideoUrl(role: MultichannelVideoRole): string {
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
}

function handleMasterClockUpdate() {
  const master = whiteVideoRef.value;
  if (!master) return;
  currentTimeSec.value = Number.isFinite(master.currentTime) ? master.currentTime : 0;
  durationSec.value = Number.isFinite(master.duration) ? master.duration : 0;
}

function handleMasterPlay() {
  syncPlayback("play");
  startClockLoop();
}

function handleMasterPause() {
  stopClockLoop();
  syncPlayback("pause");
  handleMasterClockUpdate();
}

function handleMasterSeek() {
  syncPlayback("seek");
  handleMasterClockUpdate();
}

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

function setFollowerDrift(role: MultichannelVideoRole, value: number) {
  if (role === "fluorescence") fluorescenceDriftMs.value = value;
  if (role === "device_overlay") deviceOverlayDriftMs.value = value;
}

function registrationText(key: string, fallback: string): string {
  const value = nearestFrame.value?.registration?.[key];
  return typeof value === "string" && value ? value : fallback;
}

function registrationNumber(key: string): string {
  const value = nearestFrame.value?.registration?.[key];
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

onBeforeUnmount(stopClockLoop);
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
  gap: 12px;
  min-width: 0;
}

.channel-card {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
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
  min-height: 28px;
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
  min-height: 24px;
  padding-top: 5px;
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
  max-width: 28ch;
  padding: 16px;
  color: var(--ov-text-muted);
  font-size: 13px;
  line-height: 1.5;
  text-align: center;
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
