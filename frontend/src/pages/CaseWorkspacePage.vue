<template>
  <main class="case-workspace">
    <header class="workspace-header">
      <div class="workspace-title">
        <p>术中影像工作台</p>
        <h1>颌骨骨髓炎术中辅助决策平台</h1>
      </div>
      <div class="workspace-header-actions">
        <div class="workspace-context" aria-label="当前工作区状态">
          <span>{{ store.currentCase?.title || "未载入病例" }}</span>
          <strong :class="analysisStatusClass">{{ latestRunStatusLabel }}</strong>
        </div>
        <RouterLink
          v-if="store.currentCase"
          class="navigation-workspace-link"
          :to="navigationWorkspaceRoute"
          title="打开与当前病例、视频候选区和配准证据联动的三维导航页面"
        >
          <AppIcon name="cube" />
          <span>
            <strong>三维导航</strong>
            <small>{{ threeDWorkspaceStatus }}</small>
          </span>
        </RouterLink>
      </div>
    </header>

    <details class="review-notice" aria-live="polite">
      <summary>
        <AppIcon class="notice-icon" name="alert" variant="badge" tone="amber" />
        <strong>医生复核边界</strong>
        <span>关键判断需医生确认。</span>
      </summary>
      <p>
        该系统输出的 ICG 荧光信号与风险提示仅供术中医生参考，不能替代医生的专业判断与临床决策。
        所有关键操作与治疗决策均须由具备资质的医生进行复核与确认。
      </p>
    </details>

    <section class="workspace-grid">
      <aside class="workspace-sidebar" aria-label="输入控制与结果摘要">
        <CaseWorkspaceControls
          v-model:input-mode="inputMode"
          v-model:video-timepoints="videoTimepoints"
          v-model:alpha="alpha"
          v-model:threshold="threshold"
          v-model:colormap="colormap"
          :white-light-path="whiteLightPath"
          :fluorescence-path="fluorescencePath"
          :device-overlay-path="deviceOverlayPath"
          :video-path="videoPath"
          :loading="store.loading"
          :has-case="Boolean(store.currentCase)"
          :is-uploading-white="isUploadingWhite"
          :is-uploading-fluorescence="isUploadingFluorescence"
          :is-uploading-device-overlay="isUploadingDeviceOverlay"
          :is-uploading-video="isUploadingVideo"
          :is-loading-video-candidates="isLoadingVideoCandidates"
          :is-loading-video-preview="isLoadingVideoPreview"
          :selected-video-candidate-id="selectedVideoCandidateId"
          :selected-video-candidate-preview-src="selectedVideoCandidatePreviewSrc"
          :video-candidates="videoCandidates"
          :operation-message="operationMessage"
           :operation-message-type="operationMessageType"
           :image-pair-ready="imagePairReady"
           :image-pair-options="imagePairOptions"
           :selected-image-pair-key="selectedImagePairKey"
           :analysis-job-polling="store.analysisJobPolling"
           :video-ready="videoReady"
          :camera-active="cameraActive"
          :camera-opening="isOpeningCamera"
          :camera-manual-analysis-busy="cameraManualAnalysisBusy"
          :camera-analysis-running="cameraAnalysisRunning"
          :camera-continuous-analysis-starting="cameraContinuousAnalysisStarting"
          :camera-continuous-analysis-active="cameraContinuousAnalysisActive"
          :camera-analysis-interval-sec="cameraAnalysisIntervalSec"
          :camera-continuous-analysis-status="cameraContinuousAnalysisStatus"
          :camera-status-label="cameraStatusLabel"
          :file-video-active="fileVideoActive"
          :video-realtime-analysis-status="videoRealtimeAnalysisStatus"
          :live-session-ready="Boolean(store.currentCase)"
          @file-picked="handleFilePicked"
          @load-video-candidates="loadVideoCandidates"
          @select-video-candidate="selectVideoCandidate"
          @import-video-candidate="importSelectedVideoCandidate"
           @run-analysis="runAnalysis"
           @select-image-pair="selectImagePair"
          @run-video-file-analysis="runVideoFileAnalysis"
          @start-camera="openCameraForLiveAnalysis"
          @stop-camera="stopCameraInput"
          @capture-camera-frame="captureAndAnalyzeBrowserCameraFrame"
          @start-continuous-camera-analysis="startContinuousCameraAnalysis"
          @stop-continuous-camera-analysis="stopContinuousCameraAnalysis"
          @update-camera-analysis-interval="setCameraAnalysisInterval"
        />

        <ClinicalContextPanel
          v-if="store.currentCase"
          :context="store.currentCase.clinical_context ?? emptyClinicalContext()"
          :assessment="clinicalContextAssessment"
          :disabled="store.loading"
          :save-status="clinicalContextSaveStatus"
          :save-error="clinicalContextSaveError"
          @save="saveClinicalContext"
        />

        <details v-if="showResultSummary" class="sidebar-summary-details">
          <summary>
            <span>结果摘要</span>
            <strong>{{ displayCandidates.length }} 项候选</strong>
          </summary>
          <AnalysisResultPanels
            :candidates="displayCandidates"
            :metrics="displayMetricMap"
          />
        </details>
      </aside>

      <section class="analysis-column" aria-label="分析结果">
        <ThreeChannelQualityPanel
          :quality="threeChannelQuality"
          :preview-url="apiClient.filePreviewUrl"
          :download-url="apiClient.fileDownloadUrl"
        />
        <PatientConditioningEvidencePanel
          :evidence="patientConditioningEvidence"
          :preview-url="apiClient.filePreviewUrl"
          :download-url="apiClient.fileDownloadUrl"
        />
        <BoneActivityCheckpointEvidencePanel
          :evidence="boneActivityCheckpointEvidence"
          :download-url="apiClient.fileDownloadUrl"
        />
        <ViabilitySpectrumPanel
          :spectrum="boneActivitySpectrum"
          :preview-url="apiClient.filePreviewUrl"
          :download-url="apiClient.fileDownloadUrl"
        />
        <AnalysisWorkspaceCard
          ref="analysisWorkspaceCardRef"
          :loading="store.loading"
          :error="store.error"
          :has-case="Boolean(store.currentCase)"
          :export-path="store.exportPath"
          :export-links="exportLinks"
          :export-summary="store.exportResult?.summary ?? {}"
          :export-artifact-entries="store.exportResult?.artifact_entries ?? []"
          :active-analysis-job-id="store.activeAnalysisJobId"
          :active-analysis-job-status="store.activeAnalysisJobStatus"
          :active-analysis-job-error="store.activeAnalysisJobError"
          :active-analysis-job-progress="store.activeAnalysisJobProgress"
          :last-analysis-job-timed-out="store.lastAnalysisJobTimedOut"
          :active-analysis-job-canceling="isCancelingAnalysisJob"
          :latest-run-status-label="latestRunStatusLabel"
          :analysis-status-class="analysisStatusClass"
          :kpi-items="kpiItems"
          :preview-panels="previewPanels"
          :hotspot-timeline-items="hotspotTimelineItems"
          :hotspot-timeline-total-count="allHotspotTimelineItems.length"
          :hotspot-timeline-filter="hotspotTimelineFilter"
          :selected-hotspot-timeline-key="selectedHotspotTimelineKey"
          :selected-hotspot-frame-detail="selectedHotspotFrameDetail"
          :bone-gate-candidate-frame-indexes="boneGateCandidateFrameIndexes"
          :hotspot-frame-details="hotspotFrameDetails"
          :timeline-manifest-summary="timelineManifestSummary"
          :fusion-evidence-summary="fusionEvidenceSummary"
          :video-playback="videoPlaybackAnalysis"
          :camera-stream="cameraStream"
          :camera-active="cameraActive"
          :camera-status-label="cameraStatusLabel"
          :live-overlay-src="liveOverlaySrc"
          :live-frame-status="liveFrameStatus"
          :live-model-latency-ms="liveModelLatencyMs"
          :live-end-to-end-latency-ms="liveEndToEndLatencyMs"
          :analysis-expanded="analysisExpanded"
          @export="exportCase"
          @refresh-job="refreshAnalysisJob"
          @cancel-job="cancelAnalysisJob"
          @retry-job="retryAnalysisJob"
          @reanalyze-hotspot-frame="reanalyzeSelectedHotspotFrame"
          @generate-bone-gate-for-frame="generateBoneGateForSelectedFrame"
          @save-bone-gate-mask-edit="saveBoneGateMaskEditForSelectedFrame"
          @select-hotspot-frame="selectHotspotFrame"
          @update-hotspot-timeline-filter="updateHotspotTimelineFilter"
          @playback-started="startVideoPlaybackAnalysis"
          @playback-paused="pauseVideoPlaybackAnalysis"
          @playback-ended="endVideoPlaybackAnalysis"
          @open-fullscreen="openAnalysisFullscreen"
          @close-fullscreen="closeAnalysisFullscreen"
        />

        <details v-if="showDebugPanel" class="debug-panel">
          <summary>开发调试数据</summary>
          <pre>{{ store.currentCase }}</pre>
        </details>
      </section>

    </section>

  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useRoute } from "vue-router";

import AnalysisResultPanels from "@/components/AnalysisResultPanels.vue";
import AnalysisWorkspaceCard from "@/components/AnalysisWorkspaceCard.vue";
import BoneActivityCheckpointEvidencePanel from "@/components/BoneActivityCheckpointEvidencePanel.vue";
import CaseWorkspaceControls from "@/components/CaseWorkspaceControls.vue";
import ClinicalContextPanel from "@/components/ClinicalContextPanel.vue";
import PatientConditioningEvidencePanel from "@/components/PatientConditioningEvidencePanel.vue";
import ThreeChannelQualityPanel from "@/components/ThreeChannelQualityPanel.vue";
import ViabilitySpectrumPanel from "@/components/ViabilitySpectrumPanel.vue";
import { boneActivityCheckpointEvidenceForFrame } from "@/utils/boneActivityCheckpointEvidence";
import { boneActivitySpectrumForFrame } from "@/utils/boneActivitySpectrum";
import { patientConditioningEvidenceForFrame } from "@/utils/patientConditioningEvidence";
import { threeChannelQualityForFrame } from "@/utils/threeChannelQuality";
import AppIcon from "@/components/AppIcon.vue";
import {
  filterHotspotTimelineItems,
  candidateOverlaysFromRegions,
  fusionEvidenceSummaryFromRun,
  hotspotFrameDetailsFromRun,
  hotspotTimelineFromRun,
  roiOverlaysFromRegions,
  selectedHotspotFrameDetailFromRun,
  timelineManifestSummaryFromRun,
  type AnalysisPreviewPanel,
  type FusionEvidenceSummary,
  type HotspotFrameDetail,
  type HotspotTimelineFilter,
  type VideoPlaybackAnalysis,
  videoPlaybackAnalysisFromRun,
  videoPreviewPanelsFromRun,
} from "@/components/analysisPreview";
import type { AppIconName } from "@/components/appIcons";
import { useBrowserCamera } from "@/composables/useBrowserCamera";
import {
  isDisplayableLiveFrame,
  isCurrentLiveFrameDisplay,
  useContinuousCameraAnalysis,
  type ContinuousCameraFrameContext,
  type ContinuousCameraAnalysisIntervalSec,
  type ContinuousCameraFrameInvalidationReason,
  type LiveFrameDisplayIdentity,
} from "@/composables/useContinuousCameraAnalysis";
import { useFullscreenPanel } from "@/composables/useFullscreenPanel";
import { useOperationMessage } from "@/composables/useOperationMessage";
import { apiClient } from "@/services/apiClient";
import type { LiveFrameAnalysisResult } from "@/services/apiClient";
import { useCaseStore } from "@/stores/caseStore";
import type { CandidateRegion, CaseInputAsset, ClinicalContext, ClinicalContextAssessment, RegionOfInterest, VideoCandidate } from "@/types/case";
import { candidateForHotspotFrame, candidateFrameIndexes } from "@/utils/boneGateActions";
import { caseImagePairs, imagePairLabel, selectedImageInputIds } from "@/utils/caseInputPairs";
import {
  colormapLabel,
  errorMessage,
  isRecord,
  normalizeWarning,
  runStatusLabel,
  stringFrom,
} from "@/utils/caseDisplay";
import {
  countLabel,
  hotspotFrameSelection,
  officialProfileLabel,
  parseVideoTimepoints,
  videoFileAnalysisParameters,
  type PlatformColormap,
} from "@/utils/videoAnalysisParams";

