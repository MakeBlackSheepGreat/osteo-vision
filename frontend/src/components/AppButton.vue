<template>
  <button
    :class="buttonClass"
    :type="type"
    :title="title"
    :aria-label="ariaLabel"
    :disabled="disabled"
  >
    <AppIcon v-if="icon" :name="icon" />
    <span v-if="!iconOnly" class="app-button__label">
      <slot />
    </span>
  </button>
</template>

<script setup lang="ts">
import { computed } from "vue";

import AppIcon from "@/components/AppIcon.vue";
import type { AppIconName } from "@/components/appIcons";

const props = withDefaults(
  defineProps<{
    variant?: "primary" | "secondary" | "ghost";
    size?: "sm" | "md";
    type?: "button" | "submit" | "reset";
    icon?: AppIconName;
    iconOnly?: boolean;
    block?: boolean;
    title?: string;
    ariaLabel?: string;
    disabled?: boolean;
  }>(),
  {
    variant: "secondary",
    size: "md",
    type: "button",
    iconOnly: false,
    block: false,
    disabled: false,
  },
);

// 按钮视觉状态集中在组件内，页面只声明用途，避免各处重复手写按钮 CSS。
const buttonClass = computed(() => [
  "app-button",
  `app-button--${props.variant}`,
  `app-button--${props.size}`,
  {
    "app-button--block": props.block,
    "app-button--icon-only": props.iconOnly,
  },
]);
</script>

<style scoped>
.app-button {
  --app-icon-bg: var(--ov-bg-control);
  display: inline-flex;
  gap: 8px;
  align-items: center;
  justify-content: center;
  min-width: 0;
  border: 1px solid var(--ov-border-strong);
  border-radius: 6px;
  background: var(--ov-bg-control);
  color: var(--ov-primary);
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0;
  text-decoration: none;
  overflow-wrap: anywhere;
  white-space: normal;
  cursor: pointer;
  box-shadow: none;
  transition:
    transform 140ms ease,
    border-color 140ms ease,
    background 140ms ease,
    color 140ms ease,
    box-shadow 140ms ease,
    opacity 140ms ease;
}

.app-button :deep(.app-icon) {
  width: 16px;
  height: 16px;
}

.app-button--primary :deep(.app-icon) {
  color: var(--ov-text-on-primary);
}

.app-button--md {
  min-height: var(--ov-control-height);
  padding: 9px 14px;
}

.app-button--sm {
  min-height: var(--ov-control-height-sm);
  padding: 8px 12px;
}

.app-button--block {
  width: 100%;
}

.app-button--icon-only {
  width: 34px;
  padding-right: 0;
  padding-left: 0;
}

.app-button--primary {
  --app-icon-bg: var(--ov-button-primary-bg);
  border-color: var(--ov-border-accent);
  background: var(--ov-button-primary-bg);
  color: var(--ov-text-on-primary);
  box-shadow: none;
}

.app-button--secondary {
  --app-icon-bg: var(--ov-bg-control);
  border-color: var(--ov-border-strong);
  background: var(--ov-bg-control);
  color: var(--ov-primary);
}

.app-button--ghost {
  --app-icon-bg: var(--ov-bg-hover);
  border-color: var(--ov-border);
  background: var(--ov-bg-hover);
  color: var(--ov-primary-strong);
  box-shadow: none;
}

.app-button:hover:not(:disabled) {
  transform: none;
  border-color: var(--ov-border-accent);
  background: var(--ov-bg-hover);
  color: var(--ov-primary-strong);
  box-shadow: none;
}

.app-button--primary:hover:not(:disabled) {
  color: var(--ov-text-on-primary);
  background: var(--ov-button-primary-hover);
  box-shadow: none;
}

.app-button:active:not(:disabled) {
  transform: scale(0.98);
}

.app-button:focus-visible {
  outline: 2px solid var(--ov-focus-ring);
  outline-offset: 2px;
}

.app-button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
  box-shadow: none;
}

.app-button__label {
  min-width: 0;
  max-width: 100%;
  overflow-wrap: anywhere;
  line-height: 1.25;
  white-space: normal;
}
</style>
