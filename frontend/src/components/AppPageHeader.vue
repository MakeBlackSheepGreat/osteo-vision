<template>
  <header class="ov-page-header">
    <div class="ov-title-lead">
      <AppIcon v-if="icon" :name="icon" variant="badge" :tone="iconTone" />
      <div class="ov-page-header__copy">
        <p v-if="eyebrow" class="ov-eyebrow">{{ eyebrow }}</p>
        <h1 class="ov-page-title">{{ title }}</h1>
      </div>
    </div>
    <div v-if="$slots.actions" class="ov-page-header__actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<script setup lang="ts">
import AppIcon from "@/components/AppIcon.vue";
import type { AppIconName } from "@/components/appIcons";

withDefaults(
  defineProps<{
    eyebrow?: string;
    icon?: AppIconName;
    iconTone?: "blue" | "cyan" | "green" | "amber" | "red" | "slate";
    title: string;
  }>(),
  {
    iconTone: "cyan",
  },
);
</script>