const store = useCaseStore();
const route = useRoute();

// 页面层保留业务流程编排：上传、写入病例、触发分析和导出。
const whiteLightPath = ref("");
const fluorescencePath = ref("");
const deviceOverlayPath = ref("");
const selectedImagePairKey = ref("");
const videoPath = ref("");
const inputMode = ref<"video" | "images">("video");
const videoTimepoints = ref("");
const syncedCaseId = ref("");
const alpha = ref(0.45);
const threshold = ref(0.6);
const colormap = ref<PlatformColormap>("green");
const isUploadingWhite = ref(false);
const isUploadingFluorescence = ref(false);
const isUploadingDeviceOverlay = ref(false);
const isUploadingVideo = ref(false);
const isLoadingVideoCandidates = ref(false);
const isLoadingVideoPreview = ref(false);
const videoCandidates = ref<VideoCandidate[]>([]);
const selectedVideoCandidateId = ref("");
const selectedVideoCandidatePreviewSrc = ref("");
const selectedHotspotTimelineKey = ref("");
const isCancelingAnalysisJob = ref(false);
const liveFrameResult = ref<LiveFrameAnalysisResult | null>(null);
const liveFrameSource = ref<"camera" | "video" | "">("");
const LIVE_FRAME_MAX_AGE_MS = 15_000;
const liveFrameExpectedIdentity = ref<LiveFrameDisplayIdentity | null>(null);
const liveFrameDisplayIdentity = ref<LiveFrameDisplayIdentity | null>(null);
const liveFrameStaleStatus = ref("");
let liveFrameExpiryTimer: number | null = null;
const cameraManualAnalysisBusy = ref(false);
const hotspotTimelineFilter = ref<HotspotTimelineFilter>("all");
const analysisWorkspaceCardRef = ref<InstanceType<typeof AnalysisWorkspaceCard> | null>(null);
const videoPlaybackPlaying = ref(false);
const showDebugPanel =
  import.meta.env.DEV &&
  typeof window !== "undefined" &&
  new URLSearchParams(window.location.search).has("debug");
const { operationMessage, operationMessageType, setOperationMessage } = useOperationMessage();
const {
  expanded: analysisExpanded,
  open: openAnalysisFullscreen,
  close: closeAnalysisFullscreen,
} = useFullscreenPanel();
const liveSessionCreatePromise = ref<Promise<boolean> | null>(null);
const liveModelWarmupPromise = ref<Promise<void> | null>(null);
let liveFrameRequestGeneration = 0;
let liveFrameRequestController: AbortController | null = null;
let liveFrameRequestSource: "camera" | "video" | "" = "";
let liveAnalysisSourceGeneration = 0;

watch(
  () => route.query.caseId,
  async (value) => {
    const caseId = Array.isArray(value) ? value[0] : value;
    if (!caseId || typeof caseId !== "string" || store.currentCase?.case_id === caseId) return;
    setOperationMessage(`正在载入病例：${caseId}...`);
    await store.loadCase(caseId);
    const loaded = store.currentCase?.case_id === caseId;
    setOperationMessage(loaded ? `病例已载入：${caseId}` : store.error || "病例载入失败", loaded ? "info" : "error");
  },
  { immediate: true },
);
const {
  cameraStream,
  cameraActive,
  isOpeningCamera,
  cameraStatusLabel,
  startCameraInput,
  stopCameraInput,
  captureCameraFrame,
} = useBrowserCamera({
  onMessage: setOperationMessage,
  onStop: () => {
    stopContinuousCameraAnalysis(false);
    clearLiveFrameResult("camera");
  },
});

const {
  active: cameraContinuousAnalysisActive,
  starting: cameraContinuousAnalysisStarting,
  running: cameraAnalysisRunning,
  intervalSec: cameraAnalysisIntervalSec,
  statusLabel: cameraContinuousAnalysisStatus,
  setIntervalSec: setCameraAnalysisIntervalLoop,
  start: startContinuousCameraAnalysisLoop,
  stop: stopContinuousCameraAnalysisLoop,
} = useContinuousCameraAnalysis({
  captureFrame: captureCameraFrame,
  analyzeFrame: analyzeContinuousCameraFrame,
  canAnalyze: () => Boolean(cameraActive.value && !cameraManualAnalysisBusy.value),
  beforeStart: prepareContinuousCameraAnalysis,
  onFrameInvalidated: (reason, context) => handleLiveFrameInvalidation("camera", reason, context),
  onMessage: setOperationMessage,
});

const {
  active: videoPlaybackAnalysisActive,
  running: videoPlaybackAnalysisRunning,
  statusLabel: videoPlaybackAnalysisLoopStatus,
  start: startVideoPlaybackAnalysisLoop,
  stop: stopVideoPlaybackAnalysisLoop,
} = useContinuousCameraAnalysis({
  captureFrame: captureVideoPlaybackFrame,
  analyzeFrame: analyzeContinuousVideoFrame,
  canAnalyze: () =>
    Boolean(videoPlaybackPlaying.value && fileVideoActive.value && analysisWorkspaceCardRef.value),
  getTimestampSec: () => analysisWorkspaceCardRef.value?.currentPlaybackTimeSec(),
  beforeStart: prepareVideoPlaybackAnalysis,
  onFrameInvalidated: (reason, context) => handleLiveFrameInvalidation("video", reason, context),
  onMessage: setOperationMessage,
});

const latestRun = computed(() => store.currentCase?.analysis_runs.at(-1) ?? null);
const clinicalContextAssessment = computed(() => {
  const value = latestRun.value?.parameters?.clinical_context_assessment;
  return isRecord(value) ? value as ClinicalContextAssessment : null;
});
const clinicalContextSaveStatus = ref<"idle" | "saving" | "success" | "error">("idle");
const clinicalContextSaveError = ref("");
const inputAssets = computed(() => store.currentCase?.inputs ?? []);
const availableImagePairs = computed(() => caseImagePairs(inputAssets.value));
const imagePairOptions = computed(() =>
  availableImagePairs.value.map((pair) => ({ key: pair.key, label: imagePairLabel(pair) })),
);
const selectedImageInputIdList = computed(() =>
  selectedImageInputIds(inputAssets.value, whiteLightPath.value, fluorescencePath.value, deviceOverlayPath.value),
);
const latestInputPathByChannel = computed(() => {
  const latest = new Map<CaseInputAsset["channel"], string>();
  for (const asset of inputAssets.value) {
    latest.set(asset.channel, asset.path);
  }
  return latest;
});
const imagePairReady = computed(
  () => selectedImageInputIdList.value.length === 2,
);
const videoReady = computed(
  () => Boolean(videoPath.value) && latestInputPathByChannel.value.get("video") === videoPath.value,
);
const metricEntries = computed(() => Object.entries(latestRun.value?.quantitative_summary ?? {}));
const latestCandidates = computed<CandidateRegion[]>(() => latestRun.value?.candidate_regions ?? []);
const boneGateCandidateFrameIndexes = computed(() => candidateFrameIndexes(latestCandidates.value));
const latestMode = computed(() => stringFrom(latestRun.value?.fused_outputs?.mode));
const outputPaths = computed<Record<string, unknown>>(() => {
  const fusedOutputs = latestRun.value?.fused_outputs ?? {};
  const nestedOutputs = isRecord(fusedOutputs.outputs) ? fusedOutputs.outputs : {};
  return { ...fusedOutputs, ...nestedOutputs };
});

const displayInputAssets = computed<CaseInputAsset[]>(() => (store.currentCase ? inputAssets.value : []));
const displayCandidates = computed<CandidateRegion[]>(() => (store.currentCase ? latestCandidates.value : []));
const exportLinks = computed(() => {
  const result = store.exportResult;
  if (!result) return [];
  const links = [
    { label: "证据包 ZIP", path: result.bundle_path },
    { label: "JSON 报告", path: result.report_path },
    { label: "导出清单", path: result.manifest_path },
    { label: "DICOM 二次捕获", path: result.dicom_path ?? "" },
  ];
  return links
    .filter((item) => item.path)
    .map((item) => ({
      ...item,
      href: apiClient.fileDownloadUrl(item.path),
    }));
});

const displayMetricMap = computed<Record<string, unknown>>(() => {
  if (metricEntries.value.length) return Object.fromEntries(metricEntries.value);
  return {};
});
const showResultSummary = computed(
  () => Boolean(store.currentCase) || displayCandidates.value.length > 0 || Object.keys(displayMetricMap.value).length > 0,
);

const latestRunStatusLabel = computed(() => {
  if (store.loading) return "运行中";
  if (!store.currentCase) return "未载入";
  return runStatusLabel(latestRun.value?.status);
});
const analysisStatusClass = computed(() => {
  if (store.loading) return "running";
  if (!store.currentCase) return "idle";
  if (latestRun.value?.status === "failed") return "failed";
  if (latestRun.value?.status === "completed") return "completed";
  return "idle";
});

const kpiItems = computed<Array<{ label: string; value: string; icon: AppIconName }>>(() => [
  { label: "分析任务", value: latestMode.value === "video_file_keyframes" ? "MP4 视频分析" : "JPEG 图像融合", icon: "clipboard" },
  { label: "输入通道", value: `${displayInputAssets.value.length} 个`, icon: "layers" },
  { label: "候选区域", value: String(displayCandidates.value.length), icon: "target" },
  { label: "分析状态", value: latestRunStatusLabel.value, icon: "document" },
]);

