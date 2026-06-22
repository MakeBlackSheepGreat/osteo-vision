<template>
  <section class="panel ov-card">
    <SectionHeading icon="review" icon-tone="green" eyebrow="医生操作" title="复核状态" />
    <div class="button-row">
      <button class="ov-button ov-button--primary" @click="emit('change', 'accepted')">接受候选区</button>
      <button class="ov-button ov-button--secondary" @click="emit('change', 'modified')">标记已修改</button>
      <button class="ov-button ov-button--secondary ov-button--danger" @click="emit('change', 'rejected')">
        驳回提示
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import SectionHeading from "@/components/SectionHeading.vue";

const emit = defineEmits<{
  (event: "change", value: "accepted" | "modified" | "rejected"): void;
}>();
</script>

<style scoped>
.panel {
  padding: 14px;
}

.button-row {
  display: grid;
  gap: 8px;
}
</style>
