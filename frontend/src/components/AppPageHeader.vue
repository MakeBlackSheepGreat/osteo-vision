<template>
  <header class="ov-page-header">
    <div class="ov-page-header__copy">
      <p v-if="eyebrow" class="ov-eyebrow">{{ eyebrow }}</p>
      <h1 class="ov-page-title">{{ title }}</h1>
    </div>
    <div v-if="$slots.actions" class="ov-page-header__actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<script setup lang="ts">
defineProps<{
  eyebrow?: string;
  title: string;
}>();
</script>
