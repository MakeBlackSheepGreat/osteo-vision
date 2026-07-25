<template>
  <section class="fusion-evidence-panel" aria-label="荧光融合 V2 证据">
    <header>
      <div>
        <AppIcon name="layers" />
        <strong>荧光融合证据</strong>
      </div>
      <span>{{ summary.algorithmVersionLabel }}</span>
    </header>
    <div class="fusion-evidence-body">
      <figure v-if="summary.colorbarPreviewSrc" class="fusion-colorbar">
        <img :src="summary.colorbarPreviewSrc" alt="荧光色标" />
        <figcaption>阈值 {{ summary.thresholdLabel }} · 透明度 {{ summary.alphaLabel }}</figcaption>
      </figure>
      <dl class="fusion-evidence-grid">
        <div>
          <dt>融合方法</dt>
          <dd>{{ summary.methodLabel }}</dd>
        </div>
        <div>
          <dt>背景扣除</dt>
          <dd>{{ summary.backgroundLabel }}</dd>
        </div>
        <div>
          <dt>配准状态</dt>
          <dd>{{ summary.registrationLabel }}</dd>
        </div>
        <div>
          <dt>平移估计</dt>
          <dd>{{ summary.translationLabel }}</dd>
        </div>
        <div>
          <dt>配准响应</dt>
          <dd>{{ summary.responseLabel }}</dd>
        </div>
        <div>
          <dt>输入尺寸</dt>
          <dd>{{ summary.resizeLabel }}</dd>
        </div>
      </dl>
    </div>
    <a
      v-if="summary.colorbarPath"
      class="fusion-colorbar-link"
      :href="summary.colorbarPreviewSrc"
      target="_blank"
      rel="noreferrer"
    >
      查看色标文件
    </a>
  </section>
</template>

<script setup lang="ts">
import AppIcon from "@/components/AppIcon.vue";
import type { FusionEvidenceSummary } from "@/components/analysisPreview";

defineProps<{
  summary: FusionEvidenceSummary;
}>();
</script>

<style scoped>
.fusion-evidence-panel {
  display: grid;
  gap: 8px;
  margin: 10px 0 0;
  border: 1px solid var(--ov-border);
  border-radius: 6px;
  padding: 9px 10px;
  background: var(--ov-bg-soft);
}

.fusion-evidence-panel header {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
}

.fusion-evidence-panel header div {
  display: inline-flex;
  gap: 7px;
  align-items: center;
  min-width: 0;
  color: var(--ov-text);
  font-size: 13px;
  font-weight: 900;
}

.fusion-evidence-panel header :deep(.app-icon) {
  width: 15px;
  height: 15px;
  color: var(--ov-primary-strong);
}

.fusion-evidence-panel header > span {
  flex: 0 0 auto;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 999px;
  padding: 3px 8px;
  background: var(--ov-bg-panel);
  color: var(--ov-text-secondary);
  font-size: 11px;
  font-weight: 900;
}

.fusion-evidence-body {
  display: grid;
  grid-template-columns: 245px minmax(0, 1fr);
  gap: 9px;
  align-items: stretch;
}

.fusion-colorbar {
  display: grid;
  align-content: center;
  gap: 6px;
  min-width: 0;
  margin: 0;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 5px;
  padding: 7px;
  background: var(--ov-bg-elevated);
}

.fusion-colorbar img {
  width: 100%;
  height: 32px;
  object-fit: contain;
  border-radius: 3px;
  background: var(--ov-bg-media);
}

.fusion-colorbar figcaption {
  color: var(--ov-text-secondary);
  font-size: 11px;
  font-weight: 800;
  line-height: 1.35;
}

.fusion-evidence-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
  margin: 0;
}

.fusion-evidence-grid div {
  min-width: 0;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 5px;
  padding: 6px 7px;
  background: var(--ov-bg-elevated);
}

.fusion-evidence-grid dt,
.fusion-evidence-grid dd {
  margin: 0;
  overflow-wrap: anywhere;
  white-space: normal;
}

.fusion-evidence-grid dt {
  color: var(--ov-text-muted);
  font-size: 10px;
  font-weight: 800;
}

.fusion-evidence-grid dd {
  margin-top: 2px;
  color: var(--ov-text);
  font-size: 12px;
  font-weight: 900;
}

.fusion-colorbar-link {
  justify-self: start;
  color: var(--ov-primary);
  font-size: 12px;
  font-weight: 900;
  text-decoration: none;
}

@media (max-width: 959px) {
  .fusion-evidence-body {
    grid-template-columns: 1fr;
  }

  .fusion-evidence-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
