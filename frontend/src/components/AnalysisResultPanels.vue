<template>
  <section class="result-stack">
    <article class="result-card summary-card">
      <header class="compact-card-header">
        <SectionHeading icon="document" icon-tone="green" title="结果摘要" />
        <span>{{ candidateRows.length }} 项候选</span>
      </header>

      <div class="summary-subtitle">量化 / 荧光统计</div>
      <dl class="metric-grid">
        <div v-for="metric in metricRows" :key="metric.label">
          <dt>{{ metric.label }}</dt>
          <dd>{{ metric.value }}</dd>
        </div>
      </dl>

      <div class="summary-divider"></div>
      <div class="summary-subtitle">候选区域</div>
      <ul v-if="candidateRows.length" class="candidate-list">
        <li v-for="candidate in candidateRows" :key="candidate.id">
          <div class="candidate-body">
            <div class="candidate-topline">
              <strong>{{ candidate.title }}</strong>
              <span>{{ candidate.status }}</span>
            </div>
            <div class="candidate-meta">
              <p>候选编号: {{ candidate.shortId }}</p>
              <p>置信度: {{ candidate.confidence }}</p>
              <p>面积: {{ candidate.area }}</p>
              <p>P95 强度: {{ candidate.p95 }}</p>
            </div>
          </div>
        </li>
      </ul>
      <p v-else class="empty-inline">暂无候选区域，运行分析后会在这里显示待复核结果。</p>
    </article>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";

import SectionHeading from "@/components/SectionHeading.vue";
import type { CandidateRegion } from "@/types/case";
import { metricLabel, numberLabel, reviewStateLabel, riskLabel, valueLabel } from "@/utils/caseDisplay";

const props = defineProps<{
  candidates: CandidateRegion[];
  metrics: Record<string, unknown>;
}>();

const fluorescenceMetricKeys = ["mean_intensity", "p95_intensity", "positive_area_fraction", "threshold"];
const videoMetricKeys = [
  "hotspot_frame_count",
  "hotspot_candidate_count",
  "hotspot_max_positive_area_fraction",
  "hotspot_mean_positive_area_fraction",
];

const metricRows = computed(() =>
  selectedMetricKeys().map((key) => ({
    label: metricLabel(key),
    value: valueLabel(props.metrics[key]),
  })),
);

const candidateRows = computed(() =>
  props.candidates.map((candidate, index) => ({
    id: candidate.candidate_id,
    shortId: candidate.candidate_id.replace(/^cand_/, "R").slice(0, 8).toUpperCase() || `R0${index + 1}`,
    title: riskLabel(candidate.risk_type),
    status: reviewStateLabel(candidate.status),
    confidence: numberLabel(candidate.confidence),
    area: areaLabel(props.metrics, index, candidate.score),
    p95: p95Label(props.metrics, candidate.confidence),
  })),
);

function selectedMetricKeys(): string[] {
  if (videoMetricKeys.some((key) => key in props.metrics)) {
    return videoMetricKeys;
  }
  return fluorescenceMetricKeys;
}

function p95Label(metricMap: Record<string, unknown>, _fallback?: number | null): string {
  const value = metricMap.p95_intensity;
  if (typeof value === "number") return value.toFixed(2);
  return "暂无";
}

function areaLabel(metricMap: Record<string, unknown>, index: number, candidateScore?: number | null): string {
  if (typeof candidateScore === "number" && Number.isFinite(candidateScore) && candidateScore >= 0 && candidateScore <= 1) {
    return `${(candidateScore * 100).toFixed(2)}%`;
  }
  const hotspotFraction = metricMap.hotspot_max_positive_area_fraction;
  if (typeof hotspotFraction === "number") {
    return `${(Math.max(0, hotspotFraction - index * 0.004) * 100).toFixed(2)}%`;
  }
  const areaPx = metricMap.positive_area_px;
  if (typeof areaPx === "number") return `${Math.max(0, areaPx).toFixed(0)} px`;
  return "暂无";
}

</script>

<style scoped>
.result-stack {
  display: grid;
  grid-template-columns: 1fr;
}

.result-card {
  min-width: 0;
  border: 1px solid var(--ov-border);
  border-radius: 6px;
  padding: 8px 10px;
  background: var(--ov-bg-elevated);
  box-shadow: var(--ov-shadow);
}

.compact-card-header {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--ov-border-subtle);
}

.compact-card-header > span {
  flex: 0 0 auto;
  border-radius: 999px;
  padding: 3px 8px;
  background: var(--ov-bg-soft);
  color: var(--ov-text-secondary);
  font-size: 11px;
  font-weight: 900;
}

.compact-card-header :deep(.ov-section-heading) {
  min-width: 0;
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: 0;
}

.result-card :deep(.ov-section-heading__title) {
  color: var(--ov-text);
  font-size: 12px;
}

.result-card :deep(.ov-section-heading__eyebrow) {
  display: none;
}

.summary-subtitle {
  margin: 0 0 6px;
  color: var(--ov-primary);
  font-size: 11px;
  font-weight: 900;
}

.summary-divider {
  height: 1px;
  margin: 9px 0 8px;
  background: var(--ov-border-subtle);
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 5px;
  margin: 0;
}

.metric-grid div {
  min-width: 0;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 5px;
  padding: 6px 7px;
  background: var(--ov-bg-soft);
}

.metric-grid dt,
.metric-grid dd {
  margin: 0;
  overflow-wrap: anywhere;
  white-space: normal;
}

.metric-grid dt {
  color: var(--ov-text-muted);
  font-size: 10px;
  font-weight: 800;
}

.metric-grid dd {
  margin-top: 2px;
  color: var(--ov-text);
  font-size: 12px;
  font-weight: 900;
}

.candidate-list {
  display: grid;
  gap: 5px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.candidate-list li {
  border: 1px solid var(--ov-border-subtle);
  border-radius: 5px;
  padding: 7px 8px;
  background: var(--ov-bg-soft);
}

.candidate-body {
  min-width: 0;
}

.candidate-topline {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 5px;
}

.candidate-topline strong {
  min-width: 0;
  color: var(--ov-text);
  font-size: 12px;
}

.candidate-topline span {
  flex: 0 0 auto;
  border-radius: 999px;
  padding: 3px 9px;
  background: var(--ov-bg-warning);
  color: var(--ov-warning);
  font-size: 12px;
  font-weight: 900;
}

.candidate-meta {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 3px 10px;
}

.candidate-meta p {
  margin: 0;
  color: var(--ov-text-secondary);
  font-size: 10px;
  line-height: 1.35;
}

.empty-inline {
  margin: 0;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 5px;
  padding: 10px 12px;
  background: var(--ov-bg-soft);
  color: var(--ov-text-muted);
  font-size: 13px;
  line-height: 1.5;
}

@media (max-width: 1120px) {
  .result-stack {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 959px) {
  .candidate-meta {
    grid-template-columns: 1fr;
  }
}
</style>
