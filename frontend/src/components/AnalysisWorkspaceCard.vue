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
    <p v-if="exportPath" class="export-path export-path--inline">证据包已导出：{{ exportPath }}</p>

    <AnalysisQuadGrid
      :panels="previewPanels"
      :camera-stream="cameraStream"
      :camera-active="cameraActive"
      :camera-status-label="cameraStatusLabel"
    />

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
        fullscreen
      />
    </div>
  </section>
</template>

<script setup lang="ts">
import AnalysisQuadGrid from "@/components/AnalysisQuadGrid.vue";
import AppButton from "@/components/AppButton.vue";
import AppIcon from "@/components/AppIcon.vue";
import type { AnalysisPreviewPanel } from "@/components/analysisPreview";
import type { AppIconName } from "@/components/appIcons";

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
  latestRunStatusLabel: string;
  analysisStatusClass: string;
  kpiItems: AnalysisKpiItem[];
  previewPanels: AnalysisPreviewPanel[];
  cameraStream: MediaStream | null;
  cameraActive: boolean;
  cameraStatusLabel: string;
  analysisExpanded: boolean;
}>();

const emit = defineEmits<{
  export: [];
  openFullscreen: [];
  closeFullscreen: [];
}>();
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
  display: flex;
  gap: 12px;
  justify-content: space-between;
}

.analysis-header {
  align-items: flex-start;
  margin-bottom: 10px;
}

.fullscreen-header {
  align-items: center;
}

.analysis-title-block {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  align-items: center;
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
  gap: 7px;
  align-items: center;
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

.summary-chip strong {
  color: #102136;
  font-size: 12px;
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

.export-path {
  margin: 10px 0 0;
  color: #5a6a7a;
  font-size: 12px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.export-path--inline {
  margin: 0 0 10px;
  border: 1px solid #cfe0ef;
  border-radius: 5px;
  padding: 8px 10px;
  background: #f6fbff;
  color: #2f638a;
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

@media (max-width: 959px) {
  .analysis-header,
  .fullscreen-header {
    align-items: flex-start;
  }

  .analysis-title-block {
    display: grid;
    gap: 10px;
  }

  .analysis-header-actions {
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .analysis-fullscreen-panel {
    padding: 12px;
  }
}
</style>
