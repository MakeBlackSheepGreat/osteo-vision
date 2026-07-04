<template>
  <div :class="gridClass" aria-label="四宫格图像展示">
    <article class="analysis-quad-card analysis-quad-card--camera">
      <header>
        <AppIcon name="camera" />
        <span>摄像头输入</span>
        <strong :class="{ active: cameraActive }">{{ cameraActive ? "LIVE" : "未连接" }}</strong>
      </header>
      <div class="analysis-quad-viewport camera-viewport" :class="{ active: cameraActive }">
        <video ref="cameraVideoRef" muted autoplay playsinline></video>
        <div v-if="!cameraActive" class="empty-preview-copy">
          <strong>实时预览区</strong>
          <span>{{ cameraStatusLabel }}</span>
        </div>
      </div>
      <p>{{ cameraStatusLabel }}</p>
    </article>

    <article v-for="panel in panels" :key="panel.title" class="analysis-quad-card">
      <header>
        <AppIcon :name="panelIcon(panel.title)" />
        <span>{{ panel.title }}</span>
      </header>
      <div class="analysis-quad-viewport output-viewport" :class="{ 'has-image': panel.previewSrc }">
        <img v-if="panel.previewSrc" :src="panel.previewSrc" :alt="panel.title" />
        <svg
          v-if="panel.previewSrc && panel.overlays?.length"
          class="preview-overlay"
          viewBox="0 0 1 1"
          preserveAspectRatio="none"
          aria-label="ROI 与候选区叠加"
        >
          <rect
            v-for="overlay in panel.overlays"
            :key="overlay.key"
            :class="['preview-overlay-rect', `preview-overlay-rect--${overlay.tone}`]"
            :x="overlay.x"
            :y="overlay.y"
            :width="overlay.width"
            :height="overlay.height"
            vector-effect="non-scaling-stroke"
          >
            <title>{{ overlay.label }}</title>
          </rect>
        </svg>
        <div v-if="!panel.previewSrc" class="empty-preview-copy">
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
import { computed, nextTick, ref, watch } from "vue";

import AppIcon from "@/components/AppIcon.vue";
import type { AnalysisPreviewPanel } from "@/components/analysisPreview";
import type { AppIconName } from "@/components/appIcons";

const props = withDefaults(
  defineProps<{
    panels: AnalysisPreviewPanel[];
    cameraStream: MediaStream | null;
    cameraActive: boolean;
    cameraStatusLabel: string;
    fullscreen?: boolean;
  }>(),
  {
    fullscreen: false,
  },
);

const cameraVideoRef = ref<HTMLVideoElement | null>(null);
const gridClass = computed(() => [
  "analysis-quad-grid",
  {
    "analysis-quad-grid--fullscreen": props.fullscreen,
  },
]);

watch(
  () => props.cameraStream,
  async (stream) => {
    await nextTick();
    if (!cameraVideoRef.value) return;
    cameraVideoRef.value.srcObject = stream;
    if (stream) {
      await cameraVideoRef.value.play().catch(() => undefined);
    }
  },
  { immediate: true },
);

function panelIcon(title: string): AppIconName {
  if (title.startsWith("关键帧")) return "video";
  const icons: Record<string, AppIconName> = {
    融合图: "layers",
    热图: "target",
    分割叠加: "target",
    分割掩膜: "document",
    归一化图: "document",
  };
  return icons[title] ?? "file";
}
</script>

<style scoped>
.analysis-quad-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 9px;
  min-width: 0;
}

.analysis-quad-card {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  min-width: 0;
  border: 1px solid #d4e2f0;
  border-radius: 6px;
  padding: 8px;
  background: #fbfdff;
}

.analysis-quad-card header {
  display: flex;
  gap: 7px;
  align-items: center;
  margin-bottom: 6px;
  color: #102136;
  font-size: 13px;
  font-weight: 900;
}

.analysis-quad-card header :deep(.app-icon) {
  width: 15px;
  height: 15px;
  color: #2c7ec0;
}

