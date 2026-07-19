<template>
  <div class="ov-section-heading">
    <AppIcon
      v-if="icon"
      class="ov-section-heading__icon"
      :name="icon"
      variant="badge"
      :tone="iconTone"
    />
    <div class="ov-section-heading__copy">
      <p v-if="eyebrow" class="ov-section-heading__eyebrow">{{ eyebrow }}</p>
      <component :is="tag" class="ov-section-heading__title">
        {{ title }}
      </component>
    </div>
  </div>
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
    tag?: "h2" | "h3";
  }>(),
  {
    iconTone: "blue",
    tag: "h2",
  },
);
</script>

<style scoped>
.ov-section-heading {
  display: flex;
  gap: 10px;
  align-items: center;
  min-width: 0;
}

.ov-section-heading__icon {
  width: 26px;
  height: 26px;
}

.ov-section-heading__copy {
  min-width: 0;
}

.ov-section-heading__eyebrow,
.ov-section-heading__title {
  margin: 0;
}

.ov-section-heading__title {
  overflow-wrap: anywhere;
}
</style>
