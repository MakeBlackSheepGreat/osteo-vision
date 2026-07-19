<template>
  <main class="review-shell">
    <AppPageHeader title="候选区域与 ROI 判读" class="page-header" />
    <ReviewIdentityPanel />

    <section
      v-if="feedbackMessage"
      class="review-feedback"
      :class="`review-feedback--${feedbackTone}`"
      :role="feedbackTone === 'error' ? 'alert' : 'status'"
      :aria-live="feedbackTone === 'error' ? 'assertive' : 'polite'"
      aria-atomic="true"
    >
      <strong>{{ feedbackHeading }}</strong>
      <span>{{ feedbackMessage }}</span>
    </section>

    <section class="review-grid">
      <RoiCanvas
        :region-label="activeCandidate ? '候选框几何编辑' : '术中手动 ROI'"
        :has-output="hasReviewOutput"
        :rois="displayRois"
        :disabled="!store.currentCase"
        :loading="store.loading"
        :draft-id="activeCandidate?.candidate_id ?? ''"
        :draft-geometry="activeCandidateGeometry"
        :draft-label="activeCandidate?.risk_type ?? ''"
        draft-review-state="modified"
        :save-label="activeCandidate ? '保存候选框' : '保存 ROI'"
        :empty-text="activeCandidate ? '拖拽调整候选框边界，保存后写入候选区复核记录。' : undefined"
        @save="saveRoiDraft"
      />
      <div class="review-stack">
        <CandidateRegionList
          :candidates="displayCandidates"
          :active-candidate-id="activeCandidateId"
          :loading="store.loading"
          :promoted-candidate-ids="promotedCandidateIds"
          @promote-candidate="promoteCandidateToRoi"
          @edit-candidate-geometry="editCandidateGeometry"
          @select-candidate="selectCandidate"
          @update-candidate-status="updateCandidateStatus"
        />
        <ReviewStateControls
          :candidate="activeCandidate"
          :disabled="!store.currentCase || store.loading"
          @change="setReviewState"
        />
        <QuantificationPanel :metrics="displayMetrics" />
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";

import AppPageHeader from "@/components/AppPageHeader.vue";
import CandidateRegionList from "@/components/CandidateRegionList.vue";
import QuantificationPanel from "@/components/QuantificationPanel.vue";
import ReviewIdentityPanel from "@/components/ReviewIdentityPanel.vue";
import ReviewStateControls from "@/components/ReviewStateControls.vue";
import RoiCanvas from "@/components/RoiCanvas.vue";
import { useCaseStore } from "@/stores/caseStore";
import type { CandidateRegion, RegionOfInterest, ReviewState } from "@/types/case";
import { reviewStateLabel } from "@/utils/caseDisplay";

const store = useCaseStore();
type FeedbackTone = "pending" | "success" | "error";

const latestRun = computed(() => store.currentCase?.analysis_runs.at(-1));
const latestCandidates = computed(() => latestRun.value?.candidate_regions ?? []);
const latestMetrics = computed(() => latestRun.value?.quantitative_summary ?? {});
const displayCandidates = computed<CandidateRegion[]>(() => latestCandidates.value);
const displayMetrics = computed<Record<string, unknown>>(() => latestMetrics.value);
const displayRois = computed<RegionOfInterest[]>(() => store.currentCase?.rois ?? []);
const promotedCandidateIds = computed(() =>
  displayRois.value.flatMap((roi) => (roi.candidate_id ? [roi.candidate_id] : [])),
);
const activeCandidateId = ref("");
const operationMessage = ref("");
const operationTone = ref<FeedbackTone>("pending");
const activeCandidate = computed<CandidateRegion | null>(
  () => displayCandidates.value.find((candidate) => candidate.candidate_id === activeCandidateId.value) ?? null,
);
const activeCandidateGeometry = computed<Record<string, unknown> | null>(() => {
  const geometry = activeCandidate.value?.metadata?.bbox_normalized;
  return recordFrom(geometry) ? geometry : null;
});
const hasReviewOutput = computed(
  () => latestCandidates.value.length > 0 || Object.keys(latestMetrics.value).length > 0 || displayRois.value.length > 0,
);
const feedbackMessage = computed(() => store.error || operationMessage.value);
const feedbackTone = computed<FeedbackTone>(() => (store.error ? "error" : operationTone.value));
const feedbackHeading = computed(() => {
  if (feedbackTone.value === "error") return "复核操作未完成";
  if (feedbackTone.value === "success") return "复核记录已更新";
  return "正在处理";
});

