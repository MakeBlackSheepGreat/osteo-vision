<template>
  <main class="review-shell">
    <AppPageHeader title="候选区域与 ROI 判读" class="page-header" />

    <section class="review-grid">
      <RoiCanvas
        :region-label="activeCandidate ? '候选框几何编辑' : '术中手动 ROI'"
        :has-output="hasReviewOutput"
        :rois="displayRois"
        :disabled="!store.currentCase"
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
          @promote-candidate="promoteCandidateToRoi"
          @edit-candidate-geometry="editCandidateGeometry"
          @update-candidate-status="updateCandidateStatus"
        />
        <ReviewStateControls @change="setReviewState" />
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
import ReviewStateControls from "@/components/ReviewStateControls.vue";
import RoiCanvas from "@/components/RoiCanvas.vue";
import { useCaseStore } from "@/stores/caseStore";
import type { CandidateRegion, RegionOfInterest, ReviewState } from "@/types/case";

const store = useCaseStore();

const latestRun = computed(() => store.currentCase?.analysis_runs.at(-1));
const latestCandidates = computed(() => latestRun.value?.candidate_regions ?? []);
const latestMetrics = computed(() => latestRun.value?.quantitative_summary ?? {});
const displayCandidates = computed<CandidateRegion[]>(() => latestCandidates.value);
const displayMetrics = computed<Record<string, unknown>>(() => latestMetrics.value);
const displayRois = computed<RegionOfInterest[]>(() => store.currentCase?.rois ?? []);
const activeCandidateId = ref("");
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

async function setReviewState(state: ReviewState) {
  const target = latestCandidates.value[0]?.candidate_id ?? "manual_roi";
  if (!store.currentCase) return;
  if (latestCandidates.value[0]?.candidate_id) {
    await updateCandidateStatus(target, state);
    return;
  }
  await store.addReviewEvent("review_state_change", target, state);
}

async function saveRoiDraft(payload: {
  roiId: string;
  geometry: Record<string, unknown>;
  label: string;
  reviewState: ReviewState;
}) {
  if (!store.currentCase) return;
  if (activeCandidate.value && payload.roiId === activeCandidate.value.candidate_id) {
    await store.updateCandidateRegionState(
      payload.roiId,
      payload.reviewState,
      payload.geometry,
      payload.label,
      "candidate bbox geometry edited in ROI canvas",
    );
    return;
  }
  await store.updateRegion(payload.roiId, payload.reviewState, payload.geometry, payload.label);
  if (!store.error) {
    await store.addReviewEvent("manual_roi_saved", payload.roiId, payload.reviewState);
  }
}

function editCandidateGeometry(candidateId: string) {
  activeCandidateId.value = candidateId;
}

async function promoteCandidateToRoi(candidateId: string) {
  if (!store.currentCase) return;
  await store.addRegionFromCandidate(candidateId);
  if (!store.error) {
    await store.addReviewEvent("candidate_promoted_to_roi", candidateId, "review_required");
  }
}

async function updateCandidateStatus(candidateId: string, state: ReviewState) {
  if (!store.currentCase) return;
  await store.updateCandidateRegionState(candidateId, state);
}

function recordFrom(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
</script>

<style scoped>
.review-shell {
  min-height: 100dvh;
  padding: 20px;
  background:
    radial-gradient(circle at 12% 8%, rgba(34, 211, 238, 0.16), transparent 28%),
    radial-gradient(circle at 88% 18%, rgba(52, 211, 153, 0.1), transparent 26%),
    linear-gradient(180deg, #06111f 0%, #081724 44%, #050b13 100%);
  color: #e6f3ff;
}

.page-header,
.review-grid {
  max-width: 1300px;
  margin-right: auto;
  margin-left: auto;
}

.page-header {
  margin-bottom: 14px;
}

.review-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(300px, 0.8fr);
  gap: 14px;
  align-items: start;
}

.review-stack {
  display: grid;
  gap: 14px;
}

:deep(.ov-card) {
  border: 1px solid rgba(91, 176, 214, 0.24);
  background:
    linear-gradient(180deg, rgba(15, 33, 51, 0.94), rgba(8, 20, 33, 0.96)),
    rgba(8, 20, 33, 0.96);
  box-shadow: 0 18px 42px rgba(0, 0, 0, 0.3);
}

:deep(.section-heading__eyebrow),
:deep(.roi-label-field span),
:deep(dt),
:deep(.roi-status),
:deep(.ov-empty-text) {
  color: rgba(176, 207, 229, 0.72);
}

:deep(.section-heading h2),
:deep(.section-heading__title),
:deep(strong),
:deep(dd) {
  color: #eef8ff;
}

:deep(p) {
  color: rgba(216, 232, 244, 0.78);
}

:deep(.roi-label-field input),
:deep(.roi-label-field select) {
  border-color: rgba(91, 176, 214, 0.3);
  background: rgba(3, 10, 20, 0.78);
  color: #e9f7ff;
}

:deep(.roi-label-field input::placeholder) {
  color: rgba(176, 207, 229, 0.45);
}

:deep(.canvas-frame) {
  border-color: rgba(91, 176, 214, 0.32);
  background: #07121d;
  box-shadow: inset 0 0 32px rgba(34, 211, 238, 0.08);
}

:deep(.canvas-frame.empty) {
  background:
    radial-gradient(circle at 50% 42%, rgba(34, 211, 238, 0.16), transparent 30%),
    linear-gradient(180deg, rgba(7, 18, 29, 0.98), rgba(3, 10, 18, 0.98));
}

:deep(.roi-svg rect:first-of-type) {
  fill: #07121d;
}

:deep(.canvas-meta),
:deep(.empty-canvas-copy) {
  border: 1px solid rgba(91, 176, 214, 0.26);
  background: rgba(3, 10, 20, 0.78);
  color: rgba(229, 246, 255, 0.86);
  box-shadow: 0 10px 26px rgba(0, 0, 0, 0.24);
}

:deep(.empty-canvas-copy strong) {
  color: #67e8f9;
}

:deep(.empty-canvas-copy span) {
  color: rgba(176, 207, 229, 0.74);
}

:deep(.candidate-list li) {
  border-color: rgba(91, 176, 214, 0.2);
  background: rgba(3, 12, 23, 0.62);
}

:deep(.candidate-list li.selected) {
  border-color: rgba(34, 211, 238, 0.74);
  background: linear-gradient(180deg, rgba(13, 54, 75, 0.76), rgba(7, 24, 39, 0.92));
  box-shadow: inset 0 0 0 1px rgba(34, 211, 238, 0.12);
}

:deep(.candidate-title span) {
  background: rgba(245, 158, 11, 0.16);
  color: #fbbf24;
}

:deep(.ov-button--secondary),
:deep(.ov-button--ghost) {
  border-color: rgba(91, 176, 214, 0.28);
  background: rgba(8, 22, 36, 0.82);
  color: #dff5ff;
}

:deep(.ov-button--primary) {
  background: linear-gradient(135deg, #0891b2, #14b8a6);
  color: #f8fdff;
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