const previewPanels = computed<AnalysisPreviewPanel[]>(() => {
  const overlays = previewOverlays.value;
  const livePanels = livePreviewPanels.value;
  if (livePanels.length) return livePanels.map((panel) => ({ ...panel, overlays }));
  const videoPanels = videoPreviewPanelsFromRun(
    latestRun.value,
    apiClient.filePreviewUrl,
    selectedHotspotTimelineKey.value,
  );
  if (videoPanels.length) return videoPanels.slice(0, 3).map((panel) => ({ ...panel, overlays }));
  return [
    previewPanel("融合图", `融合透明度: ${alpha.value.toFixed(2)}`, `伪彩方案: ${colormapLabel(colormap.value)}`, "白光 + ICG", stringFrom(outputPaths.value.overlay_path)),
    previewPanel("热图", `当前阈值: ${threshold.value.toFixed(2)}`, "色标范围: 0 - 1", "0        1.0", stringFrom(outputPaths.value.heatmap_path)),
    previewPanel("归一化图", "归一化方法: Min-Max", "范围: 0 - 1", "归一化荧光", stringFrom(outputPaths.value.normalized_fluorescence_path)),
  ].map((panel) => ({ ...panel, overlays }));
});

const allHotspotTimelineItems = computed(() => hotspotTimelineFromRun(latestRun.value, apiClient.filePreviewUrl));
const hotspotTimelineItems = computed(() =>
  filterHotspotTimelineItems(allHotspotTimelineItems.value, hotspotTimelineFilter.value),
);
const selectedHotspotFrameDetail = computed<HotspotFrameDetail | null>(() =>
  selectedHotspotFrameDetailFromRun(latestRun.value, apiClient.filePreviewUrl, selectedHotspotTimelineKey.value),
);
const boneActivitySpectrum = computed<Record<string, unknown> | null>(() => boneActivitySpectrumForFrame(
  latestRun.value,
  {
    key: selectedHotspotTimelineKey.value || selectedHotspotFrameDetail.value?.key,
    frameIndex: selectedHotspotFrameDetail.value?.frameIndex,
  },
));
const boneActivityCheckpointEvidence = computed<Record<string, unknown> | null>(() => (
  boneActivityCheckpointEvidenceForFrame(
    latestRun.value,
    {
      key: selectedHotspotTimelineKey.value || selectedHotspotFrameDetail.value?.key,
      frameIndex: selectedHotspotFrameDetail.value?.frameIndex,
    },
  )
));
const patientConditioningEvidence = computed<Record<string, unknown> | null>(() => patientConditioningEvidenceForFrame(
  latestRun.value,
  {
    key: selectedHotspotTimelineKey.value || selectedHotspotFrameDetail.value?.key,
    frameIndex: selectedHotspotFrameDetail.value?.frameIndex,
  },
));
const threeChannelQuality = computed<Record<string, unknown> | null>(() => threeChannelQualityForFrame(
  latestRun.value,
  {
    key: selectedHotspotTimelineKey.value || selectedHotspotFrameDetail.value?.key,
    frameIndex: selectedHotspotFrameDetail.value?.frameIndex,
  },
));
const hotspotFrameDetails = computed<HotspotFrameDetail[]>(() =>
  hotspotFrameDetailsFromRun(latestRun.value, apiClient.filePreviewUrl),
);
const timelineManifestSummary = computed(() =>
  timelineManifestSummaryFromRun(latestRun.value, apiClient.fileDownloadUrl),
);
const fusionEvidenceSummary = computed<FusionEvidenceSummary | null>(() =>
  fusionEvidenceSummaryFromRun(latestRun.value, apiClient.filePreviewUrl),
);
const videoPlaybackAnalysis = computed<VideoPlaybackAnalysis | null>(() =>
  videoPlaybackAnalysisFromRun(
    latestRun.value,
    displayInputAssets.value,
    apiClient.fileVideoUrl,
    apiClient.filePreviewUrl,
    videoPath.value,
  ),
);
const fileVideoActive = computed(() => Boolean(videoPlaybackAnalysis.value?.videoSrc));
const activeLiveFrameSource = computed<"camera" | "video" | "">(() => {
  if (fileVideoActive.value) return "video";
  if (cameraActive.value) return "camera";
  return "";
});
const liveFrameIsCurrent = computed(() => {
  return isCurrentLiveFrameDisplay(
    liveFrameResult.value,
    liveFrameDisplayIdentity.value,
    liveFrameExpectedIdentity.value,
    {
      activeSource: activeLiveFrameSource.value,
      caseId: store.currentCase?.case_id ?? "",
      requestGeneration: liveFrameRequestGeneration,
      nowMs: Date.now(),
      maxAgeMs: LIVE_FRAME_MAX_AGE_MS,
    },
  );
});
const liveFrameIsDisplayable = computed(() =>
  isDisplayableLiveFrame(
    liveFrameResult.value,
    liveFrameDisplayIdentity.value,
    {
      activeSource: activeLiveFrameSource.value,
      caseId: store.currentCase?.case_id ?? "",
      nowMs: Date.now(),
      maxAgeMs: LIVE_FRAME_MAX_AGE_MS,
    },
  ),
);
const liveOverlaySrc = computed(() =>
  liveFrameIsDisplayable.value && liveFrameResult.value?.overlay_path
    ? apiClient.filePreviewUrl(liveFrameResult.value.overlay_path)
    : "",
);
const liveFrameStatus = computed(() => {
  const result = liveFrameResult.value;
  if (!result || !liveFrameIsDisplayable.value) return liveFrameStaleStatus.value;
  if (!liveFrameIsCurrent.value) {
    return liveFrameStaleStatus.value || "上一帧实时结果保留，正在处理下一帧。";
  }
  return `${liveFrameSource.value === "video" ? "MP4 实时分割" : "实时分割"}已更新 · ${result.frame_id.slice(-6)}`;
});
const liveModelLatencyMs = computed(() =>
  liveFrameIsDisplayable.value
    ? liveFrameResult.value?.model_inference_latency_ms ?? liveFrameResult.value?.performance?.model_ms ?? null
    : null,
);
const liveEndToEndLatencyMs = computed(() =>
  liveFrameIsDisplayable.value ? liveFrameResult.value?.inference_latency_ms ?? null : null,
);
const videoRealtimeAnalysisStatus = computed(() => {
  if (videoPlaybackAnalysisRunning.value) return "MP4 逐帧实时分割正在处理当前播放帧。";
  if (videoPlaybackAnalysisActive.value) {
    return `MP4 逐帧实时分割已启动，已完成 ${videoPlaybackAnalysisLoopStatus.value.replace(/^.*已完成 /, "")}`;
  }
  return "MP4 播放后将自动启动逐帧实时分割。";
});
const navigationWorkspaceRoute = computed(() => ({
  path: "/navigation",
  query: { caseId: store.currentCase?.case_id ?? "" },
}));
const threeDWorkspaceStatus = computed(() => {
  const evidence = store.currentCase?.three_d_evidence;
  if (!isRecord(evidence) || !Object.keys(evidence).length) return "模型待接入";
  const registrationStatus = stringFrom(evidence.registration_status).toLowerCase();
  const navigationReady = evidence.navigation_ready === true || stringFrom(evidence.navigation_ready).toLowerCase() === "true";
  if (registrationStatus === "registered" && navigationReady) return "配准证据已记录";
  if (stringFrom(evidence.model_path)) return "模型已接入 / 未配准";
  return "三维证据待完善";
});
const previewOverlays = computed(() => [
  ...roiOverlaysFromRegions(store.currentCase?.rois ?? []),
  ...candidateOverlaysFromRegions(latestCandidates.value),
]);

watch(
  () =>
    store.currentCase
      ? [
          store.currentCase.case_id,
          ...store.currentCase.inputs.map(
            (asset) =>
              `${asset.input_id}:${asset.channel}:${asset.path}:${stringFrom(asset.metadata.pair_id)}:${stringFrom(asset.metadata.batch_id)}`,
          ),
        ].join("|")
      : "",
  () => {
    syncInputPathsFromCase();
  },
  { immediate: true },
);

watch(
  () => hotspotTimelineItems.value.map((item) => item.key).join("|"),
  () => {
    if (!hotspotTimelineItems.value.length) {
      selectedHotspotTimelineKey.value = "";
      return;
    }
    if (!hotspotTimelineItems.value.some((item) => item.key === selectedHotspotTimelineKey.value)) {
      selectedHotspotTimelineKey.value = hotspotTimelineItems.value[0].key;
    }
  },
  { immediate: true },
);

watch(
  () => [
    route.query.frameKey,
    store.navigationFrameSelection?.frameKey,
    store.navigationFrameSelection?.caseId,
    allHotspotTimelineItems.value.map((item) => item.key).join("|"),
  ],
  () => {
    const routeFrameKey = Array.isArray(route.query.frameKey) ? route.query.frameKey[0] : route.query.frameKey;
    const sharedSelection = store.navigationFrameSelection;
    const sharedFrameKey =
      sharedSelection && sharedSelection.caseId === store.currentCase?.case_id ? sharedSelection.frameKey : "";
    const requestedFrameKey = typeof routeFrameKey === "string" && routeFrameKey ? routeFrameKey : sharedFrameKey;
    if (!requestedFrameKey) return;
    if (allHotspotTimelineItems.value.some((item) => item.key === requestedFrameKey)) {
      selectedHotspotTimelineKey.value = requestedFrameKey;
    }
  },
  { immediate: true },
);

watch(
  () => videoPlaybackAnalysis.value?.videoSrc ?? "",
  (source, previousSource) => {
    if (source === previousSource) return;
    if (previousSource) {
      liveAnalysisSourceGeneration += 1;
      videoPlaybackPlaying.value = false;
      stopVideoPlaybackAnalysisLoop(false);
      invalidateLiveFrameRequest("video");
      clearLiveFrameResult("video");
    }
    if (source) {
      if (
        !previousSource &&
        (cameraContinuousAnalysisActive.value || liveFrameSource.value === "camera" || liveFrameRequestSource === "camera")
      ) {
        liveAnalysisSourceGeneration += 1;
        stopContinuousCameraAnalysisLoop(false);
        invalidateLiveFrameRequest("camera");
        clearLiveFrameResult("camera");
      }
      void warmupLiveFrameModel().catch(() => undefined);
    }
  },
);

watch(videoPath, (source, previousSource) => {
  if (source === previousSource || !previousSource) return;
  liveAnalysisSourceGeneration += 1;
  videoPlaybackPlaying.value = false;
  stopVideoPlaybackAnalysisLoop(false);
  invalidateLiveFrameRequest("video");
  clearLiveFrameResult("video");
});

function previewPanel(title: string, tag: string, label: string, scale: string, path: string): AnalysisPreviewPanel {
  return {
    title,
    tag,
    label,
    scale,
    path,
    previewSrc: path ? apiClient.filePreviewUrl(path) : undefined,
  };
}