async function setReviewState(state: ReviewState) {
  const candidateId = activeCandidate.value?.candidate_id;
  if (!store.currentCase || !candidateId || store.loading) return;
  await updateCandidateStatus(candidateId, state);
}

async function saveRoiDraft(payload: {
  roiId: string;
  geometry: Record<string, unknown>;
  label: string;
  reviewState: ReviewState;
}) {
  if (!store.currentCase || store.loading) return;
  if (activeCandidate.value && payload.roiId === activeCandidate.value.candidate_id) {
    startOperation("正在保存候选框几何和复核状态...");
    await store.updateCandidateRegionState(
      payload.roiId,
      payload.reviewState,
      payload.geometry,
      payload.label,
      "candidate bbox geometry edited in ROI canvas",
    );
    finishOperation(`候选区 ${payload.roiId} 的几何和复核状态已保存。`);
    return;
  }
  startOperation("正在保存手动 ROI 和复核记录...");
  await store.updateRegion(payload.roiId, payload.reviewState, payload.geometry, payload.label);
  if (store.error) {
    finishOperation("");
    return;
  }
  await store.addReviewEvent("manual_roi_saved", payload.roiId, payload.reviewState);
  finishOperation(`ROI ${payload.roiId} 已保存并写入复核记录。`);
}

function editCandidateGeometry(candidateId: string) {
  activeCandidateId.value = candidateId;
}

function selectCandidate(candidateId: string) {
  activeCandidateId.value = candidateId;
}

async function promoteCandidateToRoi(candidateId: string) {
  if (!store.currentCase || store.loading || promotedCandidateIds.value.includes(candidateId)) return;
  startOperation(`正在将候选区 ${candidateId} 转为 ROI...`);
  await store.addRegionFromCandidate(candidateId);
  if (store.error) {
    finishOperation("");
    return;
  }
  await store.addReviewEvent("candidate_promoted_to_roi", candidateId, "review_required");
  finishOperation(`候选区 ${candidateId} 已转为 ROI，并进入待复核队列。`);
}

async function updateCandidateStatus(candidateId: string, state: ReviewState) {
  if (!store.currentCase || store.loading) return;
  startOperation(`正在将候选区 ${candidateId} 更新为${reviewStateLabel(state)}...`);
  await store.updateCandidateRegionState(candidateId, state);
  finishOperation(`候选区 ${candidateId} 已更新为${reviewStateLabel(state)}。`);
}

function startOperation(message: string) {
  operationMessage.value = message;
  operationTone.value = "pending";
}

function finishOperation(successMessage: string): boolean {
  if (store.error) {
    operationMessage.value = store.error;
    operationTone.value = "error";
    return false;
  }
  operationMessage.value = successMessage;
  operationTone.value = "success";
  return true;
}

