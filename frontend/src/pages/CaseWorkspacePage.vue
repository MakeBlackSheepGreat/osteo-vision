<template>
  <main class="case-workspace">
    <header class="workspace-header">
      <div class="workspace-title">
        <h1>颌骨骨髓炎术中辅助决策平台</h1>
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
          v-model:white-light-path="whiteLightPath"
          v-model:fluorescence-path="fluorescencePath"
          v-model:video-path="videoPath"
          v-model:video-timepoints="videoTimepoints"
          v-model:alpha="alpha"
          v-model:threshold="threshold"
          v-model:colormap="colormap"
          :loading="store.loading"
          :has-case="Boolean(store.currentCase)"
          :is-uploading-white="isUploadingWhite"
          :is-uploading-fluorescence="isUploadingFluorescence"
          :is-uploading-video="isUploadingVideo"
          :is-loading-video-candidates="isLoadingVideoCandidates"
          :is-loading-video-preview="isLoadingVideoPreview"
          :selected-video-candidate-id="selectedVideoCandidateId"
          :selected-video-candidate-preview-src="selectedVideoCandidatePreviewSrc"
          :video-candidates="videoCandidates"
          :camera-active="cameraActive"
          :camera-status-label="cameraStatusLabel"
          :is-opening-camera="isOpeningCamera"
          :operation-message="operationMessage"
          :operation-message-type="operationMessageType"
          :realtime-video-active="realtimeVideoActive"
          @file-picked="handleFilePicked"
          @import-inputs="importInputs"
          @import-video="importVideoInput"
          @load-video-candidates="loadVideoCandidates"
          @select-video-candidate="selectVideoCandidate"
          @import-video-candidate="importSelectedVideoCandidate"
          @start-camera="startCameraInput"
          @stop-camera="stopCameraInput"
          @import-camera="importCameraInput"
          @run-analysis="runAnalysis"
          @run-video-file-analysis="runVideoFileAnalysis"
          @run-realtime-video="runRealtimeVideoAnalysis"
        />

        <AnalysisResultPanels :candidates="displayCandidates" :metrics="displayMetricMap" />
      </aside>

      <section class="analysis-column" aria-label="分析结果">
        <AnalysisWorkspaceCard
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
          :latest-run-status-label="latestRunStatusLabel"
          :analysis-status-class="analysisStatusClass"
          :kpi-items="kpiItems"
          :preview-panels="previewPanels"
          :hotspot-timeline-items="hotspotTimelineItems"
          :hotspot-timeline-total-count="allHotspotTimelineItems.length"
          :hotspot-timeline-filter="hotspotTimelineFilter"
          :selected-hotspot-timeline-key="selectedHotspotTimelineKey"
          :selected-hotspot-frame-detail="selectedHotspotFrameDetail"
          :hotspot-frame-details="hotspotFrameDetails"
          :timeline-manifest-summary="timelineManifestSummary"
          :fusion-evidence-summary="fusionEvidenceSummary"
          :camera-stream="cameraStream"
          :camera-active="cameraActive"
          :camera-status-label="cameraStatusLabel"
          :analysis-expanded="analysisExpanded"
          @export="exportCase"
          @refresh-job="refreshAnalysisJob"
          @cancel-job="cancelAnalysisJob"
          @retry-job="retryAnalysisJob"
          @reanalyze-hotspot-frame="reanalyzeSelectedHotspotFrame"
          @select-hotspot-frame="selectHotspotFrame"
          @update-hotspot-timeline-filter="updateHotspotTimelineFilter"
          @open-fullscreen="openAnalysisFullscreen"
          @close-fullscreen="closeAnalysisFullscreen"
        />

        <Anatomy3DPanel
          :candidates="displayCandidates"
          :metrics="displayMetricMap"
          :mode-label="latestMode === 'video_file_keyframes' ? 'MP4热点空间证据' : '双通道融合证据'"
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
import { computed, ref, watch } from "vue";

