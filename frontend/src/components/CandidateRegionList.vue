<template>
  <section class="panel ov-card">
    <SectionHeading icon="target" icon-tone="amber" eyebrow="AI 辅助提示" title="候选区域" />
    <ul v-if="candidates.length" class="candidate-list">
      <li v-for="candidate in candidates" :key="candidate.candidate_id" :class="{ selected: candidate.candidate_id === activeCandidateId }">
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
          <div v-if="candidateFrameLabel(candidate)">
            <dt>帧位置</dt>
            <dd>{{ candidateFrameLabel(candidate) }}</dd>
          </div>
          <div v-if="candidateBboxLabel(candidate)">
            <dt>候选框</dt>
            <dd>{{ candidateBboxLabel(candidate) }}</dd>
          </div>
        </dl>
        <p>{{ explanationLabel(candidate.explanation) }}</p>
        <AppButton
          v-if="canPromoteCandidate(candidate)"
          class="promote-button"
          variant="secondary"
          size="sm"
          icon="target"
          @click="emit('promoteCandidate', candidate.candidate_id)"
        >
          转为 ROI
        </AppButton>
        <div class="candidate-review-actions" aria-label="候选区复核操作">
          <AppButton
            v-if="canPromoteCandidate(candidate)"
            variant="secondary"
            size="sm"
            icon="target"
            :disabled="candidate.candidate_id === activeCandidateId"
            @click="emit('editCandidateGeometry', candidate.candidate_id)"
          >
            编辑框
          </AppButton>
          <AppButton
            variant="secondary"
            size="sm"
            icon="check"
            :disabled="candidate.status === 'accepted'"
            @click="emit('updateCandidateStatus', candidate.candidate_id, 'accepted')"
          >
            接受
          </AppButton>
          <AppButton
            variant="secondary"
            size="sm"
            icon="target"
            :disabled="candidate.status === 'modified'"
            @click="emit('updateCandidateStatus', candidate.candidate_id, 'modified')"
          >
            修改
          </AppButton>
          <AppButton
            variant="secondary"
            size="sm"
            icon="stop"
            :disabled="candidate.status === 'rejected'"
            @click="emit('updateCandidateStatus', candidate.candidate_id, 'rejected')"
          >
            拒绝
          </AppButton>
        </div>
      </li>
    </ul>
    <p v-else class="ov-empty-text">暂无候选区域。运行双通道分析后会进入医生复核队列。</p>
  </section>
</template>

<script setup lang="ts">
import AppButton from "@/components/AppButton.vue";
import SectionHeading from "@/components/SectionHeading.vue";
import type { CandidateRegion, ReviewState } from "@/types/case";
import { numberLabel, reviewStateLabel, riskLabel } from "@/utils/caseDisplay";

withDefaults(defineProps<{ candidates: CandidateRegion[]; activeCandidateId?: string }>(), {
  activeCandidateId: "",
});
const emit = defineEmits<{
  promoteCandidate: [candidateId: string];
  editCandidateGeometry: [candidateId: string];
  updateCandidateStatus: [candidateId: string, state: ReviewState];
}>();

function explanationLabel(explanation?: string | null): string {
  if (!explanation) return "等待医生结合术野和图像证据复核。";
  if (explanation.includes("fluorescence quantification")) {
    return "由荧光强度统计规则生成，需医生复核。";
  }
  return explanation;
}

function canPromoteCandidate(candidate: CandidateRegion): boolean {
  return Boolean(candidate.metadata?.bbox_normalized);
}

function candidateFrameLabel(candidate: CandidateRegion): string {
  const frame = candidate.metadata?.frame_index;
  const time = candidate.metadata?.timestamp_sec;
  const frameLabel = typeof frame === "number" || typeof frame === "string" ? `帧 ${frame}` : "";
  const timeLabel = typeof time === "number" && Number.isFinite(time) ? `${time.toFixed(2)}s` : "";
  return [frameLabel, timeLabel].filter(Boolean).join(" / ");
}

function candidateBboxLabel(candidate: CandidateRegion): string {
  const bbox = candidate.metadata?.bbox_xyxy;
  if (!Array.isArray(bbox) || bbox.length !== 4) return "";
  return bbox.map((value) => (typeof value === "number" ? Math.round(value) : value)).join(", ");
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

.candidate-list li.selected {
  border-color: var(--ov-border-accent);
  background: linear-gradient(180deg, #eef7ff, #f6fbff);
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

.promote-button {
  margin-top: 9px;
}

.candidate-review-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 9px;
}
</style>
