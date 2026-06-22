<template>
  <nav class="ov-nav-pills" :aria-label="ariaLabel">
    <RouterLink
      v-for="item in items"
      :key="item.to"
      class="ov-nav-pill"
      :to="item.to"
    >
      <AppIcon v-if="item.icon" :name="item.icon" />
      {{ item.label }}
    </RouterLink>
  </nav>
</template>

<script setup lang="ts">
import AppIcon from "@/components/AppIcon.vue";
import type { AppIconName } from "@/components/appIcons";

withDefaults(
  defineProps<{
    items: Array<{ to: string; label: string; icon?: AppIconName }>;
    ariaLabel?: string;
  }>(),
  {
    ariaLabel: "导航",
  },
);
</script>

<style scoped>
.ov-nav-pill :deep(.app-icon) {
  width: 16px;
  height: 16px;
  color: currentColor;
}
</style>
