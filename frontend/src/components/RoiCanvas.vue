<template>
  <section class="roi-panel ov-card">
    <SectionHeading icon="target" eyebrow="ROI 复核" :title="regionLabel ?? '术中 ROI'" />
    <div class="canvas-placeholder" :class="{ empty: !hasOutput }" aria-label="ROI 复核画布占位">
      <template v-if="hasOutput">
        <div class="grid-lines"></div>
        <div class="tissue-field"></div>
        <div class="fluorescence-zone zone-primary"></div>
        <div class="fluorescence-zone zone-secondary"></div>
        <div class="roi-box"></div>
        <div class="manual-contour"></div>
        <div class="crosshair horizontal"></div>
        <div class="crosshair vertical"></div>
        <div class="canvas-label">影像与标注画布</div>
        <div class="canvas-meta top-left">WL + ICG / ROI-01</div>
        <div class="canvas-meta bottom-right">窗宽 0.82 / 阈值 0.60</div>
      </template>
      <div v-else class="empty-canvas-copy">
        <strong>空白 ROI 画布</strong>
        <span>病例工作台运行分析后显示候选区域与医生标注。</span>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import SectionHeading from "@/components/SectionHeading.vue";

withDefaults(defineProps<{ regionLabel?: string; hasOutput?: boolean }>(), {
  hasOutput: false,
});
</script>

<style scoped>
.roi-panel {
  padding: 14px;
}

.canvas-placeholder {
  position: relative;
  display: grid;
  place-items: center;
  min-height: 560px;
  overflow: hidden;
  border: 1px solid var(--ov-border-strong);
  border-radius: var(--ov-radius);
  background:
    radial-gradient(circle at 54% 52%, rgba(255, 255, 255, 0.64), rgba(139, 164, 184, 0.28) 34%, transparent 61%),
    linear-gradient(135deg, rgba(28, 84, 125, 0.08), transparent 48%),
    #eef3f8;
  color: var(--ov-text-secondary);
  font-weight: 700;
}

.canvas-placeholder.empty {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(244, 249, 255, 0.96)),
    #f8fbfe;
}

.canvas-placeholder.empty::before {
  position: absolute;
  inset: 18px;
  border: 1px dashed rgba(44, 126, 192, 0.22);
  border-radius: 8px;
  content: "";
}

.empty-canvas-copy {
  position: relative;
  z-index: 2;
  display: grid;
  gap: 6px;
  justify-items: center;
  border: 1px solid rgba(44, 126, 192, 0.22);
  border-radius: 8px;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: 0 8px 20px rgba(22, 76, 120, 0.08);
}

.empty-canvas-copy strong {
  color: var(--ov-primary);
  font-size: 14px;
}

.empty-canvas-copy span {
  color: var(--ov-text-muted);
  font-size: 12px;
}

.grid-lines {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(50, 60, 75, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(50, 60, 75, 0.08) 1px, transparent 1px);
  background-size: 34px 34px;
}

.tissue-field {
  position: absolute;
  left: 16%;
  top: 20%;
  width: 70%;
  height: 58%;
  border-radius: 45% 52% 42% 48%;
  background:
    radial-gradient(circle at 58% 46%, rgba(236, 226, 206, 0.48), transparent 30%),
    radial-gradient(circle at 38% 56%, rgba(177, 104, 88, 0.38), transparent 42%),
    linear-gradient(135deg, rgba(201, 140, 116, 0.32), rgba(45, 77, 96, 0.18));
  filter: blur(0.3px);
}

.fluorescence-zone {
  position: absolute;
  border-radius: 50%;
  mix-blend-mode: screen;
}

.zone-primary {
  left: 43%;
  top: 35%;
  width: 25%;
  height: 24%;
  background: radial-gradient(circle, rgba(102, 255, 130, 0.78), rgba(45, 160, 82, 0.36) 50%, transparent 72%);
}

.zone-secondary {
  left: 34%;
  top: 50%;
  width: 18%;
  height: 18%;
  background: radial-gradient(circle, rgba(160, 255, 178, 0.58), rgba(45, 160, 82, 0.26) 52%, transparent 72%);
}

.roi-box {
  position: absolute;
  width: min(48%, 360px);
  aspect-ratio: 1.35;
  border: 2px solid var(--ov-warning);
  border-radius: var(--ov-radius);
  background: color-mix(in srgb, var(--ov-warning) 10%, transparent);
}

.manual-contour {
  position: absolute;
  left: 42%;
  top: 34%;
  width: 28%;
  height: 28%;
  border: 2px dashed rgba(45, 120, 173, 0.82);
  border-radius: 47% 52% 42% 55%;
  transform: rotate(-8deg);
}

.crosshair {
  position: absolute;
  background: rgba(45, 120, 173, 0.22);
}

.crosshair.horizontal {
  left: 10%;
  right: 10%;
  top: 50%;
  height: 1px;
}

.crosshair.vertical {
  top: 10%;
  bottom: 10%;
  left: 50%;
  width: 1px;
}

.canvas-label,
.canvas-meta {
  position: absolute;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.82);
  color: #415362;
  font-size: 12px;
  font-weight: 800;
}

.canvas-label {
  padding: 7px 10px;
}

.canvas-meta {
  padding: 5px 7px;
}

.top-left {
  left: 12px;
  top: 12px;
}

.bottom-right {
  right: 12px;
  bottom: 12px;
}
</style>
