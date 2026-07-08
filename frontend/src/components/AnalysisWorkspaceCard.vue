<template>
  <section class="analysis-card">
    <header class="analysis-header">
      <div class="analysis-title-block">
        <h2>双通道融合与风险提示</h2>
        <div class="analysis-summary-strip" aria-label="分析摘要">
          <span v-for="kpi in kpiItems" :key="kpi.label" class="summary-chip">
            <AppIcon :name="kpi.icon" />
            <span>{{ kpi.label }}</span>
            <strong>{{ kpi.value }}</strong>
          </span>
        </div>
      </div>
      <div class="analysis-header-actions">
        <span class="run-pill" :class="analysisStatusClass">{{ latestRunStatusLabel }}</span>
        <AppButton
          class="header-export-button"
          variant="secondary"
          size="sm"
          icon="download"
          :disabled="loading || !hasCase"
          @click="emit('export')"
        >
          导出证据包
        </AppButton>
        <AppButton
          variant="ghost"
          size="sm"
          icon="expand"
          icon-only
          title="进入全屏分析视图"
          aria-label="进入全屏分析视图"
          @click="emit('openFullscreen')"
        />
      </div>
    </header>

    <div v-if="loading" class="state-message">正在处理，请等待后端返回结果。</div>
    <div v-else-if="error" class="state-message error">{{ error }}</div>
    <div v-else-if="!hasCase" class="state-message muted">空白预览态，运行后同步真实输出。</div>
    <AnalysisJobPanel
      v-if="activeAnalysisJobId"
      :job-id="activeAnalysisJobId"
      :status="activeAnalysisJobStatus"
      :error="activeAnalysisJobError"
      :progress="activeAnalysisJobProgress"
      :timed-out="lastAnalysisJobTimedOut"
      :loading="loading"
      @refresh="emit('refreshJob')"
      @cancel="emit('cancelJob')"
      @retry="emit('retryJob')"
    />
    <AnalysisExportPanel
      v-if="exportPath"
      :export-path="exportPath"
      :export-links="exportLinks"
      :export-summary="exportSummary"
      :artifact-entries="exportArtifactEntries"
    />

    <AnalysisQuadGrid
      :panels="previewPanels"
      :camera-stream="cameraStream"
      :camera-active="cameraActive"
      :camera-status-label="cameraStatusLabel"
      :video-playback="videoPlayback"
      :current-playback-time="currentPlaybackTime"
      :playback-duration="playbackDuration"
      :playback-seek-time-sec="playbackSeekTimeSec"
      :playback-seek-token="playbackSeekToken"
      :camera-opening="cameraOpening"
      @playback-state-change="syncPlaybackState"
      @start-camera="emit('startCamera')"
      @stop-camera="emit('stopCamera')"
    />

    <VideoStreamSyncPanel
      v-if="videoPlayback"
      :video-playback="videoPlayback"
      :nearest-frame-detail="nearestPlaybackFrameDetail"
      @jump-to-frame="jumpPlaybackToDetail"
      @generate-bone-gate="emit('generateBoneGateForFrame')"
      @edit-bone-gate="maskEditorOpen = true"
    />

    <AnalysisFusionEvidencePanel v-if="fusionEvidenceSummary" :summary="fusionEvidenceSummary" />

    <section v-if="hotspotTimelineTotalCount" class="hotspot-timeline" aria-label="MP4 分割时间轴">
      <header>
        <AppIcon name="video" />
        <strong>MP4 分割时间轴</strong>
        <span>{{ hotspotTimelineItems.length }} / {{ hotspotTimelineTotalCount }} 帧</span>
      </header>
      <div class="hotspot-filter-group" aria-label="分割时间轴筛选">
        <button
          v-for="option in hotspotTimelineFilterOptions"
          :key="option.value"
          type="button"
          :class="{ selected: hotspotTimelineFilter === option.value }"
          :aria-pressed="hotspotTimelineFilter === option.value"
          @click="emit('updateHotspotTimelineFilter', option.value)"
        >
          {{ option.label }}
        </button>
      </div>
      <section v-if="timelineManifestSummary" class="timeline-manifest-panel" aria-label="时间轴 Manifest">
        <header>
          <div>
            <AppIcon name="document" />
            <strong>时间轴 Manifest</strong>
          </div>
          <a
            v-if="timelineManifestSummary.manifestHref"
            :href="timelineManifestSummary.manifestHref"
            target="_blank"
            rel="noreferrer"
          >
            下载 JSON
          </a>
        </header>
        <dl class="timeline-summary-grid">
          <div>
            <dt>覆盖范围</dt>
            <dd>{{ timelineManifestSummary.scopeLabel }}</dd>
          </div>
          <div>
            <dt>采样策略</dt>
            <dd>{{ timelineManifestSummary.samplingLabel }}</dd>
          </div>
          <div>
            <dt>视频帧数</dt>
            <dd>{{ timelineManifestSummary.frameCountLabel }}</dd>
          </div>
          <div>
            <dt>时长</dt>
            <dd>{{ timelineManifestSummary.durationLabel }}</dd>
          </div>
          <div>
            <dt>FPS</dt>
            <dd>{{ timelineManifestSummary.fpsLabel }}</dd>
          </div>
          <div>
            <dt>索引步长</dt>
            <dd>{{ timelineManifestSummary.coverageLabel }}</dd>
          </div>
          <div>
            <dt>选中关键帧</dt>
            <dd>{{ timelineManifestSummary.selectedFrameCountLabel }}</dd>
          </div>
          <div>
            <dt>候选帧</dt>
            <dd>{{ timelineManifestSummary.candidateFrameCountLabel }}</dd>
          </div>
          <div>
            <dt>重复候选</dt>
            <dd>{{ timelineManifestSummary.duplicateCountLabel }}</dd>
          </div>
          <div>
            <dt>跳过重复</dt>
            <dd>{{ timelineManifestSummary.skippedDuplicateCountLabel }}</dd>
          </div>
        </dl>
        <div v-if="timelineManifestSummary.traceItems.length" class="timeline-trace-list">
          <strong>候选 Trace</strong>
          <ul>
            <li v-for="item in timelineManifestSummary.traceItems" :key="item.key">
              <span>{{ item.frameLabel }}</span>
              <small>{{ item.rankLabel }} · score {{ item.scoreLabel }} · {{ item.statusLabel }}</small>
            </li>
          </ul>
        </div>
        <div v-if="timelineManifestSummary.duplicateItems.length" class="timeline-trace-list duplicate">
          <strong>重复帧组</strong>
          <ul>
            <li v-for="item in timelineManifestSummary.duplicateItems" :key="item.key">
              <span>{{ item.frameLabel }}</span>
              <small>{{ item.duplicateLabel }}</small>
            </li>
          </ul>
        </div>
      </section>
      <div v-if="hotspotTimelineItems.length" class="hotspot-timeline-list">
        <button
          v-for="item in hotspotTimelineItems"
          :key="item.key"
          class="hotspot-timeline-item"
          :class="{ selected: selectedHotspotTimelineKey === item.key }"
          type="button"
          :aria-pressed="selectedHotspotTimelineKey === item.key"
          @click="emit('selectHotspotFrame', item.key)"
        >
          <img v-if="item.previewSrc" :src="item.previewSrc" :alt="item.frameLabel" />
          <div class="hotspot-timeline-copy">
            <strong>{{ item.frameLabel }}</strong>
            <span>{{ item.timestampLabel }} · {{ item.candidateCountLabel }}</span>
            <dl>
              <div>
                <dt>阳性面积</dt>
                <dd>{{ item.positiveAreaLabel }}</dd>
              </div>
              <div>
                <dt>ROI 命中</dt>
                <dd>{{ item.roiAreaLabel }}</dd>
              </div>
            </dl>
          </div>
          <div class="hotspot-score-bar" aria-hidden="true">
            <span :style="{ width: `${Math.min(100, Math.max(0, item.score * 100))}%` }"></span>
          </div>
        </button>
      </div>
      <p v-else class="hotspot-empty-state">当前筛选下没有匹配帧。</p>

      <section v-if="selectedHotspotFrameDetail" class="hotspot-frame-detail" aria-label="当前帧详情">
        <header>
          <div>
            <AppIcon name="document" />
            <strong>当前帧详情</strong>
          </div>
          <div class="hotspot-frame-actions">
            <span>{{ selectedHotspotFrameDetail.frameLabel }} · {{ selectedHotspotFrameDetail.timestampLabel }}</span>
            <AppButton
              variant="ghost"
              size="sm"
              icon="load"
              :disabled="loading"
              @click="emit('reanalyzeHotspotFrame')"
            >
              重算当前帧
            </AppButton>
            <AppButton
              variant="secondary"
              size="sm"
              icon="target"
              :disabled="loading"
              @click="emit('generateBoneGateForFrame')"
            >
              生成骨面门控
            </AppButton>
            <AppButton
              variant="secondary"
              size="sm"
              icon="review"
              :disabled="loading"
              @click="maskEditorOpen = true"
            >
              编辑骨面 mask
            </AppButton>
          </div>
        </header>
        <dl>
          <div>
            <dt>候选数量</dt>
            <dd>{{ selectedHotspotFrameDetail.candidateCountLabel }}</dd>
          </div>
          <div>
            <dt>阳性面积</dt>
            <dd>{{ selectedHotspotFrameDetail.positiveAreaLabel }}</dd>
          </div>
          <div>
            <dt>ROI 命中</dt>
            <dd>{{ selectedHotspotFrameDetail.roiAreaLabel }}</dd>
          </div>
          <div>
            <dt>Top BBox</dt>
            <dd>{{ selectedHotspotFrameDetail.topBBoxLabel }}</dd>
          </div>
        </dl>
        <div class="hotspot-frame-links">
          <a
            v-if="selectedHotspotFrameDetail.evidenceHref"
            :href="selectedHotspotFrameDetail.evidenceHref"
            target="_blank"
            rel="noreferrer"
          >
            证据帧
          </a>
          <a
            v-if="selectedHotspotFrameDetail.overlayHref"
            :href="selectedHotspotFrameDetail.overlayHref"
            target="_blank"
            rel="noreferrer"
          >
            叠加图
          </a>
          <a
            v-if="selectedHotspotFrameDetail.maskHref"
            :href="selectedHotspotFrameDetail.maskHref"
            target="_blank"
            rel="noreferrer"
          >
            掩膜
          </a>
          <a
            v-if="selectedHotspotFrameDetail.boneGateMaskHref"
            :href="selectedHotspotFrameDetail.boneGateMaskHref"
            target="_blank"
            rel="noreferrer"
          >
            骨面门控
          </a>
          <a
            v-if="selectedHotspotFrameDetail.boneGateOverlayHref"
            :href="selectedHotspotFrameDetail.boneGateOverlayHref"
            target="_blank"
            rel="noreferrer"
          >
            骨面叠加
          </a>
          <a
            v-if="selectedHotspotFrameDetail.riskMaskHref"
            :href="selectedHotspotFrameDetail.riskMaskHref"
            target="_blank"
            rel="noreferrer"
          >
            风险图
          </a>
          <a
            v-if="selectedHotspotFrameDetail.uncertainMaskHref"
            :href="selectedHotspotFrameDetail.uncertainMaskHref"
            target="_blank"
            rel="noreferrer"
          >
            不确定性
          </a>
          <span>{{ selectedHotspotFrameDetail.evidenceLabel }}</span>
          <span>{{ selectedHotspotFrameDetail.boneGateStatusLabel }}</span>
        </div>
        <p>{{ selectedHotspotFrameDetail.domainBoundary }}</p>
        <BoneGateMaskEditor
          v-if="maskEditorOpen"
          :detail="selectedHotspotFrameDetail"
          :loading="loading"
          @save="emit('saveBoneGateMaskEdit', $event)"
          @cancel="maskEditorOpen = false"
        />
      </section>

      <details v-if="hotspotFrameDetails.length" class="hotspot-frame-drawer">
        <summary>
          <span>逐帧详情</span>
          <strong>{{ hotspotFrameDetails.length }} 帧</strong>
        </summary>
        <div class="hotspot-frame-table" aria-label="逐帧详情列表">
          <button
            v-for="detail in hotspotFrameDetails"
            :key="detail.key"
            type="button"
            class="hotspot-frame-row"
            :class="{ selected: selectedHotspotTimelineKey === detail.key }"
            @click="emit('selectHotspotFrame', detail.key)"
          >
            <span class="frame-row-main">
              <strong>{{ detail.frameLabel }}</strong>
              <small>{{ detail.timestampLabel }}</small>
            </span>
            <span>
              <small>候选</small>
              <strong>{{ detail.candidateCountLabel }}</strong>
            </span>
            <span>
              <small>阳性面积</small>
              <strong>{{ detail.positiveAreaLabel }}</strong>
            </span>
            <span>
              <small>ROI</small>
              <strong>{{ detail.roiAreaLabel }}</strong>
            </span>
            <span>
              <small>Top BBox</small>
              <strong>{{ detail.topBBoxLabel }}</strong>
            </span>
            <span class="frame-row-status" :class="{ review: detail.reviewRequired }">
              {{ detail.reviewRequired ? "需复核" : "低风险" }}
            </span>
          </button>
        </div>
      </details>
    </section>

  </section>

  <section
    v-if="analysisExpanded"
    class="analysis-fullscreen"
    role="dialog"
    aria-modal="true"
    aria-label="全屏分析视图"
  >
    <div class="analysis-fullscreen-panel">
      <header class="fullscreen-header">
        <h2>双通道融合与风险提示</h2>
        <div class="analysis-header-actions">
          <span class="run-pill" :class="analysisStatusClass">{{ latestRunStatusLabel }}</span>
          <AppButton
            variant="ghost"
            size="sm"
            icon="close"
            icon-only
            title="关闭全屏分析视图"
            aria-label="关闭全屏分析视图"
            @click="emit('closeFullscreen')"
          />
        </div>
      </header>

      <AnalysisQuadGrid
        :panels="previewPanels"
        :camera-stream="cameraStream"
        :camera-active="cameraActive"
        :camera-status-label="cameraStatusLabel"
        :video-playback="videoPlayback"
        :current-playback-time="currentPlaybackTime"
        :playback-duration="playbackDuration"
        :playback-seek-time-sec="playbackSeekTimeSec"
        :playback-seek-token="playbackSeekToken"
        :camera-opening="cameraOpening"
        @playback-state-change="syncPlaybackState"
        @start-camera="emit('startCamera')"
        @stop-camera="emit('stopCamera')"
        fullscreen
      />
    </div>
  </section>
