<template>
  <div :class="gridClass" aria-label="结果图预览">
    <article v-for="panel in panels" :key="panel.title" class="analysis-preview-card">
      <header>
        <AppIcon :name="panelIcon(panel.title)" />
        <span>{{ panel.title }}</span>
      </header>
      <div class="analysis-preview-skeleton">
        <div class="empty-preview-copy">
          <strong>空白预览区</strong>
          <span>运行分析后显示真实输出</span>
        </div>
      </div>
      <p v-if="panel.path">{{ panel.path }}</p>
      <p v-else>{{ panel.tag }} / {{ panel.label }} / {{ panel.scale }}</p>
    </article>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

import AppIcon from "@/components/AppIcon.vue";
import type { AnalysisPreviewPanel } from "@/components/analysisPreview";
import type { AppIconName } from "@/components/appIcons";

const props = withDefaults(
  defineProps<{
    panels: AnalysisPreviewPanel[];
    fullscreen?: boolean;
  }>(),
  {
    fullscreen: false,
  },
);

const gridClass = computed(() => [
  "analysis-preview-grid",
  {
    "analysis-preview-grid--fullscreen": props.fullscreen,
  },
]);

function panelIcon(title: string): AppIconName {
  const icons: Record<string, AppIconName> = {
    融合图: "layers",
    热图: "target",
    归一化图: "document",
  };
  return icons[title] ?? "file";
}
</script>

<style scoped>
.analysis-preview-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.analysis-preview-card {
  min-width: 0;
  border: 1px solid var(--ov-border);
  border-radius: 6px;
  padding: 9px;
  background: var(--ov-bg-elevated);
}

.analysis-preview-card header {
  display: flex;
  gap: 6px;
  align-items: center;
  justify-content: center;
  margin-bottom: 6px;
  color: var(--ov-text);
  font-size: 13px;
  font-weight: 900;
  text-align: center;
}

.analysis-preview-card header :deep(.app-icon) {
  width: 14px;
  height: 14px;
  color: var(--ov-primary-strong);
}

.analysis-preview-skeleton {
  position: relative;
  display: grid;
  place-items: center;
  min-height: clamp(260px, 22vw, 340px);
  overflow: hidden;
  border: 1px solid var(--ov-border-strong);
  border-radius: 4px;
  background: var(--ov-bg-panel);
  isolation: isolate;
}

.analysis-preview-skeleton::before {
  position: absolute;
  inset: 14px;
  border: 1px dashed var(--ov-border);
  border-radius: 5px;
  background: var(--ov-bg-soft);
  content: "";
}

.analysis-preview-skeleton::after {
  content: none;
}

.empty-preview-copy {
  position: relative;
  z-index: 4;
  display: grid;
  gap: 4px;
  justify-items: center;
  border: 1px solid var(--ov-border-accent);
  border-radius: 8px;
  padding: 10px 14px;
  background: var(--ov-bg-elevated);
  color: var(--ov-text-secondary);
  box-shadow: var(--ov-shadow);
}

.empty-preview-copy strong {
  color: var(--ov-primary);
  font-size: 12px;
  line-height: 1.2;
}

.empty-preview-copy span {
  color: var(--ov-text-muted);
  font-size: 11px;
  font-weight: 800;
}

.analysis-preview-card p {
  margin: 6px 0 0;
  color: var(--ov-text-secondary);
  font-size: 12px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.analysis-preview-grid--fullscreen {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  min-height: 0;
  height: 100%;
}

.analysis-preview-grid--fullscreen .analysis-preview-card {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  min-height: 0;
  border-style: solid;
  background: var(--ov-bg-elevated);
}

.analysis-preview-grid--fullscreen .analysis-preview-card p {
  display: none;
}

.analysis-preview-grid--fullscreen .analysis-preview-skeleton {
  height: 100%;
  min-height: 0;
}

@media (max-width: 1120px) {
  .analysis-preview-grid:not(.analysis-preview-grid--fullscreen) {
    grid-template-columns: 1fr;
  }

  .analysis-preview-grid:not(.analysis-preview-grid--fullscreen) .analysis-preview-skeleton {
    min-height: 260px;
  }
}

@media (max-width: 680px) {
  .analysis-preview-grid--fullscreen {
    grid-template-columns: 1fr;
    overflow: auto;
  }

  .analysis-preview-grid--fullscreen .analysis-preview-card {
    min-height: 300px;
  }

  .analysis-preview-grid--fullscreen .analysis-preview-skeleton {
    min-height: 240px;
  }
}
</style>