function syncInputPathsFromCase() {
  const caseRecord = store.currentCase;
  if (!caseRecord) {
    syncedCaseId.value = "";
    return;
  }
  const caseChanged = syncedCaseId.value !== caseRecord.case_id;
  if (caseChanged) {
    syncedCaseId.value = caseRecord.case_id;
    whiteLightPath.value = "";
    fluorescencePath.value = "";
    deviceOverlayPath.value = "";
    selectedImagePairKey.value = "";
    videoPath.value = "";
  }
  const latestByChannel = (channel: CaseInputAsset["channel"]) =>
    [...caseRecord.inputs].reverse().find((asset) => asset.channel === channel)?.path ?? "";
  const defaultPair = availableImagePairs.value.at(-1);
  if (caseChanged && defaultPair) {
    selectedImagePairKey.value = defaultPair.key;
    whiteLightPath.value = defaultPair.whiteLight.path;
    fluorescencePath.value = defaultPair.fluorescence.path;
    deviceOverlayPath.value = defaultPair.deviceOverlay?.path ?? "";
  }
  const white = latestByChannel("white_light");
  const fluorescence = latestByChannel("fluorescence");
  const video = latestByChannel("video");
  const deviceOverlay = latestByChannel("device_overlay");
  if (white && ((!defaultPair && caseChanged) || !whiteLightPath.value.trim())) whiteLightPath.value = white;
  if (fluorescence && ((!defaultPair && caseChanged) || !fluorescencePath.value.trim())) {
    fluorescencePath.value = fluorescence;
  }
  if (video && (caseChanged || !videoPath.value.trim())) videoPath.value = video;
  if (deviceOverlay && (caseChanged || !deviceOverlayPath.value.trim())) deviceOverlayPath.value = deviceOverlay;
}

function selectHotspotFrame(key: string) {
  selectedHotspotTimelineKey.value = key;
}

function updateHotspotTimelineFilter(filter: HotspotTimelineFilter) {
  hotspotTimelineFilter.value = filter;
}

async function importVideoInput(): Promise<boolean> {
  if (!store.currentCase) {
    setOperationMessage("请先新建或加载病例。", "error");
    return false;
  }
  const source = videoPath.value.trim();
  if (!source) {
    setOperationMessage("请先选择 MP4 视频。", "error");
    return false;
  }
  const exists = [...store.currentCase.inputs]
    .reverse()
    .some((asset) => asset.channel === "video" && asset.path === source);
  if (exists) {
    return true;
  }
  await store.importInputs([
    {
      channel: "video",
      path: source,
      mime_type: "video/mp4",
      metadata: {
        acquisition_mode: "official_mp4_upload",
        official_format: "MP4",
      },
    },
  ]);
  const ok = !store.error;
  if (!ok) setOperationMessage(store.error, "error");
  return ok;
}

function selectImagePair(pairKey: string) {
  const pair = availableImagePairs.value.find((candidate) => candidate.key === pairKey);
  if (!pair) return;
  selectedImagePairKey.value = pair.key;
  whiteLightPath.value = pair.whiteLight.path;
  fluorescencePath.value = pair.fluorescence.path;
  deviceOverlayPath.value = pair.deviceOverlay?.path ?? "";
  setOperationMessage(`已选择同步图像对 ${imagePairLabel(pair)}。`);
}

const livePreviewPanels = computed<AnalysisPreviewPanel[]>(() => {
  const result = liveFrameResult.value;
  if (!result || !liveFrameIsDisplayable.value) return [];
  const sourceLabel = liveFrameSource.value === "video" ? "MP4 播放帧" : "摄像头帧";
  return [
    previewPanel(
      "实时分割掩膜",
      sourceLabel,
      `推理 ${Math.round(result.inference_latency_ms)} ms`,
      "二值掩膜",
      result.mask_path || result.probability_path || "",
    ),
    previewPanel(
      "实时风险图",
      sourceLabel,
      "荧光/灌注风险提示",
      "风险掩膜",
      result.risk_mask_path || result.pseudo_color_path || "",
    ),
    previewPanel(
      "实时不确定性",
      sourceLabel,
      "低置信或质量受限区域",
      "不确定性掩膜",
      result.uncertain_mask_path || "",
    ),
  ];
});

async function loadVideoCandidates() {
  isLoadingVideoCandidates.value = true;
  setOperationMessage("正在读取本地公开视频候选...");
  try {
    const payload = await apiClient.listVideoCandidates(true);
    videoCandidates.value = payload.items;
    if (payload.items.length && !selectedVideoCandidateId.value) {
      await selectVideoCandidate(payload.items[0].record_id);
    }
    setOperationMessage(`已加载 ${payload.count} 条本地可读 MP4 候选。`);
  } catch (error) {
    setOperationMessage(errorMessage(error), "error");
  } finally {
    isLoadingVideoCandidates.value = false;
  }
}

async function selectVideoCandidate(recordId: string) {
  selectedVideoCandidateId.value = recordId;
  selectedVideoCandidatePreviewSrc.value = "";
  const candidate = videoCandidates.value.find((item) => item.record_id === recordId);
  if (candidate?.local_path) {
    videoPath.value = candidate.local_path;
    inputMode.value = "video";
  }
  if (!candidate?.system_readable) return;
  if (candidate.preview_path) {
    selectedVideoCandidatePreviewSrc.value = apiClient.filePreviewUrl(candidate.preview_path);
    return;
  }
  isLoadingVideoPreview.value = true;
  try {
    const previewCandidate = await apiClient.createVideoCandidatePreview(recordId);
    videoCandidates.value = videoCandidates.value.map((item) =>
      item.record_id === recordId ? { ...item, ...previewCandidate } : item,
    );
    if (previewCandidate.preview_path && selectedVideoCandidateId.value === recordId) {
      selectedVideoCandidatePreviewSrc.value = apiClient.filePreviewUrl(previewCandidate.preview_path);
    }
  } catch (error) {
    setOperationMessage(`公开视频预览生成失败：${errorMessage(error)}`, "error");
  } finally {
    isLoadingVideoPreview.value = false;
  }
}

async function importSelectedVideoCandidate() {
  if (!store.currentCase) {
    setOperationMessage("请先新建或加载病例。", "error");
    return;
  }
  if (!selectedVideoCandidateId.value) {
    setOperationMessage("请先选择公开视频候选。", "error");
    return;
  }
  setOperationMessage("正在导入公开视频候选...");
  try {
    store.currentCase = await apiClient.importVideoCandidate(store.currentCase.case_id, selectedVideoCandidateId.value);
    const candidate = videoCandidates.value.find((item) => item.record_id === selectedVideoCandidateId.value);
    if (candidate?.local_path) {
      videoPath.value = candidate.local_path;
    }
    inputMode.value = "video";
    setOperationMessage("公开视频候选已写入病例。");
  } catch (error) {
    setOperationMessage(errorMessage(error), "error");
  }
}

async function runAnalysis() {
  if (!store.currentCase) {
    setOperationMessage("请先新建或加载病例。", "error");
    return;
  }
  if (!imagePairReady.value) {
    const message =
      whiteLightPath.value && fluorescencePath.value
        ? "请选择同一 pair_id 下的白光 JPEG 与 ICG 荧光 JPEG。"
        : "请先导入白光 JPEG 与 ICG 荧光 JPEG，再进行图像融合分析。";
    setOperationMessage(message, "error");
    return;
  }
  setOperationMessage("正在运行 JPEG 图像融合分析...");
  await store.runAnalysis(
    {
      alpha: alpha.value,
      threshold: threshold.value,
      colormap: colormap.value,
    },
    roiHintsFromCurrentCase(),
    selectedImageInputIdList.value,
  );
  setOperationMessage(
    store.error || latestRunFailureMessage() || "分析完成，结果已同步到工作台。",
    store.error || latestRunFailureMessage() ? "error" : "info",
  );
}

async function analyzeBrowserCameraFrame(blob: Blob) {
  if (!(await ensureLiveSessionCase())) return;
  await analyzeCameraFrame(blob, {
    capturedAt: new Date().toISOString(),
    sequence: 1,
    sessionId: `browser-camera-manual-${Date.now()}`,
    trigger: "manual",
    source: "camera",
  });
}

async function captureAndAnalyzeBrowserCameraFrame() {
  if (cameraManualAnalysisBusy.value) {
    setOperationMessage("当前手工关键帧仍在分析，请等待完成。");
    return;
  }
  if (
    cameraContinuousAnalysisStarting.value ||
    cameraContinuousAnalysisActive.value ||
    cameraAnalysisRunning.value
  ) {
    setOperationMessage("请先停止连续实时分割，再抓取手工关键帧。", "error");
    return;
  }
  cameraManualAnalysisBusy.value = true;
  try {
    await analyzeBrowserCameraFrame(await captureCameraFrame());
  } catch (error) {
    setOperationMessage(errorMessage(error), "error");
  } finally {
    cameraManualAnalysisBusy.value = false;
  }
}

async function analyzeContinuousCameraFrame(blob: Blob, context: ContinuousCameraFrameContext) {
  if (!(await ensureLiveSessionCase())) {
    throw new Error("实时会话病例创建失败。");
  }
  await analyzeCameraFrame(blob, {
    ...context,
    source: "camera",
  });
}

async function captureVideoPlaybackFrame(): Promise<Blob> {
  if (!analysisWorkspaceCardRef.value) {
    throw new Error("MP4 播放视口尚未就绪。");
  }
  return analysisWorkspaceCardRef.value.capturePlaybackFrame();
}

async function analyzeContinuousVideoFrame(blob: Blob, context: ContinuousCameraFrameContext) {
  if (!store.currentCase) {
    throw new Error("请先导入 MP4 并建立病例。");
  }
  await analyzeCameraFrame(blob, {
    ...context,
    source: "video",
  });
}

