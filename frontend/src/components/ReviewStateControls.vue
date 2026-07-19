<template>
  <section class="panel ov-card">
    <SectionHeading icon="review" icon-tone="green" eyebrow="医生操作" title="复核状态" />
    <p class="selection-context" role="status">
      <span>当前复核对象</span>
      <strong v-if="candidate">{{ candidateLabel }}</strong>
      <strong v-else>请先从候选区域中选择对象</strong>
    </p>
    <div class="button-row">
      <button
        class="ov-button ov-button--primary"
        :disabled="actionDisabled('accepted')"
        :title="actionTitle('accepted')"
        @click="emit('change', 'accepted')"
      >接受候选区</button>
      <button
        class="ov-button ov-button--secondary"
        :disabled="actionDisabled('modified')"
        :title="actionTitle('modified')"
        @click="emit('change', 'modified')"
      >标记已修改</button>
      <button
        class="ov-button ov-button--secondary ov-button--danger"
        :disabled="actionDisabled('rejected')"
        :title="actionTitle('rejected')"
        @click="emit('change', 'rejected')"
      >
        驳回提示
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";

import SectionHeading from "@/components/SectionHeading.vue";
import type { CandidateRegion, ReviewState } from "@/types/case";
import { riskLabel } from "@/utils/caseDisplay";

const props = withDefaults(
  defineProps<{
    candidate?: CandidateRegion | null;
    disabled?: boolean;
  }>(),
  {
    candidate: null,
    disabled: false,
  },
);

const emit = defineEmits<{
  (event: "change", value: "accepted" | "modified" | "rejected"): void;
}>();

const candidateLabel = computed(() => (props.candidate ? riskLabel(props.candidate.risk_type) : ""));

function actionDisabled(state: ReviewState): boolean {
  return props.disabled || !props.candidate || props.candidate.status === state;
}

function actionTitle(state: ReviewState): string {
  if (props.disabled) return "当前复核写入进行中，请等待完成。";
  if (!props.candidate) return "请先从候选区域中选择对象。";
  if (props.candidate.status === state) return "当前候选区已处于该复核状态。";
  return `将当前候选区标记为${stateLabel(state)}。`;
}

function stateLabel(state: ReviewState): string {
  const labels: Record<ReviewState, string> = {
    review_required: "待复核",
    accepted: "已接受",
    modified: "已修改",
    rejected: "已拒绝",
  };
  return labels[state];
}
</script>

<style scoped>
.panel {
  padding: 14px;
}

.button-row {
  display: grid;
  gap: 8px;
}

.selection-context {
  display: grid;
  gap: 3px;
  margin: 0 0 10px;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 5px;
  padding: 8px 10px;
  background: var(--ov-bg-soft);
}

.selection-context span {
  color: var(--ov-text-muted);
  font-size: 11px;
  font-weight: 700;
}

.selection-context strong {
  color: var(--ov-text-secondary);
  font-size: 12px;
  line-height: 1.4;
}
</style>
