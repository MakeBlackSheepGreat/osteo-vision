<template>
  <main class="ov-page-shell" :class="[`ov-page-shell--${width}`, `ov-page-shell--${density}`]">
    <slot />
  </main>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    width?: "compact" | "standard" | "large" | "wide";
    density?: "comfortable" | "compact";
  }>(),
  {
    width: "standard",
    density: "comfortable",
  },
);
</script>