async function analyzeCameraFrame(
  blob: Blob,
  context: {
    capturedAt: string;
    sequence: number;
    sessionId: string;
    trigger: "manual" | "continuous";
    source: "camera" | "video";
    signal?: AbortSignal;
    timestampSec?: number;
  },
) {
  if (!store.currentCase) {
    throw new Error("请先新建或加载病例。");
  }
  liveFrameRequestController?.abort();
  const requestController = new AbortController();
  const requestGeneration = ++liveFrameRequestGeneration;
  liveFrameRequestController = requestController;
  liveFrameRequestSource = context.source;
  const capturedAtMs = Date.parse(context.capturedAt);
  const identity: LiveFrameDisplayIdentity = {
    source: context.source,
    sequence: context.sequence,
    sessionId: context.sessionId,
    capturedAt: context.capturedAt,
    capturedAtMs: Number.isFinite(capturedAtMs) ? capturedAtMs : Date.now(),
    requestGeneration,
  };
  liveFrameExpectedIdentity.value = identity;
  markLiveFramePending(
    context.source,
    context.trigger === "continuous"
      ? "上一帧实时结果保留，正在处理下一帧。"
      : "正在处理当前帧，上一帧实时结果保留。",
  );
  const abortAndMarkPending = () => {
    requestController.abort();
    markLiveFramePending(context.source, "当前实时请求已取消，保留最近一次已验证结果。");
  };
  if (context.signal?.aborted) {
    abortAndMarkPending();
  } else {
    context.signal?.addEventListener("abort", abortAndMarkPending, { once: true });
  }
  if (requestController.signal.aborted) {
    context.signal?.removeEventListener("abort", abortAndMarkPending);
    if (liveFrameRequestController === requestController) {
      liveFrameRequestController = null;
      liveFrameRequestSource = "";
    }
    return;
  }
  const sourceLabel = context.source === "video" ? "MP4 实时分割" : "实时分割";
  setOperationMessage(
    context.trigger === "continuous" ? `正在刷新${sourceLabel} ${context.sequence}...` : `正在刷新${sourceLabel}...`,
  );
  try {
    const result = await apiClient.analyzeLiveFrame(
      store.currentCase.case_id,
      blob,
      {
        capturedAt: context.capturedAt,
        sequence: context.sequence,
        timestampSec: context.timestampSec,
        threshold: threshold.value,
        colormap: colormap.value,
        signal: requestController.signal,
      },
    );
    if (
      requestController.signal.aborted ||
      requestGeneration !== liveFrameRequestGeneration ||
      liveFrameExpectedIdentity.value?.sequence !== identity.sequence ||
      liveFrameExpectedIdentity.value?.sessionId !== identity.sessionId
    ) return;
    if (result.case_id !== store.currentCase.case_id || result.captured_at !== identity.capturedAt) {
      markLiveFrameStale(context.source, "实时结果与当前帧时间戳不一致，已回退原始视频。");
      throw new Error("实时分割结果与当前帧不匹配，已安全回退。");
    }
    if (identity.capturedAtMs > Date.now() || Date.now() - identity.capturedAtMs > LIVE_FRAME_MAX_AGE_MS) {
      markLiveFrameStale(context.source, "实时结果已超过允许显示时限，已回退原始视频。");
      throw new Error("实时分割结果已超过允许显示时限，已安全回退。");
    }
    liveFrameResult.value = result;
    liveFrameSource.value = context.source;
    liveFrameDisplayIdentity.value = identity;
    liveFrameStaleStatus.value = "";
    scheduleLiveFrameExpiry(identity);
    const candidateCount = countLabel(result.quantification?.component_count);
    setOperationMessage(
      `${sourceLabel}已更新，生成 ${candidateCount} 个候选区，结果需医生复核。`,
    );
  } catch (error) {
    if (requestController.signal.aborted || requestGeneration !== liveFrameRequestGeneration || isAbortError(error)) {
      markLiveFramePending(context.source, "当前实时请求已取消，保留最近一次已验证结果。");
      return;
    }
    markLiveFramePending(context.source, "实时分割失败，保留最近一次已验证结果。");
    if (context.trigger === "manual") setOperationMessage(errorMessage(error), "error");
    throw error;
  } finally {
    context.signal?.removeEventListener("abort", abortAndMarkPending);
    if (liveFrameRequestController === requestController) {
      liveFrameRequestController = null;
      liveFrameRequestSource = "";
    }
  }
}

async function startContinuousCameraAnalysis() {
  if (!cameraActive.value) {
    setOperationMessage("请先开启摄像头。", "error");
    return;
  }
  if (cameraManualAnalysisBusy.value) {
    setOperationMessage("当前手工关键帧仍在分析，完成后可启动连续实时分割。", "error");
    return;
  }
  if (cameraContinuousAnalysisStarting.value) return;
  if (cameraContinuousAnalysisActive.value) return;
  const sourceGeneration = ++liveAnalysisSourceGeneration;
  stopVideoPlaybackAnalysisLoop(false);
  invalidateLiveFrameRequest("video");
  clearLiveFrameResult("video");
  const started = await startContinuousCameraAnalysisLoop();
  if (sourceGeneration !== liveAnalysisSourceGeneration) return;
  if (!started) {
    setOperationMessage("实时分割启动失败，请检查摄像头连接。", "error");
  }
}

function stopContinuousCameraAnalysis(message = true) {
  liveAnalysisSourceGeneration += 1;
  stopContinuousCameraAnalysisLoop(message);
  invalidateLiveFrameRequest("camera");
  clearLiveFrameResult("camera");
}

async function startVideoPlaybackAnalysis() {
  if (!fileVideoActive.value) return;
  videoPlaybackPlaying.value = true;
  if (videoPlaybackAnalysisActive.value) return;
  const sourceGeneration = ++liveAnalysisSourceGeneration;
  stopContinuousCameraAnalysisLoop(false);
  invalidateLiveFrameRequest("camera");
  clearLiveFrameResult("camera");
  const started = await startVideoPlaybackAnalysisLoop();
  if (sourceGeneration !== liveAnalysisSourceGeneration) return;
  if (!started) {
    videoPlaybackPlaying.value = false;
    setOperationMessage("MP4 实时分割启动失败，请确认视频已开始播放。", "error");
  }
}

function pauseVideoPlaybackAnalysis() {
  liveAnalysisSourceGeneration += 1;
  videoPlaybackPlaying.value = false;
  stopVideoPlaybackAnalysisLoop(false);
  invalidateLiveFrameRequest("video");
  clearLiveFrameResult("video");
  setOperationMessage("MP4 播放已暂停，逐帧实时分割已暂停。");
}

function endVideoPlaybackAnalysis() {
  liveAnalysisSourceGeneration += 1;
  videoPlaybackPlaying.value = false;
  stopVideoPlaybackAnalysisLoop(false);
  invalidateLiveFrameRequest("video");
  clearLiveFrameResult("video");
  setOperationMessage("MP4 播放结束，逐帧实时分割已停止。");
}

function clearLiveFrameResult(source?: "camera" | "video") {
  const currentSource = currentLiveFrameStateSource();
  if (source && currentSource && currentSource !== source) return;
  clearLiveFrameExpiryTimer();
  liveFrameResult.value = null;
  liveFrameSource.value = "";
  liveFrameDisplayIdentity.value = null;
  liveFrameExpectedIdentity.value = null;
}

function invalidateLiveFrameRequest(source?: "camera" | "video") {
  if (source && liveFrameRequestSource && liveFrameRequestSource !== source) return;
  liveFrameRequestGeneration += 1;
  liveFrameRequestController?.abort();
  liveFrameRequestController = null;
  liveFrameRequestSource = "";
  markLiveFrameStale(source, "当前实时结果已过期，正在显示原始视频。");
}

function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === "AbortError";
}

function handleLiveFrameInvalidation(
  source: "camera" | "video",
  reason: ContinuousCameraFrameInvalidationReason,
  _context?: ContinuousCameraFrameContext,
) {
  const messages: Record<ContinuousCameraFrameInvalidationReason, string> = {
    new_frame: "上一帧实时结果保留，正在处理下一帧。",
    failed: "实时分割失败，保留最近一次已验证结果。",
    timed_out: "实时分割超时，保留最近一次已验证结果。",
    stopped: "实时分割已停止，显示原始视频。",
  };
  if (reason === "stopped") {
    markLiveFrameStale(source, messages[reason]);
    return;
  }
  markLiveFramePending(source, messages[reason]);
}

function markLiveFramePending(source: "camera" | "video" | undefined, message: string) {
  const currentSource = currentLiveFrameStateSource();
  if (source && currentSource && currentSource !== source) return;
  liveFrameStaleStatus.value = message;
}

function markLiveFrameStale(source: "camera" | "video" | undefined, message: string) {
  const currentSource = currentLiveFrameStateSource();
  if (source && currentSource && currentSource !== source) return;
  clearLiveFrameExpiryTimer();
  liveFrameResult.value = null;
  liveFrameSource.value = "";
  liveFrameDisplayIdentity.value = null;
  liveFrameStaleStatus.value = message;
}

function currentLiveFrameStateSource(): "camera" | "video" | "" {
  return (
    liveFrameDisplayIdentity.value?.source ||
    liveFrameSource.value ||
    liveFrameExpectedIdentity.value?.source ||
    ""
  );
}

function scheduleLiveFrameExpiry(identity: LiveFrameDisplayIdentity) {
  clearLiveFrameExpiryTimer();
  const remainingMs = Math.max(0, identity.capturedAtMs + LIVE_FRAME_MAX_AGE_MS - Date.now());
  liveFrameExpiryTimer = window.setTimeout(() => {
    liveFrameExpiryTimer = null;
    if (liveFrameDisplayIdentity.value?.requestGeneration !== identity.requestGeneration) return;
    markLiveFrameStale(identity.source, "实时结果已过期，已回退原始视频。");
  }, remainingMs);
}

function clearLiveFrameExpiryTimer() {
  if (liveFrameExpiryTimer === null) return;
  window.clearTimeout(liveFrameExpiryTimer);
  liveFrameExpiryTimer = null;
}

onBeforeUnmount(() => {
  liveAnalysisSourceGeneration += 1;
  invalidateLiveFrameRequest();
});

async function prepareContinuousCameraAnalysis() {
  if (!(await ensureLiveSessionCase())) {
    throw new Error("实时会话病例创建失败。");
  }
  await warmupLiveFrameModel();
}

async function prepareVideoPlaybackAnalysis() {
  if (!store.currentCase || !fileVideoActive.value) {
    throw new Error("请先导入 MP4 并开始播放。");
  }
  await warmupLiveFrameModel();
}

async function openCameraForLiveAnalysis() {
  const opened = await startCameraInput();
  if (opened) {
    void warmupLiveFrameModel().catch(() => undefined);
  }
}

async function warmupLiveFrameModel() {
  if (liveModelWarmupPromise.value) return liveModelWarmupPromise.value;
  const task = (async () => {
    setOperationMessage("摄像头已连接，正在预热实时分割模型...");
    const warmup = await apiClient.warmupLiveFrameModel();
    if (!warmup.available) {
      throw new Error("实时分割模型不可用。");
    }
  })();
  liveModelWarmupPromise.value = task;
  try {
    await task;
  } finally {
    liveModelWarmupPromise.value = null;
  }
}

function setCameraAnalysisInterval(value: number) {
  setCameraAnalysisIntervalLoop(value as ContinuousCameraAnalysisIntervalSec);
}

async function ensureLiveSessionCase(): Promise<boolean> {
  if (store.currentCase) return true;
  if (liveSessionCreatePromise.value) return liveSessionCreatePromise.value;
  const task = (async () => {
    setOperationMessage("正在创建实时视频会话...");
    await store.createCase(`实时视频会话 ${new Date().toLocaleString("zh-CN", { hour12: false })}`);
    if (store.error || !store.currentCase) {
      setOperationMessage(store.error || "实时视频会话创建失败。", "error");
      return false;
    }
    setOperationMessage(`实时视频会话已建立：${store.currentCase.case_id}`);
    return true;
  })();
  liveSessionCreatePromise.value = task;
  try {
    return await task;
  } finally {
    liveSessionCreatePromise.value = null;
  }
}