import AnalysisResultPanels from "@/components/AnalysisResultPanels.vue";
import AnalysisWorkspaceCard from "@/components/AnalysisWorkspaceCard.vue";
import Anatomy3DPanel from "@/components/Anatomy3DPanel.vue";
import CaseWorkspaceControls from "@/components/CaseWorkspaceControls.vue";
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
  videoPreviewPanelsFromRun,
} from "@/components/analysisPreview";
import type { AppIconName } from "@/components/appIcons";
import { useBrowserCamera } from "@/composables/useBrowserCamera";
import { useFullscreenPanel } from "@/composables/useFullscreenPanel";
import { useOperationMessage } from "@/composables/useOperationMessage";
import { apiClient } from "@/services/apiClient";
import { useCaseStore } from "@/stores/caseStore";
import type { CandidateRegion, CaseInputAsset, RegionOfInterest, VideoCandidate } from "@/types/case";
import {
  colormapLabel,
  errorMessage,
  isRecord,
  normalizeWarning,
  runStatusLabel,
  stringFrom,
} from "@/utils/caseDisplay";

const store = useCaseStore();

// 页面层保留业务流程编排：上传、写入病例、触发分析和导出。
const whiteLightPath = ref("");
const fluorescencePath = ref("");
const videoPath = ref("");
const videoTimepoints = ref("");
const syncedCaseId = ref("");
const alpha = ref(0.45);
const threshold = ref(0.6);
const colormap = ref<"green" | "amber" | "magenta">("green");
const isUploadingWhite = ref(false);
const isUploadingFluorescence = ref(false);
const isUploadingVideo = ref(false);
const isLoadingVideoCandidates = ref(false);
const isLoadingVideoPreview = ref(false);
const videoCandidates = ref<VideoCandidate[]>([]);
const selectedVideoCandidateId = ref("");
const selectedVideoCandidatePreviewSrc = ref("");
const selectedHotspotTimelineKey = ref("");
const hotspotTimelineFilter = ref<HotspotTimelineFilter>("all");
const realtimeVideoActive = ref(false);
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
const {
  cameraStream,
  cameraActive,
  cameraStatusLabel,
  isOpeningCamera,
  startCameraInput,
  stopCameraInput,
} = useBrowserCamera({
  onMessage: setOperationMessage,
  onStop: () => {
    realtimeVideoActive.value = false;
  },
});

const latestRun = computed(() => store.currentCase?.analysis_runs.at(-1) ?? null);
const inputAssets = computed(() => store.currentCase?.inputs ?? []);
const metricEntries = computed(() => Object.entries(latestRun.value?.quantitative_summary ?? {}));
const latestCandidates = computed<CandidateRegion[]>(() => latestRun.value?.candidate_regions ?? []);
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
    { label: "导出 Manifest", path: result.manifest_path },
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
  { label: "分析任务", value: latestMode.value === "video_file_keyframes" ? "MP4关键帧" : "荧光融合", icon: "clipboard" },
  { label: "输入通道", value: `${displayInputAssets.value.length} 个`, icon: "layers" },
  { label: "候选区域", value: String(displayCandidates.value.length), icon: "target" },
  { label: "分析状态", value: latestRunStatusLabel.value, icon: "document" },
]);

const previewPanels = computed<AnalysisPreviewPanel[]>(() => {
  const overlays = previewOverlays.value;
  const videoPanels = videoPreviewPanelsFromRun(
    latestRun.value,
    apiClient.filePreviewUrl,
    selectedHotspotTimelineKey.value,
  );
  if (videoPanels.length) return videoPanels.slice(0, 3).map((panel) => ({ ...panel, overlays }));
  return [
    previewPanel("融合图", `融合透明度: ${alpha.value.toFixed(2)}`, `伪彩方案: ${colormapLabel(colormap.value)}`, "白光 + ICG", stringFrom(outputPaths.value.overlay_path)),
    previewPanel("热图", `当前阈值: ${threshold.value.toFixed(2)}`, "色标范围: 0 - 1", "0        1.0", stringFrom(outputPaths.value.heatmap_path)),
    previewPanel("归一化图", "归一化方法: Min-Max", "范围: 0 - 1", "normalized", stringFrom(outputPaths.value.normalized_fluorescence_path)),
  ].map((panel) => ({ ...panel, overlays }));
});

