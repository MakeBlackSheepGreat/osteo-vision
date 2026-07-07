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
  padding: 20px;
  background:
    radial-gradient(circle at 12% 8%, rgba(34, 211, 238, 0.16), transparent 28%),
    radial-gradient(circle at 88% 18%, rgba(52, 211, 153, 0.1), transparent 26%),
    linear-gradient(180deg, #06111f 0%, #081724 44%, #050b13 100%);
  color: #e6f3ff;
}

.page-header,
.report-grid,
.artifact-preview {
  max-width: 1180px;
  margin-right: auto;
  margin-left: auto;
}

.page-header {
  margin-bottom: 14px;
}

.report-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(300px, 0.72fr);
  gap: 14px;
}

.report-panel {
  padding: 16px;
}

.ov-card {
  border: 1px solid rgba(91, 176, 214, 0.24);
  background:
    linear-gradient(180deg, rgba(15, 33, 51, 0.94), rgba(8, 20, 33, 0.96)),
    rgba(8, 20, 33, 0.96);
  box-shadow: 0 18px 42px rgba(0, 0, 0, 0.3);
}

.report-panel p {
  margin: 0;
  color: rgba(216, 232, 244, 0.78);
  line-height: 1.7;
}

dl {
  display: grid;
  gap: 12px;
  margin: 0;
}

dt {
  color: rgba(176, 207, 229, 0.72);
  font-size: 12px;
}

dd {
  margin: 3px 0 0;
  color: #eef8ff;
  overflow-wrap: anywhere;
}

.artifact-preview {
  margin-top: 14px;
  padding: 16px;
}

.artifact-list {
  display: grid;
  gap: 9px;
}

.artifact-card {
  min-width: 0;
  border: 1px solid rgba(91, 176, 214, 0.2);
  border-radius: var(--ov-radius);
  padding: 11px 12px;
  background: rgba(3, 12, 23, 0.62);
}

.empty-export-preview {
  display: grid;
  gap: 6px;
  place-items: center;
  min-height: 170px;
  border: 1px dashed rgba(91, 176, 214, 0.34);
  border-radius: var(--ov-radius);
  background:
    radial-gradient(circle at 50% 42%, rgba(34, 211, 238, 0.13), transparent 34%),
    rgba(3, 12, 23, 0.56);
  text-align: center;
}

.artifact-card strong,
.artifact-card span {
  display: block;
}

.artifact-card strong {
  color: #eef8ff;
}

.artifact-card span,
.empty-export-preview span {
  margin-top: 4px;
  color: rgba(176, 207, 229, 0.72);
  font-size: 12px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.empty-export-preview strong {
  color: #67e8f9;
}

:deep(.section-heading__eyebrow) {
  color: rgba(176, 207, 229, 0.72);
}

:deep(.section-heading h2),
:deep(.section-heading__title) {
  color: #eef8ff;
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