async function runVideoFileAnalysis() {
  if (!store.currentCase) {
    setOperationMessage("请先新建或加载病例。", "error");
    return;
  }
  const source = videoPath.value.trim();
  if (!source) {
    setOperationMessage("请先选择 MP4 视频。", "error");
    return;
  }
  const imported = await importVideoInput();
  if (!imported) return;

  const requestedTimestamps = parseVideoTimepoints(videoTimepoints.value);
  if (videoTimepoints.value.trim() && !requestedTimestamps.length) {
    setOperationMessage("关键时间点格式无效，请输入秒数并用逗号或空格分隔。", "error");
    return;
  }
  setOperationMessage("正在启动 MP4 关键帧后台分析任务...");
  await store.runAnalysisJob(
    videoFileAnalysisParameters(source, fluorescenceControls(), {
      keyframeCount: 5,
      timestampsSec: requestedTimestamps,
    }),
    roiHintsFromCurrentCase(),
  );
  if (store.lastAnalysisJobTimedOut) {
    setOperationMessage(
      `MP4 后台分析仍在运行，任务 ${store.activeAnalysisJobId || "-"} 当前状态为 ${store.activeAnalysisJobStatus || "running"}。`,
    );
    return;
  }
  const latest = store.currentCase?.analysis_runs.at(-1);
  const count = countLabel(latest?.quantitative_summary?.keyframes_extracted);
  const hotspotCount = countLabel(latest?.quantitative_summary?.hotspot_candidate_count);
  setOperationMessage(
    store.error || `MP4 分割分析完成，已抽取 ${count} 帧，生成 ${hotspotCount} 个候选区。`,
    store.error ? "error" : "info",
  );
}

async function reanalyzeSelectedHotspotFrame() {
  if (!store.currentCase) {
    setOperationMessage("请先新建或加载病例。", "error");
    return;
  }
  const source = videoPath.value.trim();
  if (!source) {
    setOperationMessage("请先选择 MP4 视频。", "error");
    return;
  }
  const detail = selectedHotspotFrameDetail.value;
  if (!detail) {
    setOperationMessage("请先在 MP4 分割时间轴中选择需要重算的帧。", "error");
    return;
  }
  const imported = await importVideoInput();
  if (!imported) return;

  const frameSelection = hotspotFrameSelection(detail);
  if (!frameSelection) {
    setOperationMessage("当前帧缺少可重算的时间戳或帧号。", "error");
    return;
  }

  setOperationMessage(`正在重算 ${detail.frameLabel}...`);
  await store.runAnalysisJob(
    videoFileAnalysisParameters(source, fluorescenceControls(), {
      keyframeCount: 1,
      ...frameSelection,
    }),
    roiHintsFromCurrentCase(),
  );
  if (store.lastAnalysisJobTimedOut) {
    setOperationMessage(
      `当前帧重算仍在后台运行，任务 ${store.activeAnalysisJobId || "-"} 当前状态为 ${store.activeAnalysisJobStatus || "running"}。`,
    );
    return;
  }
  const latest = store.currentCase?.analysis_runs.at(-1);
  const count = countLabel(latest?.quantitative_summary?.keyframes_extracted);
  const hotspotCount = countLabel(latest?.quantitative_summary?.hotspot_candidate_count);
  setOperationMessage(
    store.error || `当前帧重算完成，已抽取 ${count} 帧，生成 ${hotspotCount} 个热点候选区。`,
    store.error ? "error" : "info",
  );
}

async function generateBoneGateForSelectedFrame() {
  if (store.loading) return;
  if (!store.currentCase) {
    setOperationMessage("请先新建或加载病例。", "error");
    return;
  }
  const detail = selectedHotspotFrameDetail.value;
  if (!detail) {
    setOperationMessage("请先选择需要生成骨面门控的关键帧。", "error");
    return;
  }
  const candidate = candidateForHotspotFrame(latestCandidates.value, detail);
  if (!candidate) {
    setOperationMessage("当前关键帧缺少可用于 prompt 的候选框。", "error");
    return;
  }
  const geometry = isRecord(candidate.metadata?.bbox_normalized) ? candidate.metadata.bbox_normalized : undefined;
  setOperationMessage(`正在为 ${detail.frameLabel} 生成骨面门控...`);
  await store.generateCandidateBoneGateMask(candidate.candidate_id, geometry);
  setOperationMessage(
    store.error || "骨面门控已生成，可在同步分析和医生复核中继续接受、修改或拒绝。",
    store.error ? "error" : "info",
  );
}

async function saveBoneGateMaskEditForSelectedFrame(payload: {
  maskPngBase64: string;
  reviewState: "review_required" | "accepted" | "modified" | "rejected";
  reviewerNotes: string;
}) {
  if (store.loading) return;
  if (!store.currentCase) {
    setOperationMessage("请先新建或加载病例。", "error");
    return;
  }
  const detail = selectedHotspotFrameDetail.value;
  if (!detail) {
    setOperationMessage("请先选择需要修改骨面掩膜的关键帧。", "error");
    return;
  }
  const candidate = candidateForHotspotFrame(latestCandidates.value, detail);
  if (!candidate) {
    setOperationMessage("当前关键帧缺少可回写的候选区。", "error");
    return;
  }
  setOperationMessage(`正在保存 ${detail.frameLabel} 的骨面掩膜修改...`);
  await store.saveCandidateBoneGateMaskEdit(
    candidate.candidate_id,
    payload.maskPngBase64,
    payload.reviewState,
    payload.reviewerNotes,
  );
  setOperationMessage(
    store.error || "骨面掩膜修改已保存，并进入复核回灌记录。",
    store.error ? "error" : "info",
  );
}

async function refreshAnalysisJob() {
  if (isCancelingAnalysisJob.value) return;
  if (!store.activeAnalysisJobId) {
    setOperationMessage("暂无可继续查询的后台分析任务。", "error");
    return;
  }
  setOperationMessage("正在继续查询后台分析任务...");
  await store.refreshActiveAnalysisJob();
  if (store.lastAnalysisJobTimedOut) {
    setOperationMessage(`后台分析任务 ${store.activeAnalysisJobId} 仍在 ${store.activeAnalysisJobStatus || "running"}。`);
    return;
  }
  setOperationMessage(store.error || `后台分析任务 ${store.activeAnalysisJobId} 状态：${store.activeAnalysisJobStatus || "unknown"}。`, store.error ? "error" : "info");
}

async function cancelAnalysisJob() {
  if (isCancelingAnalysisJob.value) return;
  if (!store.activeAnalysisJobId) {
    setOperationMessage("暂无可取消的后台分析任务。", "error");
    return;
  }
  isCancelingAnalysisJob.value = true;
  setOperationMessage("正在取消后台分析任务...");
  try {
    await store.cancelActiveAnalysisJob();
    setOperationMessage(
      store.error || `后台分析任务 ${store.activeAnalysisJobId} 已更新为 ${store.activeAnalysisJobStatus || "unknown"}。`,
      store.error ? "error" : "info",
    );
  } finally {
    isCancelingAnalysisJob.value = false;
  }
}

async function retryAnalysisJob() {
  if (isCancelingAnalysisJob.value) return;
  if (!store.activeAnalysisJobId) {
    setOperationMessage("暂无可重试的后台分析任务。", "error");
    return;
  }
  setOperationMessage("正在重试后台分析任务...");
  await store.retryActiveAnalysisJob();
  if (store.lastAnalysisJobTimedOut) {
    setOperationMessage(`重试任务 ${store.activeAnalysisJobId} 仍在 ${store.activeAnalysisJobStatus || "running"}。`);
    return;
  }
  setOperationMessage(store.error || `重试任务 ${store.activeAnalysisJobId} 状态：${store.activeAnalysisJobStatus || "unknown"}。`, store.error ? "error" : "info");
}

async function exportCase() {
  if (!store.currentCase) {
    setOperationMessage("请先新建或加载病例。", "error");
    return;
  }
  setOperationMessage("正在导出证据包...");
  await store.exportCase();
  setOperationMessage(store.error || `证据包已导出：${store.exportPath}`, store.error ? "error" : "info");
}

async function saveClinicalContext(context: ClinicalContext) {
  clinicalContextSaveStatus.value = "saving";
  clinicalContextSaveError.value = "";
  setOperationMessage("正在保存患者结构化上下文...");
  await store.saveClinicalContext(context);
  clinicalContextSaveStatus.value = store.error ? "error" : "success";
  clinicalContextSaveError.value = store.error;
  setOperationMessage(store.error || "患者结构化上下文已保存，当前仅用于风险先验与校准。", store.error ? "error" : "info");
}

async function handleFilePicked(channel: "white_light" | "fluorescence" | "device_overlay" | "video", event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;
  if (channel === "video") {
    await uploadSelectedVideo(file);
    return;
  }
  await uploadSelectedImage(channel, file);
}

async function uploadSelectedImage(channel: "white_light" | "fluorescence" | "device_overlay", file: File) {
  const isOverlay = channel === "device_overlay";
  const isWhite = channel === "white_light";
  if (isOverlay) {
    isUploadingDeviceOverlay.value = true;
  } else if (isWhite) {
    isUploadingWhite.value = true;
  } else {
    isUploadingFluorescence.value = true;
  }
  const channelLabel = isOverlay ? "设备叠加" : isWhite ? "白光" : "ICG 荧光";
  setOperationMessage(`正在上传${channelLabel}图像：${file.name}`);
  try {
    const uploaded = await apiClient.uploadRawImage(file);
    selectedImagePairKey.value = "";
    const attached = await attachUploadedInput({
      channel,
      path: uploaded.path,
      mime_type: "image/jpeg",
      metadata: {
        acquisition_mode: isOverlay ? "device_display_reference" : "official_jpeg_upload",
        official_format: "JPEG",
        original_filename: uploaded.original_filename,
        ...(isOverlay ? { derived_by_device: true, analysis_input_allowed: false, evidence_role: "device_display_reference" } : {}),
      },
    });
    if (!attached) return;
    if (isOverlay) {
      deviceOverlayPath.value = uploaded.path;
    } else if (isWhite) {
      whiteLightPath.value = uploaded.path;
    } else {
      fluorescencePath.value = uploaded.path;
    }
    setOperationMessage(
      `${channelLabel} JPEG 已导入病例：${uploaded.path}；${officialProfileLabel(uploaded.metadata)}`,
    );
  } catch (error) {
    setOperationMessage(errorMessage(error), "error");
  } finally {
    if (isOverlay) {
      isUploadingDeviceOverlay.value = false;
    } else if (isWhite) {
      isUploadingWhite.value = false;
    } else {
      isUploadingFluorescence.value = false;
    }
  }
}