.analysis-quad-card header strong {
  margin-left: auto;
  border: 1px solid #d6e0eb;
  border-radius: 999px;
  padding: 2px 7px;
  background: #f2f6fb;
  color: #6a7a8a;
  font-size: 10px;
  line-height: 1.4;
}

.analysis-quad-card header strong.active {
  border-color: #a8dec8;
  background: #eefaf5;
  color: #168a63;
}

.analysis-quad-viewport {
  position: relative;
  display: grid;
  place-items: center;
  min-height: clamp(205px, 17vw, 285px);
  overflow: hidden;
  border: 1px solid #cbd8e6;
  border-radius: 4px;
  background:
    linear-gradient(90deg, rgba(44, 126, 192, 0.08) 1px, transparent 1px),
    linear-gradient(180deg, rgba(44, 126, 192, 0.08) 1px, transparent 1px),
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(241, 248, 254, 0.98));
  background-size: 24px 24px, 24px 24px, auto;
  isolation: isolate;
}

.analysis-quad-viewport::before {
  position: absolute;
  inset: 14px;
  border: 1px dashed rgba(44, 126, 192, 0.2);
  border-radius: 5px;
  content: "";
  pointer-events: none;
}

.analysis-quad-viewport::after {
  position: absolute;
  inset: 0;
  border: 1px solid rgba(255, 255, 255, 0.72);
  content: "";
  pointer-events: none;
}

.camera-viewport {
  background:
    linear-gradient(90deg, rgba(17, 108, 166, 0.1) 1px, transparent 1px),
    linear-gradient(180deg, rgba(17, 108, 166, 0.1) 1px, transparent 1px),
    linear-gradient(145deg, #dff1fd, #c1e0f5);
  background-size: 24px 24px, 24px 24px, auto;
}

.camera-viewport video {
  width: 100%;
  height: 100%;
  min-height: inherit;
  object-fit: cover;
  opacity: 0;
}

.camera-viewport.active video {
  opacity: 1;
}

.output-viewport.has-image {
  background: #0f1720;
}

.output-viewport img {
  position: relative;
  z-index: 3;
  width: 100%;
  height: 100%;
  min-height: inherit;
  object-fit: contain;
}

.preview-overlay {
  position: absolute;
  z-index: 4;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.preview-overlay-rect {
  fill: rgba(228, 155, 63, 0.1);
  stroke-width: 2;
}

.preview-overlay-rect--candidate {
  stroke: #e49b3f;
}

.preview-overlay-rect--roi {
  fill: rgba(44, 126, 192, 0.1);
  stroke: #2c7ec0;
  stroke-dasharray: 7 5;
}

.empty-preview-copy {
  position: relative;
  z-index: 4;
  display: grid;
  gap: 4px;
  justify-items: center;
  max-width: min(78%, 280px);
  border: 1px solid rgba(44, 126, 192, 0.28);
  border-radius: 8px;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.82);
  color: #4d6780;
  text-align: center;
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
  line-height: 1.35;
}

.analysis-quad-card p {
  margin: 5px 0 0;
  color: #5a6a7a;
  font-size: 12px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.analysis-quad-grid--fullscreen {
  height: 100%;
  min-height: 0;
}

.analysis-quad-grid--fullscreen .analysis-quad-card {
  min-height: 0;
}

.analysis-quad-grid--fullscreen .analysis-quad-viewport {
  height: 100%;
  min-height: 0;
}

.analysis-quad-grid--fullscreen .analysis-quad-card p {
  display: none;
}

@media (max-width: 1120px) {
  .analysis-quad-grid:not(.analysis-quad-grid--fullscreen) {
    grid-template-columns: 1fr;
  }

  .analysis-quad-grid:not(.analysis-quad-grid--fullscreen) .analysis-quad-viewport {
    min-height: 220px;
  }
}

@media (max-width: 680px) {
  .analysis-quad-grid--fullscreen {
    grid-template-columns: 1fr;
    overflow: auto;
  }

  .analysis-quad-grid--fullscreen .analysis-quad-card {
    min-height: 300px;
  }

  .analysis-quad-grid--fullscreen .analysis-quad-viewport {
    min-height: 240px;
  }
}
</style>