</template>

<script setup lang="ts">
import AnalysisExportPanel from "@/components/AnalysisExportPanel.vue";
import AnalysisFusionEvidencePanel from "@/components/AnalysisFusionEvidencePanel.vue";
import AnalysisJobPanel from "@/components/AnalysisJobPanel.vue";
import AnalysisQuadGrid from "@/components/AnalysisQuadGrid.vue";
import AppButton from "@/components/AppButton.vue";
import AppIcon from "@/components/AppIcon.vue";
import BoneGateMaskEditor from "@/components/BoneGateMaskEditor.vue";
import VideoStreamSyncPanel from "@/components/VideoStreamSyncPanel.vue";
import {
  hotspotTimelineFilterOptions,
  type AnalysisPreviewPanel,
  type FusionEvidenceSummary,
  type HotspotFrameDetail,
  type HotspotTimelineFilter,
  type HotspotTimelineItem,
  type TimelineManifestSummary,
  type VideoPlaybackAnalysis,
} from "@/components/analysisPreview";
import type { AppIconName } from "@/components/appIcons";
import { useVideoPlaybackSync } from "@/composables/useVideoPlaybackSync";
import type { ReviewState } from "@/types/case";
import { ref, watch } from "vue";

// 分析视图组件只接收已经整理好的展示数据，避免把 store 和业务副作用带进展示层。
export interface AnalysisKpiItem {
  label: string;
  value: string;
  icon: AppIconName;
}

