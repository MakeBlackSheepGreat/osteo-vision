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
          v-model:alpha="alpha"
          v-model:threshold="threshold"
          v-model:colormap="colormap"
          :loading="store.loading"
          :has-case="Boolean(store.currentCase)"
          :is-uploading-white="isUploadingWhite"
          :is-uploading-fluorescence="isUploadingFluorescence"
          :camera-active="cameraActive"
          :camera-status-label="cameraStatusLabel"
          :is-opening-camera="isOpeningCamera"
          :operation-message="operationMessage"
          :operation-message-type="operationMessageType"
          :realtime-video-active="realtimeVideoActive"
          @file-picked="handleFilePicked"
          @import-inputs="importInputs"
          @start-camera="startCameraInput"
          @stop-camera="stopCameraInput"
          @import-camera="importCameraInput"
          @run-analysis="runAnalysis"
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
          :latest-run-status-label="latestRunStatusLabel"
          :analysis-status-class="analysisStatusClass"
          :kpi-items="kpiItems"
          :preview-panels="previewPanels"
          :camera-stream="cameraStream"
          :camera-active="cameraActive"
          :camera-status-label="cameraStatusLabel"
          :analysis-expanded="analysisExpanded"
          @export="exportCase"
          @open-fullscreen="openAnalysisFullscreen"
          @close-fullscreen="closeAnalysisFullscreen"
        />

        <details class="debug-panel">
          <summary>开发调试数据</summary>
          <pre>{{ store.currentCase }}</pre>
        </details>
      </section>
    </section>

  </main>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";

import AnalysisResultPanels from "@/components/AnalysisResultPanels.vue";
import AnalysisWorkspaceCard from "@/components/AnalysisWorkspaceCard.vue";
import CaseWorkspaceControls from "@/components/CaseWorkspaceControls.vue";
import AppIcon from "@/components/AppIcon.vue";
import type { AnalysisPreviewPanel } from "@/components/analysisPreview";
import type { AppIconName } from "@/components/appIcons";
import { useBrowserCamera } from "@/composables/useBrowserCamera";
import { useFullscreenPanel } from "@/composables/useFullscreenPanel";
import { useOperationMessage } from "@/composables/useOperationMessage";
import { apiClient } from "@/services/apiClient";
import { useCaseStore } from "@/stores/caseStore";
import type { CandidateRegion, CaseInputAsset } from "@/types/case";
import {
  colormapLabel,
  errorMessage,
  isRecord,
  runStatusLabel,
  stringFrom,
} from "@/utils/caseDisplay";

const store = useCaseStore();

// 页面层保留业务流程编排：上传、写入病例、触发分析和导出。
const whiteLightPath = ref("");
const fluorescencePath = ref("");
const alpha = ref(0.45);
const threshold = ref(0.6);
const colormap = ref<"green" | "amber" | "magenta">("green");
const isUploadingWhite = ref(false);
const isUploadingFluorescence = ref(false);
const realtimeVideoActive = ref(false);
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

const outputPaths = computed<Record<string, unknown>>(() => {
  const fusedOutputs = latestRun.value?.fused_outputs ?? {};
  const nestedOutputs = isRecord(fusedOutputs.outputs) ? fusedOutputs.outputs : {};
  return { ...fusedOutputs, ...nestedOutputs };
});

const displayInputAssets = computed<CaseInputAsset[]>(() => (store.currentCase ? inputAssets.value : []));
const displayCandidates = computed<CandidateRegion[]>(() => (store.currentCase ? latestCandidates.value : []));

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
  { label: "分析任务", value: "荧光融合", icon: "clipboard" },
  { label: "输入通道", value: `${displayInputAssets.value.length} 个`, icon: "layers" },
  { label: "候选区域", value: String(displayCandidates.value.length), icon: "target" },
  { label: "分析状态", value: latestRunStatusLabel.value, icon: "document" },
]);

const previewPanels = computed<AnalysisPreviewPanel[]>(() => [
  {
    title: "融合图",
    tag: `融合透明度: ${alpha.value.toFixed(2)}`,
    label: `伪彩方案: ${colormapLabel(colormap.value)}`,
    scale: "白光 + ICG",
    path: stringFrom(outputPaths.value.overlay_path),
  },
  {
    title: "热图",
    tag: `当前阈值: ${threshold.value.toFixed(2)}`,
    label: "色标范围: 0 - 1",
    scale: "0        1.0",
    path: stringFrom(outputPaths.value.heatmap_path),
  },
  {
    title: "归一化图",
    tag: "归一化方法: Min-Max",
    label: "范围: 0 - 1",
    scale: "normalized",
    path: stringFrom(outputPaths.value.normalized_fluorescence_path),
  },
]);

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
  });
  setOperationMessage(store.error || "分析完成，结果已同步到工作台。", store.error ? "error" : "info");
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
  });
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

async function handleFilePicked(channel: "white_light" | "fluorescence", event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;
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
    setOperationMessage(`${isWhite ? "白光" : "ICG 荧光"}图像已上传：${uploaded.path}`);
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

</script>

<style scoped>
.case-workspace {
  min-height: 100dvh;
  padding: 14px 28px 24px;
  background:
    linear-gradient(180deg, rgba(236, 243, 250, 0.96), rgba(246, 249, 252, 0.98) 260px),
    #f3f6fa;
  color: #162020;
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
  color: #102136;
  font-size: 32px;
  line-height: 1.15;
  letter-spacing: 0;
  overflow-wrap: anywhere;
}

.review-notice {
  margin-bottom: 12px;
  border: 1px solid #e49b3f;
  border-radius: 5px;
  background: #fffaf0;
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
  border-bottom: 1px solid rgba(228, 155, 63, 0.42);
}

.review-notice[open] summary::after {
  content: "收起";
}

.notice-icon {
  width: 22px;
  height: 22px;
}

.review-notice strong {
  color: #bd650c;
  font-size: 14px;
  white-space: nowrap;
}

.review-notice span {
  min-width: 0;
  color: #405060;
  font-size: 13px;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.review-notice p {
  margin: 0;
  padding: 10px 14px 12px 46px;
  color: #405060;
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
  border: 1px solid #d6e0eb;
  border-radius: 6px;
  background: #ffffff;
  box-shadow: 0 2px 12px rgba(39, 74, 106, 0.06);
}

.result-card {
  padding: 13px 15px;
}

.result-card :deep(.ov-section-heading) {
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid #e3ebf3;
}

.result-card :deep(.ov-section-heading__title) {
  color: #102136;
  font-size: 15px;
}

.result-card :deep(.ov-section-heading__eyebrow) {
  display: none;
}

.empty-inline {
  margin: 0;
  border: 1px solid #e0e8f1;
  border-radius: 5px;
  padding: 10px 12px;
  background: #fbfdff;
  color: #6a7a8a;
  font-size: 13px;
  line-height: 1.5;
}

.debug-panel {
  opacity: 0.72;
  padding: 0;
  background: #f8fbfe;
}

.debug-panel summary {
  cursor: pointer;
  padding: 8px 12px;
  color: #5a6a7a;
  font-size: 12px;
  font-weight: 900;
}

.debug-panel pre {
  max-height: 260px;
  margin: 0;
  overflow: auto;
  border-top: 1px solid #e0e8f1;
  padding: 12px 16px;
  color: #405060;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
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