const allHotspotTimelineItems = computed(() => hotspotTimelineFromRun(latestRun.value, apiClient.filePreviewUrl));
const hotspotTimelineItems = computed(() =>
  filterHotspotTimelineItems(allHotspotTimelineItems.value, hotspotTimelineFilter.value),
);
const selectedHotspotFrameDetail = computed<HotspotFrameDetail | null>(() =>
  selectedHotspotFrameDetailFromRun(latestRun.value, apiClient.filePreviewUrl, selectedHotspotTimelineKey.value),
);
const hotspotFrameDetails = computed<HotspotFrameDetail[]>(() =>
  hotspotFrameDetailsFromRun(latestRun.value, apiClient.filePreviewUrl),
);
const timelineManifestSummary = computed(() =>
  timelineManifestSummaryFromRun(latestRun.value, apiClient.fileDownloadUrl),
);
const fusionEvidenceSummary = computed<FusionEvidenceSummary | null>(() =>
  fusionEvidenceSummaryFromRun(latestRun.value, apiClient.filePreviewUrl),
);
const previewOverlays = computed(() => [
  ...roiOverlaysFromRegions(store.currentCase?.rois ?? []),
  ...candidateOverlaysFromRegions(latestCandidates.value),
]);

watch(
  () =>
    store.currentCase
      ? [
          store.currentCase.case_id,
          ...store.currentCase.inputs.map((asset) => `${asset.input_id}:${asset.channel}:${asset.path}`),
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
    videoPath.value = "";
  }
  const latestByChannel = (channel: CaseInputAsset["channel"]) =>
    [...caseRecord.inputs].reverse().find((asset) => asset.channel === channel)?.path ?? "";
  const white = latestByChannel("white_light");
  const fluorescence = latestByChannel("fluorescence");
  const video = latestByChannel("video");
  if (white && (caseChanged || !whiteLightPath.value.trim())) whiteLightPath.value = white;
  if (fluorescence && (caseChanged || !fluorescencePath.value.trim())) fluorescencePath.value = fluorescence;
  if (video && (caseChanged || !videoPath.value.trim())) videoPath.value = video;
}

function selectHotspotFrame(key: string) {
  selectedHotspotTimelineKey.value = key;
}

function updateHotspotTimelineFilter(filter: HotspotTimelineFilter) {
  hotspotTimelineFilter.value = filter;
}

async function importInputs() {
  if (!store.currentCase) {
    setOperationMessage("请先新建或加载病例。", "error");
    return;
  }
  if (!whiteLightPath.value.trim() || !fluorescencePath.value.trim()) {
    setOperationMessage("请先提供白光和 ICG 荧光两路输入。", "error");
    return;
  }
  setOperationMessage("正在写入双通道输入...");
  await store.importInputs([
    { channel: "white_light", path: whiteLightPath.value.trim() },
    { channel: "fluorescence", path: fluorescencePath.value.trim() },
  ]);
  setOperationMessage(store.error || "双通道输入已写入病例。", store.error ? "error" : "info");
}

async function importVideoInput(): Promise<boolean> {
  if (!store.currentCase) {
    setOperationMessage("请先新建或加载病例。", "error");
    return false;
  }
  const source = videoPath.value.trim();
  if (!source) {
    setOperationMessage("请先提供官方 MP4 视频路径。", "error");
    return false;
  }
  const exists = store.currentCase.inputs.some((asset) => asset.channel === "video" && asset.path === source);
  if (exists) {
    setOperationMessage("MP4 视频输入已存在，本次直接复用。");
    return true;
  }
  setOperationMessage("正在写入官方 MP4 视频输入...");
  await store.importInputs([
    {
      channel: "video",
      path: source,
      mime_type: "video/mp4",
      metadata: {
        acquisition_mode: "official_mp4_upload",
        official_resolution: "3840x2160",
      },
    },
  ]);
  const ok = !store.error;
  setOperationMessage(store.error || "MP4 视频输入已写入病例。", ok ? "info" : "error");
  return ok;
}

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
  setOperationMessage("正在运行双通道分析...");
  await store.runAnalysis({
    alpha: alpha.value,
    threshold: threshold.value,
    colormap: colormap.value,
  }, roiHintsFromCurrentCase());
  setOperationMessage(
    store.error || latestRunFailureMessage() || "分析完成，结果已同步到工作台。",
    store.error || latestRunFailureMessage() ? "error" : "info",
  );
}

