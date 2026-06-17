<template>
  <main class="review">
    <h1>Physician Review Workspace</h1>
    <RoiCanvas region-label="Manual ROI" />
    <CandidateRegionList :candidates="latestCandidates" />
    <ReviewStateControls @change="setReviewState" />
    <QuantificationPanel :metrics="latestMetrics" />
  </main>
</template>

<script setup lang="ts">
import { computed } from "vue";

import CandidateRegionList from "@/components/CandidateRegionList.vue";
import QuantificationPanel from "@/components/QuantificationPanel.vue";
import ReviewStateControls from "@/components/ReviewStateControls.vue";
import RoiCanvas from "@/components/RoiCanvas.vue";
import { useCaseStore } from "@/stores/caseStore";
import type { ReviewState } from "@/types/case";

const store = useCaseStore();

const latestRun = computed(() => store.currentCase?.analysis_runs.at(-1));
const latestCandidates = computed(() => latestRun.value?.candidate_regions ?? []);
const latestMetrics = computed(() => latestRun.value?.quantitative_summary ?? {});

async function setReviewState(state: ReviewState) {
  const target = latestCandidates.value[0]?.candidate_id ?? "manual_roi";
  if (!store.currentCase) return;
  await store.addReviewEvent("review_state_change", target, state);
}
</script>
