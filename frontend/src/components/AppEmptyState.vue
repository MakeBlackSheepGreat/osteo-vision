<template>
  <section class="ov-empty-state" :class="{ 'ov-empty-state--compact': compact }" :aria-label="title">
    <AppIcon :name="icon" variant="badge" :tone="tone" />
    <div>
      <h2>{{ title }}</h2>
      <p>{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="ov-empty-state__actions">
      <slot name="actions" />
    </div>
  </section>
</template>

<script setup lang="ts">
import AppIcon from "@/components/AppIcon.vue";
import type { AppIconName } from "@/components/appIcons";

withDefaults(
  defineProps<{
    title: string;
    description: string;
    icon?: AppIconName;
    tone?: "blue" | "cyan" | "green" | "amber" | "red" | "slate";
    compact?: boolean;
  }>(),
  {
    icon: "document",
    tone: "cyan",
    compact: false,
  },
);
</script>