async function uploadSelectedVideo(file: File) {
  isUploadingVideo.value = true;
  setOperationMessage(`正在上传官方 MP4 视频：${file.name}`);
  try {
    const uploaded = await apiClient.uploadRawFile(file);
    videoPath.value = uploaded.path;
    const attached = await attachUploadedInput({
      channel: "video",
      path: uploaded.path,
      mime_type: "video/mp4",
      metadata: {
        acquisition_mode: "official_mp4_upload",
        official_format: "MP4",
        original_filename: uploaded.original_filename,
      },
    });
    if (!attached) return;
    if (uploaded.keyframe_job_id) {
      setOperationMessage(
        `MP4 视频已导入病例：${uploaded.path}；${officialProfileLabel(uploaded.metadata)}；预抽取关键帧正在后台运行，播放后可立即启动逐帧实时分割。`,
      );
    } else {
      const keyframeCount = uploaded.keyframes?.length ?? 0;
      setOperationMessage(`MP4 视频已导入病例：${uploaded.path}；${officialProfileLabel(uploaded.metadata)}；预抽取关键帧 ${keyframeCount} 张。`);
    }
  } catch (error) {
    setOperationMessage(errorMessage(error), "error");
  } finally {
    isUploadingVideo.value = false;
  }
}

async function attachUploadedInput(input: {
  channel: "white_light" | "fluorescence" | "device_overlay" | "video";
  path: string;
  mime_type: string;
  metadata: Record<string, unknown>;
}): Promise<boolean> {
  if (!store.currentCase) {
    setOperationMessage("请先新建或加载病例。", "error");
    return false;
  }
  await store.importInputs([input]);
  if (store.error) {
    setOperationMessage(store.error, "error");
    return false;
  }
  return true;
}

function emptyClinicalContext(): ClinicalContext {
  return {
    age_years: null,
    age_group: "unknown",
    sex_at_birth: "not_recorded",
    comorbidities: [],
    comorbidities_reviewed: false,
    medications: [],
    medications_reviewed: false,
    labs: [],
    source_organization: null,
    recorded_by: null,
    recorded_at: null,
    review_status: "unreviewed",
    deidentified: true,
    clinical_use_boundary: "risk_prior_and_calibration_only_no_spatial_boundary_effect",
  };
}

function fluorescenceControls() {
  // 白光/荧光融合参数在图片分析、MP4 分析和单帧重算中共用，统一从这里组装。
  return {
    alpha: alpha.value,
    threshold: threshold.value,
    colormap: colormap.value,
  };
}

function latestRunFailureMessage(): string {
  const latest = store.currentCase?.analysis_runs.at(-1);
  if (latest?.status !== "failed") return "";
  const warning = latest.warnings.find((item) => Boolean(item.blocking)) ?? latest.warnings[0];
  return warning ? normalizeWarning(warning, 0).message : "分析未通过，请检查输入和参数。";
}

function roiHintsFromCurrentCase(): Array<Record<string, unknown>> {
  return (store.currentCase?.rois ?? [])
    .filter((roi: RegionOfInterest) => roi.geometry?.type === "rect")
    .map((roi: RegionOfInterest) => ({
      roi_id: roi.roi_id,
      source: roi.source,
      geometry: roi.geometry,
      label: roi.label,
      review_state: roi.review_state,
      candidate_id: roi.candidate_id,
    }));
}

</script>

<style scoped>
.case-workspace {
  min-height: 100dvh;
  overflow-x: hidden;
  padding: var(--ov-page-top) var(--ov-page-inline) var(--ov-page-bottom);
  background: var(--ov-bg);
  color: var(--ov-text);
}

.workspace-header,
.review-notice,
.workspace-grid {
  width: min(100%, var(--ov-content-wide));
  margin-right: auto;
  margin-left: auto;
}

.workspace-header {
  display: flex;
  gap: var(--ov-space-5);
  align-items: end;
  justify-content: space-between;
  padding: 0 4px var(--ov-space-5);
}

.workspace-title {
  min-width: 0;
}

.workspace-title h1 {
  margin: 0;
  color: var(--ov-text);
  font-size: var(--ov-font-workspace-title);
  line-height: 1.2;
  letter-spacing: 0;
  overflow-wrap: anywhere;
}

.workspace-title p {
  margin: 0 0 4px;
  color: var(--ov-primary-strong);
  font-size: 11px;
  font-weight: 700;
}

.workspace-context {
  display: flex;
  gap: var(--ov-space-3);
  align-items: center;
  justify-content: flex-end;
  color: var(--ov-text-muted);
  font-size: 12px;
  font-weight: 600;
}

.workspace-context span,
.workspace-context strong {
  border: 1px solid var(--ov-border);
  border-radius: 6px;
  padding: 6px 10px;
  background: var(--ov-bg-elevated);
}

.workspace-context strong {
  color: var(--ov-text-secondary);
}

.workspace-context strong.running {
  color: var(--ov-warning);
}

.workspace-context strong.completed {
  color: var(--ov-success);
}

.workspace-context strong.failed {
  color: var(--ov-danger);
}

.workspace-header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--ov-space-3);
  align-items: center;
  justify-content: flex-end;
}

.navigation-workspace-link {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  min-height: 38px;
  border: 1px solid var(--ov-border-accent);
  border-radius: 6px;
  padding: 6px 10px;
  background: var(--ov-bg-elevated);
  color: var(--ov-text);
  text-decoration: none;
  transition:
    transform 140ms ease,
    border-color 140ms ease,
    background 140ms ease;
}

.navigation-workspace-link:hover {
  transform: translateY(-1px);
  border-color: var(--ov-primary-strong);
  background: var(--ov-bg-hover);
}

.navigation-workspace-link:focus-visible {
  outline: 2px solid var(--ov-focus-ring);
  outline-offset: 2px;
}

.navigation-workspace-link :deep(.app-icon) {
  width: 18px;
  height: 18px;
  color: var(--ov-primary-strong);
}

.navigation-workspace-link > span {
  display: grid;
  gap: 1px;
}

.navigation-workspace-link strong,
.navigation-workspace-link small {
  line-height: 1.2;
}

.navigation-workspace-link strong {
  font-size: 12px;
}

.navigation-workspace-link small {
  color: var(--ov-text-muted);
  font-size: 10px;
  font-weight: 700;
}

.review-notice {
  margin-bottom: var(--ov-space-5);
  border: 1px solid var(--ov-border);
  border-left: 3px solid var(--ov-warning);
  border-radius: 6px;
  background: var(--ov-bg-warning);
}

.review-notice summary {
  display: grid;
  grid-template-columns: 24px auto minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  min-height: 42px;
  padding: 8px 14px 8px 12px;
  cursor: pointer;
  list-style: none;
}

.review-notice summary::-webkit-details-marker {
  display: none;
}

.review-notice summary::after {
  justify-self: end;
  color: var(--ov-warning);
  font-size: 12px;
  font-weight: 900;
  content: "详情";
}

.review-notice[open] summary {
  border-bottom: 1px solid var(--ov-border);
}

.review-notice[open] summary::after {
  content: "收起";
}

.notice-icon {
  width: 22px;
  height: 22px;
}

.review-notice strong {
  color: var(--ov-warning);
  font-size: 13px;
  overflow-wrap: anywhere;
}

.review-notice span {
  min-width: 0;
  color: var(--ov-text-secondary);
  font-size: 12px;
  font-weight: 600;
  overflow-wrap: anywhere;
}

.review-notice p {
  margin: 0;
  padding: 10px 14px 12px 46px;
  color: var(--ov-text-secondary);
  font-size: 13px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.workspace-grid {
  display: grid;
  grid-template-columns: minmax(304px, 326px) minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}

.workspace-sidebar {
  display: grid;
  gap: 16px;
  min-width: 0;
}

.sidebar-summary-details {
  min-width: 0;
  border: 1px solid var(--ov-border);
  border-radius: 7px;
  background: var(--ov-bg-elevated);
  box-shadow: var(--ov-shadow);
}

.sidebar-summary-details > summary {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
  min-height: 44px;
  padding: 10px 12px;
  color: var(--ov-text);
  cursor: pointer;
  list-style: none;
}

.sidebar-summary-details > summary::-webkit-details-marker {
  display: none;
}

.sidebar-summary-details > summary::after {
  color: var(--ov-primary-strong);
  font-size: 16px;
  font-weight: 800;
  content: "+";
}

.sidebar-summary-details[open] > summary {
  border-bottom: 1px solid var(--ov-border-subtle);
}

.sidebar-summary-details[open] > summary::after {
  content: "-";
}

.sidebar-summary-details > summary span {
  font-size: 14px;
  font-weight: 700;
}

.sidebar-summary-details > summary strong {
  margin-left: auto;
  color: var(--ov-text-muted);
  font-size: 11px;
}

.sidebar-summary-details :deep(.summary-card) {
  border: 0;
  border-radius: 0;
  box-shadow: none;
}

.analysis-column {
  display: grid;
  gap: 16px;
  min-width: 0;
}

.result-card,
.debug-panel {
  min-width: 0;
  border: 1px solid var(--ov-border);
  border-radius: 6px;
  background: var(--ov-bg-elevated);
  box-shadow: var(--ov-shadow);
}

.result-card {
  padding: 18px;
}

.result-card :deep(.ov-section-heading) {
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--ov-border-subtle);
}

.result-card :deep(.ov-section-heading__title) {
  color: var(--ov-text);
  font-size: 15px;
}

.result-card :deep(.ov-section-heading__eyebrow) {
  display: none;
}

