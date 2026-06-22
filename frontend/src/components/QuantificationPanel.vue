<template>
  <section class="panel ov-card">
    <SectionHeading icon="document" icon-tone="green" eyebrow="荧光分析" title="量化指标" />
    <dl v-if="entries.length" class="metric-list">
      <div v-for="[key, value] in entries" :key="key">
        <dt>{{ metricLabel(key) }}</dt>
        <dd>{{ valueLabel(value) }}</dd>
      </div>
    </dl>
    <p v-else class="ov-empty-text">暂无量化指标。</p>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";

import SectionHeading from "@/components/SectionHeading.vue";
import { metricLabel, valueLabel } from "@/utils/caseDisplay";

const props = defineProps<{ metrics: Record<string, unknown> }>();

const entries = computed(() => Object.entries(props.metrics));

</script>

<style scoped>
.panel {
  padding: 14px;
}

.metric-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 0;
}

dt {
  color: var(--ov-text-muted);
  font-size: 12px;
}

dd {
  margin: 3px 0 0;
  color: var(--ov-text);
  overflow-wrap: anywhere;
}
</style>
