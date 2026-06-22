<template>
  <main class="review-shell">
    <AppPageHeader title="候选区域与 ROI 判读" class="page-header" />

    <section class="review-grid">
      <RoiCanvas region-label="术中手动 ROI" :has-output="hasReviewOutput" />
      <div class="review-stack">
        <CandidateRegionList :candidates="displayCandidates" />
        <ReviewStateControls @change="setReviewState" />
        <QuantificationPanel :metrics="displayMetrics" />
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed } from "vue";

import AppPageHeader from "@/components/AppPageHeader.vue";
import CandidateRegionList from "@/components/CandidateRegionList.vue";
import QuantificationPanel from "@/components/QuantificationPanel.vue";
import ReviewStateControls from "@/components/ReviewStateControls.vue";
import RoiCanvas from "@/components/RoiCanvas.vue";
import { useCaseStore } from "@/stores/caseStore";
import type { CandidateRegion, ReviewState } from "@/types/case";

const store = useCaseStore();

const latestRun = computed(() => store.currentCase?.analysis_runs.at(-1));
const latestCandidates = computed(() => latestRun.value?.candidate_regions ?? []);
const latestMetrics = computed(() => latestRun.value?.quantitative_summary ?? {});
const displayCandidates = computed<CandidateRegion[]>(() => latestCandidates.value);
const displayMetrics = computed<Record<string, unknown>>(() => latestMetrics.value);
const hasReviewOutput = computed(
  () => latestCandidates.value.length > 0 || Object.keys(latestMetrics.value).length > 0,
);

async function setReviewState(state: ReviewState) {
  const target = latestCandidates.value[0]?.candidate_id ?? "manual_roi";
  if (!store.currentCase) return;
  await store.addReviewEvent("review_state_change", target, state);
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
