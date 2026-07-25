<template>
  <section class="ov-toolbar" :aria-label="ariaLabel">
    <slot />
  </section>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    ariaLabel?: string;
  }>(),
  {
    ariaLabel: "页面操作",
  },
);
</script>

