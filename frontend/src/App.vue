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
  { to: "/review", label: "医生复核", icon: "review" as const },
  { to: "/report", label: "报告导出", icon: "report" as const },
];
</script>

<style scoped>
.app-shell {
  position: relative;
  min-height: 100dvh;
}

.app-top-nav {
  position: absolute;
  z-index: 70;
  top: 25px;
  right: 0;
  left: 0;
  pointer-events: none;
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
  border-color: #a8c4dd;
  border-radius: 7px;
  padding: 8px 13px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(244, 249, 255, 0.94));
  color: #24445f;
  font-size: 15px;
  font-weight: 900;
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.9) inset,
    0 7px 16px rgba(20, 86, 138, 0.06);
}

.app-top-nav__pills :deep(.ov-nav-pill.router-link-active) {
  border-color: #155f96;
  background: linear-gradient(180deg, #f1f9ff, #dceeff);
  color: #155f96;
}

.app-top-nav__pills :deep(.ov-nav-pill:hover) {
  transform: translateY(-1px);
  border-color: #2c7ec0;
  color: #155f96;
}

.app-top-nav__pills :deep(.app-icon) {
  width: 16px;
  height: 16px;
}

@media (max-width: 1120px) {
  .app-top-nav {
    position: static;
    padding-top: 10px;
  }

  .app-top-nav__inner {
    padding: 0 12px;
  }

  .app-top-nav__pills {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
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
