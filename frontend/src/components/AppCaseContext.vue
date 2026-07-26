<template>
  <section class="ov-case-context" aria-label="当前病例摘要">
    <div class="ov-case-context__copy">
      <span>当前病例</span>
      <strong>{{ title || "未载入病例" }}</strong>
      <small v-if="caseId" class="ov-breakable">{{ caseId }}</small>
    </div>
    <span v-if="status" class="ov-status-badge" :class="`is-${tone}`">{{ status }}</span>
    <slot name="actions" />
  </section>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string;
    caseId?: string;
    status?: string;
    tone?: "neutral" | "info" | "success" | "warning" | "danger";
  }>(),
  {
    title: "",
    caseId: "",
    status: "",
    tone: "neutral",
  },
);
</script>

