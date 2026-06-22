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
  border: 1px solid #d4e2f0;
  border-radius: 6px;
  padding: 9px;
  background: #fbfdff;
}

.analysis-preview-card header {
  display: flex;
  gap: 6px;
  align-items: center;
  justify-content: center;
  margin-bottom: 6px;
  color: #102136;
  font-size: 13px;
  font-weight: 900;
  text-align: center;
}

.analysis-preview-card header :deep(.app-icon) {
  width: 14px;
  height: 14px;
  color: #2c7ec0;
}

.analysis-preview-skeleton {
  position: relative;
  display: grid;
  place-items: center;
  min-height: clamp(260px, 22vw, 340px);
  overflow: hidden;
  border: 1px solid #cbd8e6;
  border-radius: 4px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.95), rgba(242, 248, 254, 0.96)),
    #f8fbfe;
  isolation: isolate;
}

.analysis-preview-skeleton::before {
  position: absolute;
  inset: 14px;
  border: 1px dashed rgba(44, 126, 192, 0.22);
  border-radius: 5px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.58), rgba(239, 247, 254, 0.42));
  content: "";
}

.analysis-preview-skeleton::after {
  position: absolute;
  inset: 0;
  border: 1px solid rgba(255, 255, 255, 0.72);
  content: "";
  pointer-events: none;
}

.empty-preview-copy {
  position: relative;
  z-index: 4;
  display: grid;
  gap: 4px;
  justify-items: center;
  border: 1px solid rgba(44, 126, 192, 0.28);
  border-radius: 8px;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.82);
  color: #4d6780;
  box-shadow: 0 8px 20px rgba(22, 76, 120, 0.08);
}

.empty-preview-copy strong {
  color: #155f96;
  font-size: 12px;
  line-height: 1.2;
}

.empty-preview-copy span {
  color: #6c8299;
  font-size: 11px;
  font-weight: 800;
}

.analysis-preview-card p {
  margin: 6px 0 0;
  color: #5a6a7a;
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
  background: #f7fbff;
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
