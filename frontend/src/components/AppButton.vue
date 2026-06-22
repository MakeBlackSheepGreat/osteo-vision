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
  --app-icon-bg: #ffffff;
  display: inline-flex;
  gap: 8px;
  align-items: center;
  justify-content: center;
  min-width: 0;
  border: 1px solid #9fc3e4;
  border-radius: 6px;
  background: #ffffff;
  color: #155f96;
  font: inherit;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0;
  text-decoration: none;
  white-space: nowrap;
  cursor: pointer;
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.94) inset,
    0 7px 16px rgba(20, 86, 138, 0.08);
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
  color: #ffffff;
}

.app-button--md {
  min-height: 36px;
  padding: 8px 12px;
}

.app-button--sm {
  min-height: 34px;
  padding: 7px 10px;
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
  --app-icon-bg: #1c75b7;
  border-color: #155f96;
  background: linear-gradient(180deg, #2f8dcc, #155f96);
  color: #ffffff;
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.28) inset,
    0 10px 20px rgba(21, 95, 150, 0.18);
}

.app-button--secondary {
  --app-icon-bg: #ffffff;
  border-color: #9fc3e4;
  background: linear-gradient(180deg, #ffffff, #f3f9ff);
  color: #155f96;
}

.app-button--ghost {
  --app-icon-bg: #edf7ff;
  border-color: #c4d9ec;
  background: #eef7ff;
  color: #216fa7;
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.9) inset;
}

.app-button:hover:not(:disabled) {
  transform: translateY(-1px);
  border-color: #2c7ec0;
  color: #0d5a91;
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.96) inset,
    0 10px 20px rgba(20, 86, 138, 0.13);
}

.app-button--primary:hover:not(:disabled) {
  color: #ffffff;
  background: linear-gradient(180deg, #3799d9, #1c70ad);
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.3) inset,
    0 12px 22px rgba(21, 95, 150, 0.24);
}

.app-button:active:not(:disabled) {
  transform: translateY(0) scale(0.99);
}

.app-button:focus-visible {
  outline: 2px solid rgba(44, 126, 192, 0.52);
  outline-offset: 2px;
}

.app-button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
  box-shadow: none;
}

.app-button__label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