const props = defineProps<{
  loading: boolean;
  error: string;
  hasCase: boolean;
  exportPath: string;
  exportLinks: Array<{ label: string; path: string; href: string }>;
  exportSummary: Record<string, unknown>;
  exportArtifactEntries: Array<{ kind: string; path: string; size_bytes?: number | null }>;
  activeAnalysisJobId: string;
  activeAnalysisJobStatus: string;
  activeAnalysisJobError: string;
  activeAnalysisJobProgress: Record<string, unknown>;
  lastAnalysisJobTimedOut: boolean;
  latestRunStatusLabel: string;
  analysisStatusClass: string;
  kpiItems: AnalysisKpiItem[];
  previewPanels: AnalysisPreviewPanel[];
  hotspotTimelineItems: HotspotTimelineItem[];
  hotspotTimelineTotalCount: number;
  hotspotTimelineFilter: HotspotTimelineFilter;
  selectedHotspotTimelineKey: string;
  selectedHotspotFrameDetail: HotspotFrameDetail | null;
  hotspotFrameDetails: HotspotFrameDetail[];
  timelineManifestSummary: TimelineManifestSummary | null;
  fusionEvidenceSummary: FusionEvidenceSummary | null;
  videoPlayback: VideoPlaybackAnalysis | null;
  cameraStream: MediaStream | null;
  cameraActive: boolean;
  cameraOpening: boolean;
  cameraStatusLabel: string;
  analysisExpanded: boolean;
}>();

