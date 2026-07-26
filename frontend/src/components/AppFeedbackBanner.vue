<template>
  <section
    class="ov-feedback-banner"
    :class="`ov-feedback-banner--${tone}`"
    :role="resolvedRole"
    :aria-live="resolvedLive"
    aria-atomic="true"
  >
    <AppIcon :name="iconName" />
    <div>
      <strong v-if="title">{{ title }}</strong>
      <span>{{ message }}</span>
    </div>
    <slot name="actions" />
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";

import AppIcon from "@/components/AppIcon.vue";

const props = withDefaults(
  defineProps<{
    tone?: "info" | "pending" | "success" | "warning" | "error";
    title?: string;
    message: string;
    role?: "status" | "alert";
  }>(),
  {
    tone: "info",
  },
);

const iconName = computed(() => {
  if (props.tone === "success") return "check";
  if (props.tone === "error" || props.tone === "warning") return "alert";
  return "document";
});
const resolvedRole = computed(() => props.role ?? (props.tone === "error" ? "alert" : "status"));
const resolvedLive = computed(() => (resolvedRole.value === "alert" ? "assertive" : "polite"));
</script>

