<template>
  <dl class="ov-metric-strip" :aria-label="ariaLabel">
    <div v-for="item in items" :key="item.label" :class="item.tone ? `is-${item.tone}` : undefined">
      <dt>
        <AppIcon v-if="item.icon" :name="item.icon" />
        <span>{{ item.label }}</span>
      </dt>
      <dd :class="{ 'ov-breakable': item.breakable }">{{ item.value }}</dd>
    </div>
  </dl>
</template>

<script setup lang="ts">
import AppIcon from "@/components/AppIcon.vue";
import type { AppIconName } from "@/components/appIcons";

export interface AppMetricItem {
  label: string;
  value: string | number;
  icon?: AppIconName;
  tone?: "neutral" | "info" | "success" | "warning" | "danger";
  breakable?: boolean;
}

withDefaults(
  defineProps<{
    items: AppMetricItem[];
    ariaLabel?: string;
  }>(),
  {
    ariaLabel: "指标摘要",
  },
);
</script>