const emit = defineEmits<{
  export: [];
  refreshJob: [];
  cancelJob: [];
  retryJob: [];
  reanalyzeHotspotFrame: [];
  generateBoneGateForFrame: [];
  saveBoneGateMaskEdit: [payload: { maskPngBase64: string; reviewState: ReviewState; reviewerNotes: string }];
  selectHotspotFrame: [key: string];
  updateHotspotTimelineFilter: [filter: HotspotTimelineFilter];
  startCamera: [];
  stopCamera: [];
  openFullscreen: [];
  closeFullscreen: [];
}>();

const {
  currentPlaybackTime,
  playbackDuration,
  playbackSeekTimeSec,
  playbackSeekToken,
  nearestFrameDetail: nearestPlaybackFrameDetail,
  syncPlaybackState,
  jumpPlaybackToDetail,
} = useVideoPlaybackSync({
  videoPlayback: () => props.videoPlayback,
  selectedFrameKey: () => props.selectedHotspotTimelineKey,
  onSelectFrame: (key) => emit("selectHotspotFrame", key),
});

const maskEditorOpen = ref(false);

watch(
  () => props.selectedHotspotFrameDetail?.key,
  () => {
    maskEditorOpen.value = false;
  },
);

</script>

<style scoped>
.analysis-card {
  position: relative;
  min-width: 0;
  border: 1px solid #d6e0eb;
  border-radius: 6px;
  padding: 14px 16px 16px;
  background: #ffffff;
  box-shadow: 0 2px 12px rgba(39, 74, 106, 0.06);
}

