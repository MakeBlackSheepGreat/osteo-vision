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
    <div v-if="artifactEntries.length" class="export-artifact-list">
      <strong>证据文件</strong>
      <ul>
        <li v-for="entry in artifactEntries.slice(0, 8)" :key="`${entry.kind}-${entry.path}`">
          <span>{{ artifactKindLabel(entry.kind) }}</span>
          <small>{{ formatBytes(entry.size_bytes) }}</small>
        </li>
      </ul>
    </div>
    <p class="export-path export-path--inline">{{ exportPath }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

import AppIcon from "@/components/AppIcon.vue";

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
    ["ZIP 大小", formatBytes(summary.bundle_size_bytes)],
    ["DICOM", summary.dicom_included === true ? "已包含" : "未包含"],
  ];
  return items
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .map(([label, value]) => ({ label: String(label), value: String(value) }));
});

function artifactKindLabel(kind: string): string {
  const labels: Record<string, string> = {
    report_json: "JSON 报告",
    report_md: "Markdown 报告",
    dicom_secondary_capture: "DICOM 二次捕获",
    quantification_csv: "量化 CSV",
    evidence_bundle: "证据包 ZIP",
    bundle_manifest: "Bundle Manifest",
    overlay: "融合图",
    video_overlay: "分割叠加视频",
    video_mask: "分割掩膜视频",
    video_segmentation_manifest: "MP4 分割 Manifest",
    probability_map: "概率图",
    heatmap: "热图",
    colorbar: "荧光色标",
    roi_mask: "ROI 掩膜",
  };
  return labels[kind] ?? kind;
}

function formatBytes(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "暂无";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(2)} MB`;
}
</script>

<style scoped>
.export-panel {
  display: grid;
  gap: 7px;
  margin: 0 0 10px;
  border: 1px solid #cfe0ef;
  border-radius: 6px;
  padding: 8px 10px;
  background: #f6fbff;
}

.export-panel-title {
  display: flex;
  gap: 7px;
  align-items: center;
  color: #2f638a;
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
  border: 1px solid #bad4ea;
  border-radius: 5px;
  padding: 4px 8px;
  background: #ffffff;
  color: #1f5f93;
  font-size: 12px;
  font-weight: 800;
  text-decoration: none;
}

.export-link strong {
  color: #102136;
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
  border: 1px solid #dbe8f4;
  border-radius: 5px;
  padding: 5px 7px;
  background: #ffffff;
}

.export-summary-grid dt,
.export-summary-grid dd {
  margin: 0;
  overflow-wrap: anywhere;
  white-space: normal;
}

.export-summary-grid dt {
  color: #6a7a8a;
  font-size: 10px;
  font-weight: 800;
}

.export-summary-grid dd {
  color: #102136;
  font-size: 12px;
  font-weight: 900;
}

.export-artifact-list {
  display: grid;
  gap: 5px;
}

.export-artifact-list > strong {
  color: #2f638a;
  font-size: 12px;
}

.export-artifact-list ul {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 5px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.export-artifact-list li {
  display: flex;
  gap: 6px;
  justify-content: space-between;
  min-width: 0;
  border: 1px solid #dbe8f4;
  border-radius: 5px;
  padding: 5px 7px;
  background: #ffffff;
}

.export-artifact-list span,
.export-artifact-list small {
  min-width: 0;
  color: #405060;
  font-size: 11px;
  overflow-wrap: anywhere;
  white-space: normal;
}

.export-artifact-list span {
  font-weight: 800;
}

.export-path {
  margin: 10px 0 0;
  color: #5a6a7a;
  font-size: 12px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.export-path--inline {
  margin: 0;
  color: #2f638a;
}
</style>