function recordFrom(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
</script>

<style scoped>
.review-shell {
  min-height: 100dvh;
  padding: var(--ov-page-top) var(--ov-page-inline) var(--ov-page-bottom);
  background: var(--ov-shell-background);
  color: var(--ov-text);
}

.page-header,
.review-feedback,
.review-grid {
  max-width: var(--ov-content-standard);
  margin-right: auto;
  margin-left: auto;
}

.page-header {
  margin-bottom: var(--ov-space-5);
}

.review-feedback {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--ov-space-3);
  align-items: baseline;
  margin-bottom: var(--ov-space-5);
  border: 1px solid var(--ov-border-strong);
  border-radius: var(--ov-radius-control);
  padding: 12px 14px;
  background: var(--ov-bg-info);
  color: var(--ov-text-secondary);
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.review-feedback strong {
  color: var(--ov-primary);
  font-size: 12px;
}

.review-feedback span {
  min-width: 0;
  font-size: 13px;
}

.review-feedback--success {
  border-color: var(--ov-success);
  background: var(--ov-bg-success);
  color: var(--ov-success);
}

.review-feedback--success strong {
  color: var(--ov-success);
}

.review-feedback--error {
  border-color: var(--ov-danger-border);
  background: var(--ov-bg-danger);
  color: var(--ov-danger);
}

.review-feedback--error strong {
  color: var(--ov-danger);
}

.review-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(320px, 0.7fr);
  gap: 24px;
  align-items: start;
}

.review-stack {
  display: grid;
  gap: 20px;
}

:deep(.ov-card) {
  border: 1px solid var(--ov-border);
  background: var(--ov-bg-elevated);
  box-shadow: var(--ov-shadow);
}

:deep(.section-heading__eyebrow),
:deep(.roi-label-field span),
:deep(dt),
:deep(.roi-status),
:deep(.ov-empty-text) {
  color: var(--ov-text-muted);
}

:deep(.section-heading h2),
:deep(.section-heading__title),
:deep(strong),
:deep(dd) {
  color: var(--ov-text);
}

:deep(p) {
  color: var(--ov-text-secondary);
}

:deep(.roi-label-field input),
:deep(.roi-label-field select) {
  border-color: var(--ov-border-strong);
  background: var(--ov-bg-control);
  color: var(--ov-text);
}

:deep(.roi-label-field input::placeholder) {
  color: var(--ov-text-muted);
}

:deep(.canvas-frame) {
  border-color: var(--ov-border-strong);
  background: var(--ov-bg-media);
  box-shadow: inset 0 0 32px var(--ov-overlay-strong);
}

:deep(.canvas-frame.empty) {
  background: var(--ov-bg-soft);
  box-shadow: none;
}

:deep(.canvas-frame.active .roi-svg rect:first-of-type) {
  fill: var(--ov-bg-media);
}

:deep(.canvas-frame.empty .roi-svg rect:first-of-type) {
  fill: var(--ov-bg-soft);
}

:deep(.canvas-meta),
:deep(.empty-canvas-copy) {
  border: 1px solid var(--ov-border-strong);
  background: var(--ov-bg-elevated);
  color: var(--ov-text-secondary);
  box-shadow: var(--ov-shadow);
}

:deep(.empty-canvas-copy strong) {
  color: var(--ov-primary-strong);
}

:deep(.empty-canvas-copy span) {
  color: var(--ov-text-muted);
}

:deep(.candidate-list li) {
  border-color: var(--ov-border-subtle);
  background: var(--ov-bg-soft);
}

:deep(.candidate-list li.selected) {
  border-color: var(--ov-border-accent);
  background: var(--ov-bg-selected);
  box-shadow: inset 0 0 0 1px var(--ov-focus-ring);
}

:deep(.candidate-title span) {
  background: var(--ov-bg-warning);
  color: var(--ov-warning);
}

:deep(.ov-button--secondary),
:deep(.ov-button--ghost) {
  border-color: var(--ov-border-strong);
  background: var(--ov-bg-control);
  color: var(--ov-text);
}

:deep(.ov-button--primary) {
  background: var(--ov-button-primary-bg);
  color: var(--ov-text-on-primary);
}

:deep(.ov-button:disabled) {
  opacity: 0.45;
}

@media (max-width: 860px) {
  .review-shell {
    padding: 12px;
  }

  .review-grid {
    grid-template-columns: 1fr;
  }
}
</style>