.empty-inline {
  margin: 0;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 5px;
  padding: 10px 12px;
  background: var(--ov-bg-soft);
  color: var(--ov-text-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.debug-panel {
  opacity: 0.72;
  padding: 0;
  background: var(--ov-bg-elevated);
}

.debug-panel summary {
  cursor: pointer;
  padding: 8px 12px;
  color: var(--ov-text-secondary);
  font-size: 12px;
  font-weight: 900;
}

.debug-panel pre {
  max-height: 260px;
  margin: 0;
  overflow: auto;
  border-top: 1px solid var(--ov-border-subtle);
  padding: 12px 16px;
  color: var(--ov-text);
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
}

.case-workspace :deep(.control-card),
.case-workspace :deep(.analysis-card),
.case-workspace :deep(.summary-card),
.case-workspace :deep(.analysis-quad-card),
.case-workspace :deep(.fusion-evidence-panel),
.case-workspace :deep(.hotspot-timeline),
.case-workspace :deep(.export-panel),
.case-workspace :deep(.job-panel),
.case-workspace :deep(.hotspot-frame-detail),
.case-workspace :deep(.hotspot-frame-drawer),
.case-workspace :deep(.timeline-manifest-panel) {
  border-color: var(--ov-border);
  background: var(--ov-bg-elevated);
  color: var(--ov-text);
  box-shadow: var(--ov-shadow);
}

.case-workspace :deep(.control-card .ov-section-heading),
.case-workspace :deep(.compact-card-header),
.case-workspace :deep(.analysis-header),
.case-workspace :deep(.fusion-evidence-panel header),
.case-workspace :deep(.hotspot-timeline header),
.case-workspace :deep(.timeline-manifest-panel header) {
  border-color: var(--ov-border-subtle);
}

.case-workspace :deep(h2),
.case-workspace :deep(.analysis-header h2),
.case-workspace :deep(.fullscreen-header h2),
.case-workspace :deep(.ov-section-heading__title),
.case-workspace :deep(.compact-card-header strong),
.case-workspace :deep(.summary-chip strong),
.case-workspace :deep(.metric-grid dd),
.case-workspace :deep(.candidate-topline strong),
.case-workspace :deep(.analysis-quad-card header),
.case-workspace :deep(.fusion-evidence-panel header div),
.case-workspace :deep(.fusion-evidence-grid dd),
.case-workspace :deep(.timeline-summary-grid dd),
.case-workspace :deep(.hotspot-timeline-copy strong),
.case-workspace :deep(.hotspot-timeline-copy dd),
.case-workspace :deep(.hotspot-frame-detail dd),
.case-workspace :deep(.hotspot-frame-row strong) {
  color: var(--ov-text);
}

.case-workspace :deep(.field span),
.case-workspace :deep(.control-group-label),
.case-workspace :deep(.summary-chip),
.case-workspace :deep(.compact-card-header > span),
.case-workspace :deep(.summary-subtitle),
.case-workspace :deep(.metric-grid dt),
.case-workspace :deep(.candidate-meta p),
.case-workspace :deep(.analysis-quad-card p),
.case-workspace :deep(.state-message),
.case-workspace :deep(.export-path),
.case-workspace :deep(.fusion-evidence-grid dt),
.case-workspace :deep(.timeline-summary-grid dt),
.case-workspace :deep(.hotspot-timeline header span),
.case-workspace :deep(.hotspot-timeline-copy span),
.case-workspace :deep(.hotspot-timeline-copy dt),
.case-workspace :deep(.hotspot-frame-actions span),
.case-workspace :deep(.hotspot-frame-detail dt),
.case-workspace :deep(.hotspot-frame-detail p),
.case-workspace :deep(.hotspot-frame-row small) {
  color: var(--ov-text-secondary);
}

.case-workspace :deep(input),
.case-workspace :deep(textarea),
.case-workspace :deep(select),
.case-workspace :deep(output) {
  border-color: var(--ov-border-strong);
  background: var(--ov-bg-control);
  color: var(--ov-text);
}

.case-workspace :deep(input::placeholder),
.case-workspace :deep(textarea::placeholder) {
  color: var(--ov-text-muted);
}

.case-workspace :deep(input:focus),
.case-workspace :deep(textarea:focus),
.case-workspace :deep(select:focus) {
  border-color: var(--ov-border-accent);
  outline: 2px solid var(--ov-focus-ring);
}

.case-workspace :deep(.video-candidate-card),
.case-workspace :deep(.metric-grid div),
.case-workspace :deep(.candidate-list li),
.case-workspace :deep(.summary-chip),
.case-workspace :deep(.empty-inline),
.case-workspace :deep(.export-link),
.case-workspace :deep(.export-summary-grid div),
.case-workspace :deep(.export-artifact-list li),
.case-workspace :deep(.fusion-colorbar),
.case-workspace :deep(.fusion-evidence-grid div),
.case-workspace :deep(.timeline-summary-grid div),
.case-workspace :deep(.timeline-trace-list li),
.case-workspace :deep(.hotspot-timeline-item),
.case-workspace :deep(.hotspot-frame-row) {
  border-color: var(--ov-border-subtle);
  background: var(--ov-bg-soft);
}

.case-workspace :deep(.analysis-quad-viewport) {
  border-color: var(--ov-border-strong);
}

.case-workspace :deep(.empty-preview-copy) {
  border-color: var(--ov-border);
  background: var(--ov-bg-elevated);
  color: var(--ov-text-secondary);
  box-shadow: var(--ov-shadow);
}

.case-workspace :deep(.empty-preview-copy strong) {
  color: var(--ov-text);
}

.case-workspace :deep(.empty-preview-copy span) {
  color: var(--ov-text-secondary);
}

.case-workspace :deep(.app-button) {
  border-color: var(--ov-border-strong);
  background: var(--ov-bg-control);
  color: var(--ov-primary);
  box-shadow: none;
}

.case-workspace :deep(.app-button--primary) {
  border-color: var(--ov-border-accent);
  background: var(--ov-button-primary-bg);
  color: var(--ov-text-on-primary);
}

.case-workspace :deep(.app-button--ghost) {
  background: var(--ov-bg-hover);
  color: var(--ov-primary-strong);
}

.case-workspace :deep(.app-button:disabled) {
  opacity: 0.48;
}

.case-workspace :deep(.run-pill),
.case-workspace :deep(.candidate-topline span),
.case-workspace :deep(.frame-row-status),
.case-workspace :deep(.hotspot-filter-group button),
.case-workspace :deep(.timeline-manifest-panel header a),
.case-workspace :deep(.hotspot-frame-links a) {
  border: 1px solid var(--ov-border);
  background: var(--ov-bg-soft);
  color: var(--ov-primary-strong);
}

.case-workspace :deep(.analysis-header),
.case-workspace :deep(.fullscreen-header) {
  min-width: 0;
}

.case-workspace :deep(.analysis-title-block),
.case-workspace :deep(.analysis-summary-strip) {
  min-width: 0;
}

.case-workspace :deep(.analysis-header-actions) {
  flex-wrap: wrap;
  justify-content: flex-end;
  min-width: 0;
}

.case-workspace :deep(.summary-chip) {
  max-width: 100%;
}

.case-workspace :deep(.summary-chip span),
.case-workspace :deep(.summary-chip strong) {
  min-width: 0;
  overflow-wrap: anywhere;
  white-space: normal;
}

.case-workspace :deep(.run-pill.running),
.case-workspace :deep(.job-panel.timeout) {
  border-color: var(--ov-warning);
  background: var(--ov-bg-warning);
  color: var(--ov-warning);
}

.case-workspace :deep(.run-pill.failed),
.case-workspace :deep(.state-message.error),
.case-workspace :deep(.operation-message.error) {
  border-color: var(--ov-danger-border);
  background: var(--ov-bg-danger);
  color: var(--ov-danger);
}

.case-workspace :deep(.operation-message),
.case-workspace :deep(.state-message.muted),
.case-workspace :deep(.hotspot-empty-state),
.case-workspace :deep(.empty-inline) {
  border-color: var(--ov-border-subtle);
  background: var(--ov-bg-soft);
  color: var(--ov-text-secondary);
}

.case-workspace :deep(.summary-divider),
.case-workspace :deep(.hotspot-frame-table) {
  border-color: var(--ov-border-subtle);
  background: transparent;
}

/* Desktop clinical workstation polish: matte surfaces, fewer nested frames, clearer hierarchy. */
.result-card,
.debug-panel,
.case-workspace :deep(.control-card),
.case-workspace :deep(.analysis-card),
.case-workspace :deep(.summary-card),
.case-workspace :deep(.analysis-quad-card),
.case-workspace :deep(.fusion-evidence-panel),
.case-workspace :deep(.hotspot-timeline),
.case-workspace :deep(.export-panel),
.case-workspace :deep(.job-panel),
.case-workspace :deep(.hotspot-frame-detail),
.case-workspace :deep(.hotspot-frame-drawer),
.case-workspace :deep(.timeline-manifest-panel) {
  border-color: var(--ov-border);
  background: var(--ov-bg-elevated);
  box-shadow: var(--ov-shadow);
}

.case-workspace :deep(.analysis-card) {
  padding: 20px;
}

.case-workspace :deep(.analysis-quad-card) {
  border-color: var(--ov-border-subtle);
  background: var(--ov-bg-panel);
  box-shadow: none;
}

.case-workspace :deep(.analysis-quad-viewport) {
  border-color: var(--ov-border-strong);
}

.case-workspace :deep(.empty-preview-copy) {
  border: 0;
  padding: 8px 12px;
  background: transparent;
  box-shadow: none;
}

.case-workspace :deep(.empty-preview-copy strong) {
  color: var(--ov-text);
}

.case-workspace :deep(.empty-preview-copy span) {
  color: var(--ov-text-muted);
}

.case-workspace :deep(input),
.case-workspace :deep(textarea),
.case-workspace :deep(select),
.case-workspace :deep(output) {
  border-color: var(--ov-border-strong);
  background: var(--ov-bg-control);
  color: var(--ov-text);
}

.case-workspace :deep(.app-button) {
  border-color: var(--ov-border-strong);
  background: var(--ov-bg-control);
  color: var(--ov-primary);
  box-shadow: none;
}

.case-workspace :deep(.app-button--primary) {
  border-color: var(--ov-border-accent);
  background: var(--ov-button-primary-bg);
  color: var(--ov-text-on-primary);
}

.case-workspace :deep(.summary-chip),
.case-workspace :deep(.run-pill),
.case-workspace :deep(.candidate-topline span),
.case-workspace :deep(.frame-row-status) {
  border-radius: 6px;
}

.case-workspace :deep(.summary-chip) {
  background: var(--ov-bg-soft);
  font-weight: 600;
}

.case-workspace :deep(.analysis-header h2) {
  font-size: 18px;
}

.case-workspace :deep(.analysis-quad-card header) {
  font-size: 12px;
  font-weight: 700;
}

.case-workspace :deep(.control-card .ov-section-heading__title),
.case-workspace :deep(.result-card .ov-section-heading__title) {
  font-size: 14px;
  font-weight: 700;
}

.case-workspace :deep(.video-example-details) {
  border-color: var(--ov-border-subtle);
}

.case-workspace :deep(.video-example-details summary) {
  color: var(--ov-primary-strong);
}

@media (max-width: 1359px) {
  .workspace-grid {
    grid-template-columns: minmax(286px, 304px) minmax(0, 1fr);
  }
}

@media (max-width: 1180px) {
  .workspace-grid {
    grid-template-columns: 1fr;
  }

  .workspace-sidebar {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-items: start;
  }

  .workspace-sidebar :deep(.left-sidebar),
  .workspace-sidebar :deep(.summary-card) {
    min-width: 0;
  }
}

@media (max-width: 959px) {
  .case-workspace {
    padding: 14px;
  }

  .workspace-grid {
    grid-template-columns: 1fr;
  }

  .workspace-sidebar {
    grid-template-columns: 1fr;
  }

  .workspace-title h1 {
    font-size: 24px;
    line-height: 1.22;
  }

  .review-notice {
    margin-bottom: 10px;
  }

  .review-notice summary {
    grid-template-columns: 22px auto minmax(0, 1fr) auto;
    padding: 7px 10px;
  }

  .review-notice span {
    white-space: normal;
  }

  .review-notice p {
    grid-column: 1 / -1;
    padding: 9px 10px 11px;
  }
}

</style>
