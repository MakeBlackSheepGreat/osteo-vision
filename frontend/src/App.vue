<template>
  <div class="app-shell">
    <header class="app-top-nav" aria-label="顶部导航">
      <div class="app-top-nav__inner">
        <AppNavPills class="app-top-nav__pills" :items="navItems" aria-label="顶部导航" />
      </div>
    </header>
    <router-view />
  </div>
</template>

<script setup lang="ts">
import AppNavPills from "@/components/AppNavPills.vue";

const navItems = [
  { to: "/case", label: "病例工作台", icon: "target" as const },
  { to: "/cases", label: "病例档案", icon: "case" as const },
  { to: "/data", label: "视频库", icon: "video" as const },
  { to: "/review", label: "医生复核", icon: "review" as const },
  { to: "/report", label: "报告导出", icon: "report" as const },
];
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
  padding: 12px 0 8px;
  background: var(--ov-top-nav-background);
  backdrop-filter: blur(14px);
}

.app-top-nav__inner {
  display: flex;
  justify-content: flex-end;
  width: min(100%, 1540px);
  margin: 0 auto;
  padding: 0 28px;
}

.app-top-nav__pills {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
  pointer-events: auto;
}

.app-top-nav__pills :deep(.ov-nav-pill) {
  gap: 8px;
  min-width: 126px;
  min-height: 40px;
  border-color: var(--ov-nav-border);
  border-radius: 7px;
  padding: 8px 13px;
  background: var(--ov-nav-bg);
  color: var(--ov-nav-text);
  font-size: 15px;
  font-weight: 900;
  box-shadow: var(--ov-nav-shadow);
  backdrop-filter: blur(12px);
}

.app-top-nav__pills :deep(.ov-nav-pill.router-link-active) {
  border-color: var(--ov-nav-border-active);
  background: var(--ov-nav-bg-active);
  color: var(--ov-nav-text-active);
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.16) inset,
    0 0 0 1px rgba(116, 215, 255, 0.12),
    0 0 26px rgba(74, 203, 255, 0.22);
}

.app-top-nav__pills :deep(.ov-nav-pill:hover) {
  transform: translateY(-1px);
  border-color: var(--ov-nav-border-active);
  color: var(--ov-nav-text-active);
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.1) inset,
    0 10px 24px rgba(0, 0, 0, 0.28),
    0 0 24px rgba(74, 203, 255, 0.2);
}

.app-top-nav__pills :deep(.app-icon) {
  width: 16px;
  height: 16px;
  color: var(--ov-nav-icon);
}

@media (max-width: 1120px) {
  .app-top-nav {
    padding-top: 10px;
  }

  .app-top-nav__inner {
    padding: 0 12px;
  }

  .app-top-nav__pills {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(146px, 1fr));
    gap: 8px;
    width: 100%;
  }

  .app-top-nav__pills :deep(.ov-nav-pill) {
    min-height: 42px;
    padding: 9px 10px;
    font-size: 14px;
  }
}

@media (min-width: 861px) and (max-width: 1120px) {
  .app-top-nav__pills {
    display: flex;
    width: auto;
  }
}
</style>
