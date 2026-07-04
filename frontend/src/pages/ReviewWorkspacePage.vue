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
    radial-gradient(circle at 10% 8%, rgba(45, 120, 173, 0.06), transparent 24%),
    linear-gradient(180deg, #eef3f8, var(--ov-bg) 240px),
    var(--ov-bg);
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

@media (max-width: 860px) {
  .review-shell {
    padding: 12px;
  }

  .review-grid {
    grid-template-columns: 1fr;
  }
}
</style>
