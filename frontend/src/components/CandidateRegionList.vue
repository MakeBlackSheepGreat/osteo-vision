<template>
  <section>
    <h2>Candidate Regions</h2>
    <ul>
      <li v-for="candidate in candidates" :key="candidate.candidate_id">
        {{ candidate.risk_type }} · {{ candidate.status }}
      </li>
    </ul>
    <p v-if="candidates.length === 0">No candidate region yet.</p>
  </section>
</template>

<script setup lang="ts">
import type { CandidateRegion } from "@/types/case";

defineProps<{ candidates: CandidateRegion[] }>();
</script>
