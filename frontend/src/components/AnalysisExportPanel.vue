<template>
  <div class="export-panel">
    <div class="export-panel-title">
      <AppIcon name="download" />
      <strong>证据包已导出</strong>
    </div>
    <div v-if="exportLinks.length" class="export-link-list">
      <a
        v-for="link in exportLinks"
        :key="link.path"
        :href="link.href"
        class="export-link"
        target="_blank"
        rel="noreferrer"
      >
        <span>{{ link.label }}</span>
        <strong>下载</strong>
      </a>
    </div>
    <dl v-if="exportSummaryItems.length" class="export-summary-grid" aria-label="导出摘要">
      <div v-for="item in exportSummaryItems" :key="item.label">
        <dt>{{ item.label }}</dt>
        <dd>{{ item.value }}</dd>
      </div>
    </dl>
    <div v-if="artifactEntries.length" class="export-artifact-summary">
      <div>
        <strong>证据文件共 {{ artifactEntries.length }} 项</strong>
        <span>{{ artifactTypeSummary }}</span>
      </div>
      <a class="export-report-link" href="/report">查看完整文件清单</a>
    </div>
    <p class="export-path export-path--inline ov-breakable">{{ exportPath }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

import AppIcon from "@/components/AppIcon.vue";
import { artifactKindLabel, formatArtifactBytes } from "@/utils/artifactDisplay";

const props = defineProps<{
  exportPath: string;
  exportLinks: Array<{ label: string; path: string; href: string }>;
  exportSummary: Record<string, unknown>;
  artifactEntries: Array<{ kind: string; path: string; size_bytes?: number | null }>;
}>();

// 导出摘要属于报告展示细节，独立出来后主工作台不用关心字段命名和大小格式化。
const exportSummaryItems = computed(() => {
  const summary = props.exportSummary;
  const items = [
    ["分析次数", summary.analysis_run_count],
    ["候选区", summary.candidate_region_count],
    ["证据文件", summary.total_artifact_count],
    ["量化行", summary.quantification_row_count],
    ["ZIP 大小", formatArtifactBytes(summary.bundle_size_bytes)],
    ["DICOM", summary.dicom_included === true ? "已包含" : "未包含"],
  ];
  return items
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .map(([label, value]) => ({ label: String(label), value: String(value) }));
});

const artifactTypeSummary = computed(() =>
  Array.from(new Set(props.artifactEntries.map((entry) => artifactKindLabel(entry.kind)))).join("、"),
);
</script>

<style scoped>
.export-panel {
  display: grid;
  gap: 7px;
  margin: 0 0 10px;
  border: 1px solid var(--ov-border);
  border-radius: 6px;
  padding: 8px 10px;
  background: var(--ov-bg-soft);
}

.export-panel-title {
  display: flex;
  gap: 7px;
  align-items: center;
  color: var(--ov-primary);
  font-size: 12px;
}

.export-panel-title :deep(.app-icon) {
  width: 15px;
  height: 15px;
}

.export-link-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.export-link {
  display: inline-flex;
  gap: 7px;
  align-items: center;
  min-height: 28px;
  border: 1px solid var(--ov-border-strong);
  border-radius: 5px;
  padding: 4px 8px;
  background: var(--ov-bg-control);
  color: var(--ov-primary);
  font-size: 12px;
  font-weight: 800;
  text-decoration: none;
}

.export-link strong {
  color: var(--ov-text);
  font-size: 11px;
}

.export-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
  margin: 0;
}

.export-summary-grid div {
  min-width: 0;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 5px;
  padding: 5px 7px;
  background: var(--ov-bg-elevated);
}

.export-summary-grid dt,
.export-summary-grid dd {
  margin: 0;
  overflow-wrap: anywhere;
  white-space: normal;
}

.export-summary-grid dt {
  color: var(--ov-text-muted);
  font-size: 10px;
  font-weight: 800;
}

.export-summary-grid dd {
  color: var(--ov-text);
  font-size: 12px;
  font-weight: 900;
}

.export-artifact-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  align-items: center;
  justify-content: space-between;
  min-width: 0;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 5px;
  padding: 8px 9px;
  background: var(--ov-bg-elevated);
}

.export-artifact-summary > div {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.export-artifact-summary strong,
.export-artifact-summary span {
  min-width: 0;
  color: var(--ov-text-secondary);
  font-size: 12px;
  overflow-wrap: break-word;
  white-space: normal;
}

.export-artifact-summary strong {
  color: var(--ov-text);
  font-weight: 800;
}

.export-report-link {
  color: var(--ov-primary);
  font-size: 12px;
  font-weight: 800;
  line-height: 1.35;
}

.export-path {
  margin: 10px 0 0;
  color: var(--ov-text-secondary);
  font-size: 12px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.export-path--inline {
  margin: 0;
  color: var(--ov-primary);
}
</style>
