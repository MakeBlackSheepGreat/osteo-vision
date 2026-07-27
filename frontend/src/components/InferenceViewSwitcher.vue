<template>
  <div class="inference-view-switcher">
    <div class="inference-view-tabs" role="tablist" aria-label="AI 推理结果视图">
      <button
        v-for="option in inferenceViewOptions"
        :key="option.key"
        type="button"
        role="tab"
        :class="[`view-${option.key}`, { active: selectedView === option.key }]"
        :aria-selected="selectedView === option.key"
        :title="option.label"
        @click="selectedView = option.key"
      >
        <span class="view-swatch" aria-hidden="true"></span>
        {{ option.shortLabel }}
      </button>
    </div>

    <div class="inference-view-media">
      <img v-if="selectedSource" :src="selectedSource" :alt="selectedOption.alt" />
      <div v-else class="inference-view-empty" role="status">
        <AppIcon name="target" />
        <strong>等待{{ selectedOption.label }}输出</strong>
        <span>{{ emptyMessage }}</span>
      </div>
      <span v-if="statusLabel" class="inference-refresh-badge" :class="sourceMode">
        {{ statusLabel }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";

import AppIcon from "@/components/AppIcon.vue";
import {
  inferenceViewOptions,
  type InferenceViewKey,
  type InferenceViewSources,
} from "@/components/inferenceViews";

const props = withDefaults(defineProps<{
  sources?: InferenceViewSources;
  statusLabel?: string;
  sourceMode?: "continuous" | "keyframe" | "waiting";
  emptyMessage?: string;
}>(), {
  sources: () => ({}),
  statusLabel: "",
  sourceMode: "waiting",
  emptyMessage: "完成当前帧推理后显示",
});

const selectedView = ref<InferenceViewKey>("signal");
const selectedOption = computed(
  () => inferenceViewOptions.find((option) => option.key === selectedView.value) ?? inferenceViewOptions[0],
);
const selectedSource = computed(() => props.sources[selectedView.value] ?? "");
</script>

<style scoped>
.inference-view-switcher {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
}

.inference-view-tabs {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 3px;
  padding: 4px;
  border-bottom: 1px solid var(--ov-border-strong);
  background: var(--ov-bg-soft);
}

.inference-view-tabs button {
  display: inline-flex;
  min-width: 0;
  min-height: 30px;
  align-items: center;
  justify-content: center;
  gap: 5px;
  border: 1px solid transparent;
  border-radius: 4px;
  padding: 4px 6px;
  background: transparent;
  color: var(--ov-text-secondary);
  font: inherit;
  font-size: 11px;
  font-weight: 800;
  line-height: 1.25;
  cursor: pointer;
}

.inference-view-tabs button:hover {
  background: var(--ov-bg-elevated);
  color: var(--ov-text);
}

.inference-view-tabs button.active {
  border-color: var(--ov-border-strong);
  background: var(--ov-bg-elevated);
  color: var(--ov-text);
}

.view-swatch {
  flex: 0 0 auto;
  width: 8px;
  height: 8px;
  border-radius: 2px;
  background: var(--ov-success);
}

.view-risk .view-swatch {
  background: var(--ov-warning);
}

.view-uncertainty .view-swatch {
  background: #6d77c8;
}

.inference-view-media {
  position: relative;
  display: grid;
  min-width: 0;
  min-height: 0;
  place-items: center;
  overflow: hidden;
  background: var(--ov-bg-panel);
}

.inference-view-media img {
  display: block;
  width: 100%;
  height: 100%;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.inference-view-empty {
  display: grid;
  max-width: 280px;
  gap: 7px;
  place-items: center;
  padding: 20px;
  color: var(--ov-text-secondary);
  text-align: center;
}

.inference-view-empty :deep(.app-icon) {
  width: 22px;
  height: 22px;
  color: var(--ov-primary);
}

.inference-view-empty strong {
  color: var(--ov-text);
  font-size: 13px;
}

.inference-view-empty span {
  font-size: 11px;
  line-height: 1.5;
}

.inference-refresh-badge {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 2;
  max-width: calc(100% - 16px);
  border: 1px solid var(--ov-warning);
  border-radius: 4px;
  padding: 5px 8px;
  background: color-mix(in srgb, var(--ov-bg-panel) 88%, transparent);
  color: var(--ov-text);
  font-size: 11px;
  font-weight: 800;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.inference-refresh-badge.continuous {
  border-color: var(--ov-success);
}

@media (max-width: 680px) {
  .inference-view-tabs button {
    align-items: flex-start;
    font-size: 10px;
  }
}
</style>