async function runVideoFileAnalysis() {
  if (!store.currentCase) {
    setOperationMessage("请先新建或加载病例。", "error");
    return;
  }
  const source = videoPath.value.trim();
  if (!source) {
    setOperationMessage("请先提供官方 MP4 视频路径。", "error");
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
  await store.runAnalysisJob({
    mode: "video_file",
    source_path: source,
    keyframe_count: 5,
    ...(requestedTimestamps.length ? { keyframe_timestamps_sec: requestedTimestamps } : {}),
    alpha: alpha.value,
    threshold: threshold.value,
    colormap: colormap.value,
  }, roiHintsFromCurrentCase());
  realtimeVideoActive.value = false;
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
    store.error || `MP4 分析完成，已抽取 ${count} 帧，生成 ${hotspotCount} 个热点候选区。`,
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
    setOperationMessage("请先提供官方 MP4 视频路径。", "error");
    return;
  }
  const detail = selectedHotspotFrameDetail.value;
  if (!detail) {
    setOperationMessage("请先在 MP4 热点时间轴中选择需要重算的帧。", "error");
    return;
  }
  const imported = await importVideoInput();
  if (!imported) return;

  const manualFrameParameter =
    typeof detail.timestampSec === "number" && Number.isFinite(detail.timestampSec)
      ? { keyframe_timestamps_sec: [detail.timestampSec] }
      : typeof detail.frameIndex === "number" && Number.isFinite(detail.frameIndex)
        ? { keyframe_frame_indexes: [detail.frameIndex] }
        : null;
  if (!manualFrameParameter) {
    setOperationMessage("当前帧缺少可重算的时间戳或帧号。", "error");
    return;
  }

  setOperationMessage(`正在重算 ${detail.frameLabel}...`);
  await store.runAnalysisJob({
    mode: "video_file",
    source_path: source,
    keyframe_count: 1,
    ...manualFrameParameter,
    alpha: alpha.value,
    threshold: threshold.value,
    colormap: colormap.value,
  }, roiHintsFromCurrentCase());
  realtimeVideoActive.value = false;
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

async function refreshAnalysisJob() {
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
  if (!store.activeAnalysisJobId) {
    setOperationMessage("暂无可取消的后台分析任务。", "error");
    return;
  }
  setOperationMessage("正在取消后台分析任务...");
  await store.cancelActiveAnalysisJob();
  setOperationMessage(store.error || `后台分析任务 ${store.activeAnalysisJobId} 已更新为 ${store.activeAnalysisJobStatus || "unknown"}。`, store.error ? "error" : "info");
}

async function retryAnalysisJob() {
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

async function importCameraInput(): Promise<boolean> {
  if (!store.currentCase) {
    setOperationMessage("请先新建或加载病例。", "error");
    return false;
  }
  if (!cameraActive.value) {
    setOperationMessage("请先打开摄像头。", "error");
    return false;
  }

  const existingCameraInput = store.currentCase.inputs.some((asset) => asset.path === "camera://browser/default");
  if (existingCameraInput) {
    setOperationMessage("摄像头输入已存在，本次直接复用实时预览通道。");
    return true;
  }

  setOperationMessage("正在写入摄像头输入...");
  await store.importInputs([
    {
      channel: "video",
      path: "camera://browser/default",
      mime_type: "application/x-browser-camera",
      metadata: {
        source: "browser_camera",
        acquisition_mode: "live_preview",
        created_at: new Date().toISOString(),
      },
    },
  ]);
  const ok = !store.error;
  setOperationMessage(store.error || "摄像头输入已写入病例，当前为实时预览模式。", ok ? "info" : "error");
  return ok;
}

async function runRealtimeVideoAnalysis() {
  if (!store.currentCase) {
    setOperationMessage("请先新建或加载病例。", "error");
    return;
  }

  const opened = cameraActive.value || (await startCameraInput());
  if (!opened) return;

  const imported = await importCameraInput();
  if (!imported) return;

  setOperationMessage("正在启动实时视频分析预览...");
  await store.runAnalysis({
    mode: "realtime_video",
    alpha: alpha.value,
    threshold: threshold.value,
    colormap: colormap.value,
    source_path: "camera://browser/default",
  }, roiHintsFromCurrentCase());
  realtimeVideoActive.value = !store.error;
  setOperationMessage(
    store.error || "实时视频分析预览已启动；当前只登记实时输入与运行记录，AI 流式推理尚未接入。",
    store.error ? "error" : "info",
  );
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

async function handleFilePicked(channel: "white_light" | "fluorescence" | "video", event: Event) {
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

async function uploadSelectedImage(channel: "white_light" | "fluorescence", file: File) {
  // 上传成功后填入后端保存路径，后续“写入输入”和“运行分析”都会使用这个真实路径。
  const isWhite = channel === "white_light";
  if (isWhite) {
    isUploadingWhite.value = true;
  } else {
    isUploadingFluorescence.value = true;
  }
  setOperationMessage(`正在上传${isWhite ? "白光" : "ICG 荧光"}图像：${file.name}`);
  try {
    const uploaded = await apiClient.uploadRawImage(file);
    if (isWhite) {
      whiteLightPath.value = uploaded.path;
    } else {
      fluorescencePath.value = uploaded.path;
    }
    setOperationMessage(`${isWhite ? "白光" : "ICG 荧光"}图像已上传：${uploaded.path}；${officialProfileLabel(uploaded)}`);
  } catch (error) {
    setOperationMessage(errorMessage(error), "error");
  } finally {
    if (isWhite) {
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
    if (uploaded.keyframe_job_id) {
      setOperationMessage(`MP4 视频已保存：${uploaded.path}；${officialProfileLabel(uploaded)}；关键帧后台任务已创建。`);
      const job = await waitForUploadJob(uploaded.keyframe_job_id);
      const keyframeCount = keyframeCountFromJob(job.result);
      setOperationMessage(`MP4 视频已上传：${uploaded.path}；${officialProfileLabel(uploaded)}；后台预抽取关键帧 ${keyframeCount} 张。`);
    } else {
      const keyframeCount = uploaded.keyframes?.length ?? 0;
      setOperationMessage(`MP4 视频已上传：${uploaded.path}；${officialProfileLabel(uploaded)}；预抽取关键帧 ${keyframeCount} 张。`);
    }
  } catch (error) {
    setOperationMessage(errorMessage(error), "error");
  } finally {
    isUploadingVideo.value = false;
  }
}

async function waitForUploadJob(jobId: string) {
  let job = await apiClient.getUploadJob(jobId);
  for (let attempt = 0; attempt < 180 && ["queued", "running"].includes(job.status); attempt += 1) {
    if (attempt === 20 || attempt === 60 || attempt === 120) {
      setOperationMessage("MP4 关键帧后台任务仍在处理，可继续等待。");
    }
    await sleep(1000);
    job = await apiClient.getUploadJob(jobId);
  }
  return job;
}

function keyframeCountFromJob(result: Record<string, unknown> | undefined): number {
  const keyframes = result?.keyframes;
  return Array.isArray(keyframes) ? keyframes.length : 0;
}

function officialProfileLabel(uploaded: { metadata?: Record<string, unknown> }): string {
  const profile = isRecord(uploaded.metadata?.official_input_profile) ? uploaded.metadata.official_input_profile : null;
  if (!profile) return "官方规格未读取";
  if (profile.status === "official_profile_match") return "官方规格匹配";
  const observed = Array.isArray(profile.observed_resolution) ? profile.observed_resolution.join("×") : "";
  const target = Array.isArray(profile.target_resolution) ? profile.target_resolution.join("×") : "3840×2160";
  return observed ? `官方规格需确认：${observed} / 目标 ${target}` : "官方规格需确认";
}

function countLabel(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) return String(Math.max(0, Math.round(value)));
  if (typeof value === "string" && value.trim()) return value.trim();
  return "0";
}

function latestRunFailureMessage(): string {
  const latest = store.currentCase?.analysis_runs.at(-1);
  if (latest?.status !== "failed") return "";
  const warning = latest.warnings.find((item) => Boolean(item.blocking)) ?? latest.warnings[0];
  return warning ? normalizeWarning(warning, 0).message : "分析未通过，请检查输入和参数。";
}

function parseVideoTimepoints(value: string): number[] {
  return value
    .split(/[,\s，；;]+/)
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isFinite(item) && item >= 0);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
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
  padding: 14px 28px 24px;
  background:
    radial-gradient(circle at 12% 4%, rgba(44, 126, 192, 0.28), transparent 28%),
    radial-gradient(circle at 86% 0%, rgba(58, 211, 255, 0.16), transparent 30%),
    linear-gradient(rgba(103, 222, 255, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(103, 222, 255, 0.035) 1px, transparent 1px),
    linear-gradient(180deg, #07131f, #091724 360px, #06101b);
  background-size: auto, auto, 28px 28px, 28px 28px, auto;
  color: #d8edf7;
}

.workspace-header,
.review-notice,
.workspace-grid {
  width: min(100%, 1540px);
  margin-right: auto;
  margin-left: auto;
}

.workspace-header {
  padding: 0 2px 12px;
}

.workspace-title {
  min-width: 0;
}

.workspace-title h1 {
  margin: 0;
  color: #f2fbff;
  font-size: 32px;
  line-height: 1.15;
  letter-spacing: 0;
  text-shadow: 0 0 22px rgba(103, 222, 255, 0.22);
  overflow-wrap: anywhere;
}

.review-notice {
  margin-bottom: 12px;
  border: 1px solid rgba(231, 174, 82, 0.5);
  border-radius: 5px;
  background: rgba(47, 35, 15, 0.72);
  box-shadow: 0 0 22px rgba(231, 174, 82, 0.08);
}

.review-notice summary {
  display: grid;
  grid-template-columns: 24px auto minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  min-height: 40px;
  padding: 7px 12px;
  cursor: pointer;
  list-style: none;
}

.review-notice summary::-webkit-details-marker {
  display: none;
}

.review-notice summary::after {
  justify-self: end;
  color: #aa7128;
  font-size: 12px;
  font-weight: 900;
  content: "详情";
}

.review-notice[open] summary {
  border-bottom: 1px solid rgba(228, 155, 63, 0.34);
}

.review-notice[open] summary::after {
  content: "收起";
}

.notice-icon {
  width: 22px;
  height: 22px;
}

.review-notice strong {
  color: #ffd58f;
  font-size: 14px;
  white-space: nowrap;
}

.review-notice span {
  min-width: 0;
  color: #d8c8ab;
  font-size: 13px;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.review-notice p {
  margin: 0;
  padding: 10px 14px 12px 46px;
  color: #d8c8ab;
  font-size: 13px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.workspace-grid {
  display: grid;
  grid-template-columns: minmax(284px, 304px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.workspace-sidebar {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.analysis-column {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.result-card,
.debug-panel {
  min-width: 0;
  border: 1px solid rgba(123, 215, 255, 0.26);
  border-radius: 6px;
  background: rgba(8, 22, 36, 0.86);
  box-shadow:
    0 0 0 1px rgba(71, 208, 255, 0.08) inset,
    0 14px 34px rgba(0, 0, 0, 0.16);
}

.result-card {
  padding: 13px 15px;
}

.result-card :deep(.ov-section-heading) {
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(121, 209, 255, 0.22);
}

.result-card :deep(.ov-section-heading__title) {
  color: #f2fbff;
  font-size: 15px;
}

.result-card :deep(.ov-section-heading__eyebrow) {
  display: none;
}

.empty-inline {
  margin: 0;
  border: 1px solid rgba(123, 215, 255, 0.22);
  border-radius: 5px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.045);
  color: #9fb8c8;
  font-size: 13px;
  line-height: 1.5;
}

.debug-panel {
  opacity: 0.72;
  padding: 0;
  background: rgba(8, 22, 36, 0.86);
}

.debug-panel summary {
  cursor: pointer;
  padding: 8px 12px;
  color: #9fb8c8;
  font-size: 12px;
  font-weight: 900;
}

.debug-panel pre {
  max-height: 260px;
  margin: 0;
  overflow: auto;
  border-top: 1px solid rgba(121, 209, 255, 0.22);
  padding: 12px 16px;
  color: #c4d9e6;
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
  border-color: rgba(123, 215, 255, 0.25);
  background:
    linear-gradient(180deg, rgba(13, 34, 52, 0.94), rgba(7, 20, 34, 0.94)),
    #081624;
  color: #d9edf7;
  box-shadow:
    0 0 0 1px rgba(71, 208, 255, 0.07) inset,
    0 14px 34px rgba(0, 0, 0, 0.18);
}

.case-workspace :deep(.control-card .ov-section-heading),
.case-workspace :deep(.compact-card-header),
.case-workspace :deep(.analysis-header),
.case-workspace :deep(.fusion-evidence-panel header),
.case-workspace :deep(.hotspot-timeline header),
.case-workspace :deep(.timeline-manifest-panel header) {
  border-color: rgba(121, 209, 255, 0.22);
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
  color: #f2fbff;
}

.case-workspace :deep(.field span),
.case-workspace :deep(.camera-panel-copy span),
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
  color: #9dbccc;
}

.case-workspace :deep(input),
.case-workspace :deep(select),
.case-workspace :deep(output) {
  border-color: rgba(123, 215, 255, 0.28);
  background: rgba(3, 14, 25, 0.78);
  color: #eefaff;
}

.case-workspace :deep(input::placeholder) {
  color: #7694a8;
}

.case-workspace :deep(input:focus),
.case-workspace :deep(select:focus) {
  border-color: #74d7ff;
  outline: 2px solid rgba(116, 215, 255, 0.22);
}

.case-workspace :deep(.camera-input-panel),
.case-workspace :deep(.video-candidate-card),
.case-workspace :deep(.metric-grid div),
.case-workspace :deep(.candidate-list li),
.case-workspace :deep(.summary-chip),
.case-workspace :deep(.export-link),
.case-workspace :deep(.export-summary-grid div),
.case-workspace :deep(.export-artifact-list li),
.case-workspace :deep(.fusion-colorbar),
.case-workspace :deep(.fusion-evidence-grid div),
.case-workspace :deep(.timeline-summary-grid div),
.case-workspace :deep(.timeline-trace-list li),
.case-workspace :deep(.hotspot-timeline-item),
.case-workspace :deep(.hotspot-frame-row) {
  border-color: rgba(123, 215, 255, 0.2);
  background: rgba(255, 255, 255, 0.045);
}

.case-workspace :deep(.analysis-quad-viewport) {
  border-color: rgba(123, 215, 255, 0.24);
  background:
    linear-gradient(90deg, rgba(86, 207, 255, 0.055) 1px, transparent 1px),
    linear-gradient(180deg, rgba(86, 207, 255, 0.055) 1px, transparent 1px),
    radial-gradient(circle at 50% 40%, rgba(55, 182, 255, 0.12), transparent 38%),
    linear-gradient(180deg, #081623, #06111d);
  background-size: 28px 28px, 28px 28px, auto, auto;
}

.case-workspace :deep(.camera-viewport) {
  background:
    linear-gradient(90deg, rgba(86, 207, 255, 0.07) 1px, transparent 1px),
    linear-gradient(180deg, rgba(86, 207, 255, 0.07) 1px, transparent 1px),
    linear-gradient(145deg, #0b2130, #07131f);
  background-size: 24px 24px, 24px 24px, auto;
}

.case-workspace :deep(.empty-preview-copy) {
  border-color: rgba(123, 215, 255, 0.32);
  background: rgba(7, 20, 34, 0.78);
  color: #9dbccc;
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.22);
}

.case-workspace :deep(.empty-preview-copy strong) {
  color: #dff6ff;
}

.case-workspace :deep(.empty-preview-copy span) {
  color: #9dbccc;
}

.case-workspace :deep(.app-button) {
  border-color: rgba(116, 215, 255, 0.34);
  background: linear-gradient(180deg, rgba(15, 45, 68, 0.96), rgba(7, 25, 41, 0.96));
  color: #dff7ff;
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.08) inset,
    0 8px 18px rgba(0, 0, 0, 0.18);
}

.case-workspace :deep(.app-button--primary) {
  border-color: #74d7ff;
  background: linear-gradient(180deg, #2f8dcc, #155f96);
  color: #ffffff;
}

.case-workspace :deep(.app-button--ghost) {
  background: rgba(18, 52, 76, 0.82);
  color: #bdefff;
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
  border: 1px solid rgba(123, 215, 255, 0.24);
  background: rgba(255, 255, 255, 0.06);
  color: #bdefff;
}

.case-workspace :deep(.run-pill.running),
.case-workspace :deep(.job-panel.timeout) {
  border-color: rgba(231, 174, 82, 0.45);
  background: rgba(47, 35, 15, 0.62);
  color: #ffd58f;
}

.case-workspace :deep(.run-pill.failed),
.case-workspace :deep(.state-message.error),
.case-workspace :deep(.operation-message.error) {
  border-color: rgba(255, 116, 122, 0.42);
  background: rgba(68, 19, 25, 0.68);
  color: #ffd3d6;
}

.case-workspace :deep(.operation-message),
.case-workspace :deep(.realtime-status),
.case-workspace :deep(.state-message.muted),
.case-workspace :deep(.hotspot-empty-state) {
  border-color: rgba(123, 215, 255, 0.22);
  background: rgba(255, 255, 255, 0.045);
  color: #9dbccc;
}

.case-workspace :deep(.summary-divider),
.case-workspace :deep(.hotspot-frame-table) {
  border-color: rgba(121, 209, 255, 0.18);
  background: transparent;
}

@media (max-width: 1359px) {
  .workspace-grid {
    grid-template-columns: minmax(278px, 296px) minmax(0, 1fr);
  }
}

@media (max-width: 959px) {
  .case-workspace {
    padding: 14px;
  }

  .workspace-grid {
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
