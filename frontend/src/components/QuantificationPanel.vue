<template>
  <section>
    <h2>Quantification</h2>
    <pre>{{ metrics }}</pre>
  </section>
</template>

<script setup lang="ts">
defineProps<{ metrics: Record<string, unknown> }>();
</script>
