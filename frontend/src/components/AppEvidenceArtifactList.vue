<template>
  <div v-if="artifacts.length" class="ov-artifact-list" :class="{ 'ov-artifact-list--compact': compact }">
    <article v-for="artifact in visibleArtifacts" :key="artifact.id || artifact.path" class="ov-artifact-list__item">
      <div>
        <strong>{{ artifact.label || artifactKindLabel(artifact.kind || "") }}</strong>
        <span v-if="artifact.path" class="ov-breakable">{{ artifact.path }}</span>
      </div>
      <small v-if="artifact.sizeBytes !== undefined">{{ formatArtifactBytes(artifact.sizeBytes) }}</small>
      <a v-if="artifact.href" :href="artifact.href" target="_blank" rel="noreferrer">查看</a>
    </article>
  </div>
  <AppEmptyState
    v-else
    compact
    icon="file"
    title="暂无导出内容"
    :description="emptyText"
  />
</template>

<script setup lang="ts">
import { computed } from "vue";

import AppEmptyState from "@/components/AppEmptyState.vue";
import { artifactKindLabel, formatArtifactBytes } from "@/utils/artifactDisplay";

const props = withDefaults(
  defineProps<{
    artifacts: Array<{
      id?: string;
      kind?: string;
      label?: string;
      path?: string;
      href?: string;
      sizeBytes?: number | null;
    }>;
    compact?: boolean;
    limit?: number;
    emptyText?: string;
  }>(),
  {
    compact: false,
    limit: 0,
    emptyText: "运行分析并导出证据包后，可在此查看文件清单。",
  },
);

const visibleArtifacts = computed(() => (props.limit > 0 ? props.artifacts.slice(0, props.limit) : props.artifacts));
</script>
