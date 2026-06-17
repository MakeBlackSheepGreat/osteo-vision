<template>
  <section class="roi-canvas">
    <h2>ROI</h2>
    <p>Manual review region: {{ regionLabel }}</p>
  </section>
</template>

<script setup lang="ts">
defineProps<{ regionLabel?: string }>();
</script>
