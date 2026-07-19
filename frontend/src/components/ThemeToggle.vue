<template>
  <button
    type="button"
    class="theme-toggle"
    :class="{ 'is-dark': isDark }"
    :title="actionLabel"
    :aria-label="actionLabel"
    :aria-pressed="isDark"
    @click="toggleTheme"
  >
    <AppIcon
      :name="isDark ? 'sun' : 'moon'"
      class="theme-toggle__icon"
      :class="`theme-toggle__icon--${isDark ? 'sun' : 'moon'}`"
    />
  </button>
</template>

<script setup lang="ts">
import { computed } from "vue";

import AppIcon from "@/components/AppIcon.vue";
import { useTheme } from "@/composables/useTheme";

const { isDark, toggleTheme } = useTheme();
const actionLabel = computed(() => (isDark.value ? "切换到日间模式" : "切换到夜间模式"));
</script>

<style scoped>
.theme-toggle {
  display: inline-grid;
  flex: 0 0 38px;
  place-items: center;
  width: 38px;
  height: 38px;
  border: 1px solid var(--ov-nav-border);
  border-radius: 6px;
  padding: 0;
  background: transparent;
  color: var(--ov-primary-strong);
  box-shadow: none;
  cursor: pointer;
  transition:
    transform 160ms ease,
    border-color 160ms ease,
    background 160ms ease,
    color 160ms ease,
    box-shadow 160ms ease;
}

.theme-toggle:hover {
  transform: none;
  border-color: var(--ov-nav-border-active);
  background: var(--ov-nav-bg-hover);
  color: var(--ov-nav-text-active);
}

.theme-toggle:focus-visible {
  outline: 2px solid var(--ov-border-accent);
  outline-offset: 2px;
}

.theme-toggle:active {
  transform: translateY(0);
}

.theme-toggle__icon {
  font-size: 18px;
  width: 18px;
  height: 18px;
}

.theme-toggle__icon--sun {
  color: var(--ov-warning);
}

@media (prefers-reduced-motion: reduce) {
  .theme-toggle {
    transition: none;
  }
}
</style>
