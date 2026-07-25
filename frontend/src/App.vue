<template>
  <div class="app-shell">
    <header class="app-top-nav" aria-label="顶部导航">
      <div class="app-top-nav__inner">
        <RouterLink class="app-brand" to="/case" aria-label="返回病例工作台">
          <AppIcon name="target" variant="badge" tone="cyan" />
          <span>
            <strong>OSTEO VISION</strong>
            <small>术中荧光辅助平台</small>
          </span>
        </RouterLink>
        <AppNavPills class="app-top-nav__pills" :items="navigationItems" aria-label="顶部导航" />
        <ThemeToggle class="app-top-nav__theme" />
      </div>
    </header>
    <router-view />
  </div>
</template>

<script setup lang="ts">
import AppIcon from "@/components/AppIcon.vue";
import AppNavPills from "@/components/AppNavPills.vue";
import ThemeToggle from "@/components/ThemeToggle.vue";
import { initializeTheme } from "@/composables/useTheme";
import { navigationItems } from "@/router/navigation";

initializeTheme();
</script>

<style scoped>
.app-shell {
  position: relative;
  min-height: 100dvh;
  background: var(--ov-shell-background);
}

.app-top-nav {
  position: sticky;
  z-index: 70;
  top: 0;
  right: 0;
  left: 0;
  border-bottom: 1px solid var(--ov-border-subtle);
  padding: 8px 0;
  background: var(--ov-top-nav-background);
  backdrop-filter: blur(14px);
}

.app-top-nav__inner {
  display: flex;
  gap: 14px;
  align-items: center;
  width: min(100%, var(--ov-content-wide));
  margin: 0 auto;
  padding: 0 var(--ov-page-inline);
}

.app-top-nav__pills {
  display: flex;
  flex: 1 1 auto;
  flex-wrap: wrap;
  gap: 4px;
  justify-content: flex-end;
  min-width: 0;
  pointer-events: auto;
}

.app-top-nav__theme {
  flex: 0 0 auto;
  align-self: center;
}

.app-top-nav__pills :deep(.ov-nav-pill) {
  gap: 6px;
  min-height: 36px;
  border-color: transparent;
  border-radius: 6px;
  padding: 7px 8px;
  background: transparent;
  color: var(--ov-nav-text);
  font-size: 13px;
  font-weight: 650;
  box-shadow: none;
}

.app-brand {
  display: inline-flex;
  flex: 0 0 auto;
  gap: 10px;
  align-items: center;
  color: var(--ov-text);
  text-decoration: none;
}

.app-brand :deep(.app-icon) {
  width: 34px;
  height: 34px;
}

.app-brand span {
  display: grid;
  gap: 1px;
}

.app-brand strong {
  color: var(--ov-text);
  font-size: 14px;
  font-weight: 750;
  line-height: 1.1;
}

.app-brand small {
  color: var(--ov-text-muted);
  font-size: 11px;
  font-weight: 600;
  line-height: 1.2;
}

.app-top-nav__pills :deep(.ov-nav-pill.router-link-active) {
  border-color: var(--ov-nav-border-active);
  background: var(--ov-nav-bg-active);
  color: var(--ov-nav-text-active);
  box-shadow: inset 0 -2px 0 var(--ov-nav-border-active);
}

.app-top-nav__pills :deep(.ov-nav-pill:hover) {
  transform: none;
  border-color: var(--ov-nav-border);
  background: var(--ov-nav-bg-hover);
  color: var(--ov-nav-text-active);
  box-shadow: none;
}

.app-top-nav__pills :deep(.app-icon) {
  width: 16px;
  height: 16px;
  color: var(--ov-nav-icon);
}

@media (max-width: 1120px) {
  .app-top-nav__inner {
    flex-wrap: wrap;
    gap: 8px 12px;
  }

  .app-top-nav__pills {
    order: 3;
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    width: 100%;
  }

  .app-top-nav__pills :deep(.ov-nav-pill) {
    justify-content: center;
    min-width: 0;
  }

  .app-top-nav__theme {
    margin-left: auto;
  }
}
</style>
