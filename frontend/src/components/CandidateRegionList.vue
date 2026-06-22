<template>
  <section class="panel ov-card">
    <SectionHeading icon="target" icon-tone="amber" eyebrow="AI 辅助提示" title="候选区域" />
    <ul v-if="candidates.length" class="candidate-list">
      <li v-for="candidate in candidates" :key="candidate.candidate_id">
        <div class="candidate-title">
          <strong>{{ riskLabel(candidate.risk_type) }}</strong>
          <span>{{ reviewStateLabel(candidate.status) }}</span>
        </div>
        <dl>
          <div>
            <dt>分数</dt>
            <dd>{{ numberLabel(candidate.score) }}</dd>
          </div>
          <div>
            <dt>置信参考</dt>
            <dd>{{ numberLabel(candidate.confidence) }}</dd>
          </div>
        </dl>
        <p>{{ explanationLabel(candidate.explanation) }}</p>
      </li>
    </ul>
    <p v-else class="ov-empty-text">暂无候选区域。运行双通道分析后会进入医生复核队列。</p>
  </section>
</template>

<script setup lang="ts">
import SectionHeading from "@/components/SectionHeading.vue";
import type { CandidateRegion } from "@/types/case";
import { numberLabel, reviewStateLabel, riskLabel } from "@/utils/caseDisplay";

defineProps<{ candidates: CandidateRegion[] }>();

function explanationLabel(explanation?: string | null): string {
  if (!explanation) return "等待医生结合术野和图像证据复核。";
  if (explanation.includes("fluorescence quantification")) {
    return "由荧光强度统计规则生成，需医生复核。";
  }
  return explanation;
}
</script>

<style scoped>
.panel {
  padding: 14px;
}

.candidate-list {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.candidate-list li {
  border: 1px solid var(--ov-border-subtle);
  border-radius: var(--ov-radius);
  padding: 10px;
  background: var(--ov-bg-soft);
}

.candidate-title {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
}

.candidate-title span {
  border-radius: 999px;
  padding: 4px 8px;
  background: var(--ov-bg-warning);
  color: var(--ov-warning);
  font-size: 12px;
  font-weight: 700;
}

dl {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin: 10px 0;
}

dt {
  color: var(--ov-text-muted);
  font-size: 12px;
}

dd {
  margin: 2px 0 0;
  color: var(--ov-text);
}

p {
  margin: 0;
  color: var(--ov-text-secondary);
  font-size: 13px;
  line-height: 1.6;
}
</style>
