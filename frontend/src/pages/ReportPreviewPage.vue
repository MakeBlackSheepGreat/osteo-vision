<template>
  <main class="report-shell">
    <AppPageHeader title="病例证据包预览" class="page-header" />

    <section class="report-grid">
      <article class="report-panel ov-card">
        <SectionHeading icon="download" title="当前导出" />
        <dl>
          <div>
            <dt>病例 ID</dt>
            <dd>{{ displayCaseId }}</dd>
          </div>
          <div>
            <dt>证据包路径</dt>
            <dd>{{ displayExportPath }}</dd>
          </div>
          <div>
            <dt>证据文件数量</dt>
            <dd>{{ displayArtifactCount }}</dd>
          </div>
        </dl>
      </article>

      <article class="report-panel ov-card">
        <SectionHeading icon="alert" icon-tone="amber" title="输出边界" />
        <p>导出内容面向病例复核、过程记录和结果留档。报告中的候选区域、荧光统计和图像证据均需结合术中视野与医生判断。</p>
      </article>
    </section>

    <section class="artifact-preview ov-card" aria-label="导出文件清单">
      <SectionHeading icon="file" eyebrow="导出文件" title="文件清单" class="preview-heading" />
      <div v-if="previewArtifacts.length" class="artifact-list">
        <article v-for="artifact in previewArtifacts" :key="artifact.id" class="artifact-card">
          <div>
            <strong>{{ artifact.label }}</strong>
            <span>{{ artifact.path }}</span>
          </div>
        </article>
      </div>
      <div v-else class="empty-export-preview">
        <strong>暂无导出内容</strong>
        <span>请在病例工作台运行分析并导出证据包后查看文件清单。</span>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed } from "vue";

import AppPageHeader from "@/components/AppPageHeader.vue";
import SectionHeading from "@/components/SectionHeading.vue";
import { useCaseStore } from "@/stores/caseStore";
import { artifactLabel } from "@/utils/caseDisplay";

const store = useCaseStore();

const displayCaseId = computed(() => store.currentCase?.case_id ?? "未载入病例");
const displayExportPath = computed(() => store.exportPath || "暂无导出路径");
const previewArtifacts = computed(() =>
  (store.currentCase?.artifacts ?? []).map((artifact) => ({
    id: artifact.artifact_id,
    label: artifactLabel(artifact.kind),
    path: artifact.path,
  })),
);
const displayArtifactCount = computed(() => previewArtifacts.value.length);
</script>

<style scoped>
.report-shell {
  min-height: 100dvh;
  padding: var(--ov-page-top) var(--ov-page-inline) var(--ov-page-bottom);
  background: var(--ov-shell-background);
  color: var(--ov-text);
}

.page-header,
.report-grid,
.artifact-preview {
  max-width: 1360px;
  margin-right: auto;
  margin-left: auto;
}

.page-header {
  margin-bottom: 24px;
}

.report-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(300px, 0.72fr);
  gap: 20px;
}

.report-panel {
  padding: 20px;
}

.ov-card {
  border: 1px solid var(--ov-border);
  background: var(--ov-bg-elevated);
  box-shadow: var(--ov-shadow);
}

.report-panel p {
  margin: 0;
  color: var(--ov-text-secondary);
  line-height: 1.7;
}

dl {
  display: grid;
  gap: 12px;
  margin: 0;
}

dt {
  color: var(--ov-text-muted);
  font-size: 12px;
}

dd {
  margin: 3px 0 0;
  color: var(--ov-text);
  overflow-wrap: anywhere;
}

.artifact-preview {
  margin-top: 20px;
  padding: 20px;
}

.artifact-list {
  display: grid;
  gap: 12px;
}

.artifact-card {
  min-width: 0;
  border: 1px solid var(--ov-border-subtle);
  border-radius: var(--ov-radius);
  padding: 14px 16px;
  background: var(--ov-bg-soft);
}

.empty-export-preview {
  display: grid;
  gap: 6px;
  place-items: center;
  min-height: 170px;
  border: 1px dashed var(--ov-border-strong);
  border-radius: var(--ov-radius);
  background: var(--ov-bg-soft);
  text-align: center;
}

.artifact-card strong,
.artifact-card span {
  display: block;
}

.artifact-card strong {
  color: var(--ov-text);
}

.artifact-card span,
.empty-export-preview span {
  margin-top: 4px;
  color: var(--ov-text-muted);
  font-size: 12px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.empty-export-preview strong {
  color: var(--ov-primary-strong);
}

:deep(.section-heading__eyebrow) {
  color: var(--ov-text-muted);
}

:deep(.section-heading h2),
:deep(.section-heading__title) {
  color: var(--ov-text);
}

@media (max-width: 760px) {
  .report-shell {
    padding: 12px;
  }

  .report-grid {
    grid-template-columns: 1fr;
  }
}
</style>
