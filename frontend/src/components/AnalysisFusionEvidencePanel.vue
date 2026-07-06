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
        <figcaption>阈值 {{ summary.thresholdLabel }} · Alpha {{ summary.alphaLabel }}</figcaption>
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
  border: 1px solid #d4e2f0;
  border-radius: 6px;
  padding: 9px 10px;
  background: #fbfdff;
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
  color: #102136;
  font-size: 13px;
  font-weight: 900;
}

.fusion-evidence-panel header :deep(.app-icon) {
  width: 15px;
  height: 15px;
  color: #2c7ec0;
}

.fusion-evidence-panel header > span {
  flex: 0 0 auto;
  border: 1px solid #d3e2f1;
  border-radius: 999px;
  padding: 3px 8px;
  background: #f2f7fc;
  color: #4d6780;
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
  border: 1px solid #dbe8f4;
  border-radius: 5px;
  padding: 7px;
  background: #ffffff;
}

.fusion-colorbar img {
  width: 100%;
  height: 32px;
  object-fit: fill;
  border-radius: 3px;
  background: #0f1720;
}

.fusion-colorbar figcaption {
  color: #5a6a7a;
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
  border: 1px solid #dbe8f4;
  border-radius: 5px;
  padding: 6px 7px;
  background: #ffffff;
}

.fusion-evidence-grid dt,
.fusion-evidence-grid dd {
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fusion-evidence-grid dt {
  color: #6a7a8a;
  font-size: 10px;
  font-weight: 800;
}

.fusion-evidence-grid dd {
  margin-top: 2px;
  color: #102136;
  font-size: 12px;
  font-weight: 900;
}

.fusion-colorbar-link {
  justify-self: start;
  color: #1f5f93;
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