.analysis-header,
.fullscreen-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
}

.analysis-header {
  align-items: flex-start;
  margin-bottom: 10px;
}

.fullscreen-header {
  align-items: center;
}

.analysis-title-block {
  display: grid;
  flex-wrap: wrap;
  gap: 8px 14px;
  min-width: 0;
}

.analysis-header h2,
.fullscreen-header h2 {
  margin: 0;
  color: #102136;
  line-height: 1.25;
}

.analysis-header h2 {
  font-size: 21px;
}

.fullscreen-header h2 {
  font-size: 20px;
}

.analysis-header-actions {
  display: inline-flex;
  flex: 0 0 auto;
  flex-wrap: wrap;
  gap: 7px;
  align-items: center;
  justify-content: flex-end;
  min-width: 0;
}

.analysis-summary-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
  margin: 0;
}

.summary-chip {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  max-width: 100%;
  min-height: 26px;
  border: 1px solid #d3e2f1;
  border-radius: 999px;
  padding: 3px 8px;
  background: linear-gradient(180deg, #ffffff, #f4f9ff);
  color: #4d6780;
  font-size: 12px;
  font-weight: 800;
}

.summary-chip :deep(.app-icon) {
  width: 14px;
  height: 14px;
  color: #2c7ec0;
}

.summary-chip span {
  min-width: 0;
  overflow-wrap: anywhere;
  white-space: normal;
}

.summary-chip strong {
  min-width: 0;
  color: #102136;
  font-size: 12px;
  overflow-wrap: anywhere;
  white-space: normal;
}

.header-export-button {
  min-width: 106px;
}

.run-pill {
  flex: 0 0 auto;
  border-radius: 999px;
  padding: 5px 10px;
  background: #eef4ff;
  color: #1262d8;
  font-size: 12px;
  font-weight: 800;
}

.run-pill.failed {
  background: #fff4f1;
  color: #a23b25;
}

.run-pill.running {
  background: #fffaf0;
  color: #bd650c;
}

.run-pill.idle {
  background: #f2f6fb;
  color: #5a6a7a;
}

.state-message {
  margin-bottom: 9px;
  border: 1px solid #d6e0eb;
  border-radius: 6px;
  padding: 7px 10px;
  background: #f8fbfe;
  color: #405060;
  font-size: 12px;
  line-height: 1.4;
}

.state-message.error {
  border-color: #e7b7ab;
  background: #fff4f1;
  color: #a23b25;
}

.state-message.muted {
  color: #6a7a8a;
}

.analysis-fullscreen {
  position: fixed;
  z-index: 80;
  inset: 0;
  display: block;
  width: 100dvw;
  height: 100dvh;
  overflow: hidden;
  padding: 0;
  background: #eef6fd;
}

.analysis-fullscreen-panel {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 12px;
  width: 100%;
  height: 100%;
  max-width: none;
  max-height: none;
  overflow: hidden;
  border: 0;
  border-radius: 0;
  padding: 14px 16px 16px;
  background: linear-gradient(180deg, #ffffff, #f4f9ff);
  box-shadow: none;
}

.hotspot-timeline {
  display: grid;
  gap: 8px;
  margin-top: 10px;
  border: 1px solid #d6e4f2;
  border-radius: 6px;
  padding: 9px 10px;
  background: #f8fbfe;
}

.hotspot-timeline header {
  display: flex;
  gap: 7px;
  align-items: center;
  color: #102136;
  font-size: 13px;
}

.hotspot-timeline header :deep(.app-icon) {
  width: 15px;
  height: 15px;
  color: #2c7ec0;
}

.hotspot-timeline header span {
  margin-left: auto;
  color: #5a6a7a;
  font-size: 12px;
  font-weight: 800;
}

.hotspot-filter-group {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.hotspot-filter-group button {
  min-height: 28px;
  border: 1px solid #c9dae8;
  border-radius: 999px;
  padding: 4px 10px;
  background: #ffffff;
  color: #426078;
  font: inherit;
  font-size: 12px;
  font-weight: 850;
  cursor: pointer;
}

.hotspot-filter-group button.selected {
  border-color: #1c75b7;
  background: #eaf5ff;
  color: #145d91;
}

.hotspot-filter-group button:focus-visible {
  outline: 2px solid rgba(44, 126, 192, 0.52);
  outline-offset: 2px;
}

.timeline-manifest-panel {
  display: grid;
  gap: 8px;
  border: 1px solid #dbe8f4;
  border-radius: 6px;
  padding: 8px 9px;
  background: #ffffff;
}

.timeline-manifest-panel header,
.timeline-manifest-panel header div {
  display: flex;
  gap: 7px;
  align-items: center;
  min-width: 0;
}

.timeline-manifest-panel header {
  justify-content: space-between;
}

.timeline-manifest-panel header a {
  flex: 0 0 auto;
  border: 1px solid #c9dae8;
  border-radius: 999px;
  padding: 3px 8px;
  background: #f8fbfe;
  color: #145d91;
  font-size: 11px;
  font-weight: 900;
  text-decoration: none;
}

.timeline-summary-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 7px;
  margin: 0;
}

.timeline-summary-grid div {
  min-width: 0;
  border: 1px solid #e0e8f1;
  border-radius: 5px;
  padding: 5px 7px;
  background: #f8fbfe;
}

.timeline-summary-grid dt,
.timeline-summary-grid dd {
  margin: 0;
  min-width: 0;
  overflow-wrap: anywhere;
  white-space: normal;
}

.timeline-summary-grid dt {
  color: #748494;
  font-size: 10px;
  font-weight: 900;
}

.timeline-summary-grid dd {
  color: #102136;
  font-size: 12px;
  font-weight: 900;
}

.timeline-trace-list {
  display: grid;
  gap: 5px;
  min-width: 0;
}

.timeline-trace-list > strong {
  color: #2f638a;
  font-size: 12px;
}

.timeline-trace-list.duplicate > strong {
  color: #8a5b1f;
}

.timeline-trace-list ul {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 5px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.timeline-trace-list li {
  display: grid;
  gap: 2px;
  min-width: 0;
  border: 1px solid #e0e8f1;
  border-radius: 5px;
  padding: 5px 7px;
  background: #fbfdff;
}

.timeline-trace-list span,
.timeline-trace-list small {
  min-width: 0;
  overflow-wrap: anywhere;
  white-space: normal;
}

.timeline-trace-list span {
  color: #102136;
  font-size: 11px;
  font-weight: 900;
}

.timeline-trace-list small {
  color: #5a6a7a;
  font-size: 10px;
  font-weight: 800;
}

.hotspot-timeline-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.hotspot-timeline-item {
  position: relative;
  display: grid;
  grid-template-columns: 78px minmax(0, 1fr);
  gap: 8px;
  overflow: hidden;
  border: 1px solid #dbe8f4;
  border-radius: 6px;
  padding: 7px;
  background: #ffffff;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition:
    border-color 140ms ease,
    box-shadow 140ms ease,
    transform 140ms ease;
}

.hotspot-timeline-item:hover {
  transform: translateY(-1px);
  border-color: #2c7ec0;
  box-shadow: 0 8px 18px rgba(20, 86, 138, 0.12);
}

.hotspot-timeline-item.selected {
  border-color: #1c75b7;
  background: #f0f8ff;
  box-shadow:
    0 0 0 1px rgba(28, 117, 183, 0.18) inset,
    0 8px 20px rgba(20, 86, 138, 0.12);
}

.hotspot-timeline-item:focus-visible {
  outline: 2px solid rgba(44, 126, 192, 0.52);
  outline-offset: 2px;
}

.hotspot-timeline-item img {
  width: 78px;
  height: 62px;
  border-radius: 4px;
  object-fit: cover;
  background: #0f1720;
}

.hotspot-timeline-copy {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.hotspot-timeline-copy strong,
.hotspot-timeline-copy span {
  min-width: 0;
  overflow-wrap: anywhere;
  white-space: normal;
}

.hotspot-timeline-copy strong {
  color: #102136;
  font-size: 12px;
}

.hotspot-timeline-copy span {
  color: #5a6a7a;
  font-size: 11px;
  font-weight: 800;
}

.hotspot-timeline-copy dl {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 5px;
  margin: 0;
}

.hotspot-timeline-copy dt,
.hotspot-timeline-copy dd {
  margin: 0;
  overflow-wrap: anywhere;
  white-space: normal;
}

.hotspot-timeline-copy dt {
  color: #748494;
  font-size: 10px;
  font-weight: 900;
}

.hotspot-timeline-copy dd {
  color: #102136;
  font-size: 11px;
  font-weight: 900;
}

.hotspot-score-bar {
  position: absolute;
  right: 7px;
  bottom: 5px;
  left: 93px;
  height: 4px;
  overflow: hidden;
  border-radius: 999px;
  background: #dbe8f4;
}

.hotspot-score-bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #2c7ec0, #35a26b);
}

.hotspot-frame-detail {
  display: grid;
  gap: 8px;
  border: 1px solid #dbe8f4;
  border-radius: 6px;
  padding: 8px 9px;
  background: #ffffff;
}

.hotspot-frame-detail header,
.hotspot-frame-detail header div,
.hotspot-frame-actions {
  display: flex;
  gap: 7px;
  align-items: center;
  min-width: 0;
}

.hotspot-frame-detail header {
  justify-content: space-between;
}

.hotspot-frame-actions {
  justify-content: flex-end;
  flex-wrap: wrap;
}

.hotspot-frame-actions span {
  color: #5a6a7a;
  font-size: 12px;
  font-weight: 850;
}

.hotspot-frame-detail dl {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 7px;
  margin: 0;
}

.hotspot-frame-detail dt,
.hotspot-frame-detail dd {
  margin: 0;
  min-width: 0;
  overflow-wrap: anywhere;
}

.hotspot-frame-detail dt {
  color: #748494;
  font-size: 10px;
  font-weight: 900;
}

.hotspot-frame-detail dd {
  color: #102136;
  font-size: 12px;
  font-weight: 900;
}

.hotspot-frame-links {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  min-width: 0;
}

.hotspot-frame-links a {
  border: 1px solid #c9dae8;
  border-radius: 999px;
  padding: 3px 8px;
  background: #f8fbfe;
  color: #145d91;
  font-size: 11px;
  font-weight: 900;
  text-decoration: none;
}

.hotspot-frame-links span {
  min-width: 0;
  color: #5a6a7a;
  font-size: 11px;
  font-weight: 800;
  overflow-wrap: anywhere;
  white-space: normal;
}

.hotspot-frame-detail p {
  margin: 0;
  color: #5a6a7a;
  font-size: 11px;
  line-height: 1.45;
}

.hotspot-frame-drawer {
  border: 1px solid #dbe8f4;
  border-radius: 6px;
  background: #ffffff;
}

.hotspot-frame-drawer summary {
  display: flex;
  cursor: pointer;
  list-style: none;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 9px;
  color: #102136;
  font-size: 12px;
  font-weight: 900;
}

.hotspot-frame-drawer summary::-webkit-details-marker {
  display: none;
}

.hotspot-frame-drawer summary strong {
  color: #5a6a7a;
  font-size: 11px;
}

.hotspot-frame-table {
  display: grid;
  gap: 6px;
  max-height: 310px;
  overflow: auto;
  border-top: 1px solid #e4edf6;
  padding: 8px;
}

.hotspot-frame-row {
  display: grid;
  grid-template-columns: minmax(86px, 1.2fr) repeat(4, minmax(68px, 1fr)) minmax(58px, 0.55fr);
  align-items: center;
  gap: 8px;
  width: 100%;
  min-width: 0;
  border: 1px solid #edf3f8;
  border-radius: 6px;
  padding: 7px 8px;
  background: #f9fcff;
  color: inherit;
  text-align: left;
}

.hotspot-frame-row:hover,
.hotspot-frame-row.selected {
  border-color: #8bb9da;
  background: #eef7ff;
}

.hotspot-frame-row:focus-visible {
  outline: 2px solid #2c7ec0;
  outline-offset: 2px;
}

.hotspot-frame-row span {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.hotspot-frame-row small,
.hotspot-frame-row strong {
  min-width: 0;
  overflow-wrap: anywhere;
}

.hotspot-frame-row small {
  color: #748494;
  font-size: 10px;
  font-weight: 850;
}

.hotspot-frame-row strong {
  color: #102136;
  font-size: 11px;
  font-weight: 900;
}

.frame-row-main strong {
  font-size: 12px;
}

.frame-row-status {
  justify-self: end;
  border: 1px solid #c9dae8;
  border-radius: 999px;
  padding: 4px 8px;
  background: #ffffff;
  color: #5a6a7a;
  font-size: 11px;
  font-weight: 900;
  text-align: center;
  overflow-wrap: anywhere;
  white-space: normal;
}

.frame-row-status.review {
  border-color: #f0c27a;
  background: #fff8ea;
  color: #8a560b;
}

.hotspot-empty-state {
  margin: 0;
  border: 1px dashed #cbd9e7;
  border-radius: 6px;
  padding: 9px 10px;
  background: #ffffff;
  color: #5a6a7a;
  font-size: 12px;
}

@media (max-width: 1180px) {
  .analysis-header,
  .fullscreen-header {
    align-items: flex-start;
    grid-template-columns: 1fr;
  }

  .analysis-title-block {
    display: grid;
    gap: 10px;
  }

  .analysis-header-actions {
    justify-content: flex-start;
  }
}

@media (max-width: 959px) {

  .analysis-fullscreen-panel {
    padding: 12px;
  }

  .hotspot-timeline-list {
    grid-template-columns: 1fr;
  }

  .hotspot-frame-detail dl {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .hotspot-frame-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .frame-row-status {
    justify-self: start;
  }

  .timeline-summary-grid,
  .timeline-trace-list ul {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
