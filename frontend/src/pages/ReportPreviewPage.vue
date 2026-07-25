<template>
  <AppPageShell class="report-shell" width="standard">
    <AppPageHeader icon="report" title="病例证据包预览" class="page-header" />
    <AppFeedbackBanner v-if="store.error" class="report-feedback" tone="error" :message="store.error" />

    <section class="report-grid">
      <article class="report-panel ov-card">
        <SectionHeading icon="download" title="当前导出" />
        <AppMetricStrip :items="summaryItems" aria-label="当前证据包摘要" />
      </article>

      <article class="report-panel ov-card">
        <SectionHeading icon="alert" icon-tone="amber" title="输出边界" />
        <p>导出内容面向病例复核、过程记录和结果留档。报告中的候选区域、荧光统计和图像证据均需结合术中视野与医生判断。</p>
      </article>
    </section>

    <section class="artifact-preview ov-card" aria-label="导出文件清单">
      <SectionHeading icon="file" eyebrow="导出文件" title="文件清单" class="preview-heading" />
      <AppEvidenceArtifactList
        :artifacts="previewArtifacts"
        empty-text="请在病例工作台运行分析并导出证据包后查看文件清单。"
      />
    </section>
  </AppPageShell>
</template>

<script setup lang="ts">
import { computed, watch } from "vue";
import { useRoute } from "vue-router";

import AppEvidenceArtifactList from "@/components/AppEvidenceArtifactList.vue";
import AppFeedbackBanner from "@/components/AppFeedbackBanner.vue";
import AppMetricStrip from "@/components/AppMetricStrip.vue";
import AppPageHeader from "@/components/AppPageHeader.vue";
import AppPageShell from "@/components/AppPageShell.vue";
import SectionHeading from "@/components/SectionHeading.vue";
import { useCaseStore } from "@/stores/caseStore";
import { artifactLabel } from "@/utils/caseDisplay";

const store = useCaseStore();
const route = useRoute();

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
const summaryItems = computed(() => [
  { label: "病例 ID", value: displayCaseId.value, icon: "case" as const, breakable: true },
  { label: "证据包路径", value: displayExportPath.value, icon: "folder" as const, breakable: true },
  { label: "证据文件", value: displayArtifactCount.value, icon: "file" as const, tone: "info" as const },
]);

watch(
  () => route.query.caseId,
  async (value) => {
    const caseId = Array.isArray(value) ? value[0] : value;
    if (!caseId || typeof caseId !== "string" || store.currentCase?.case_id === caseId) return;
    await store.loadCase(caseId);
  },
  { immediate: true },
);
</script>

<style scoped>
.report-shell {
  min-height: calc(100dvh - 64px);
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

.artifact-preview {
  margin-top: 20px;
  padding: 20px;
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
