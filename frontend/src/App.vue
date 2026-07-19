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
        <AppNavPills class="app-top-nav__pills" :items="navItems" aria-label="顶部导航" />
        <ThemeToggle class="app-top-nav__theme" />
      </div>
    </header>
    <RuntimeStatusBanner @blocking-change="runtimeBlocked = $event" />
    <router-view v-if="!runtimeBlocked" />
    <main v-else class="runtime-blocked" role="alert">
      <AppIcon name="stop" variant="badge" tone="red" />
      <div>
        <strong>比赛工作流已锁定</strong>
        <p>请使用根目录严格比赛启动入口，并确认后端运行档位、模型和配置校验全部通过。</p>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";

import AppIcon from "@/components/AppIcon.vue";
import AppNavPills from "@/components/AppNavPills.vue";
import RuntimeStatusBanner from "@/components/RuntimeStatusBanner.vue";
import ThemeToggle from "@/components/ThemeToggle.vue";
import { initializeTheme } from "@/composables/useTheme";

initializeTheme();

const runtimeBlocked = ref(import.meta.env.VITE_OSTEO_EXPECT_STRICT_RUNTIME === "true");

const navItems = [
  { to: "/intake", label: "数据准入", icon: "upload" as const },
  { to: "/cases", label: "病例档案", icon: "case" as const },
  { to: "/case", label: "病例工作台", icon: "target" as const },
  { to: "/navigation", label: "三维导航", icon: "cube" as const },
  { to: "/review", label: "医生复核", icon: "review" as const },
  { to: "/annotations", label: "人工标注", icon: "brush" as const },
  { to: "/report", label: "报告导出", icon: "report" as const },
  { to: "/data", label: "视频库", icon: "video" as const },
  { to: "/dataset-review", label: "静态数据复核", icon: "brush" as const },
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
  border-bottom: 1px solid var(--ov-border-subtle);
  padding: 8px 0;
  background: var(--ov-top-nav-background);
  backdrop-filter: blur(14px);
}

.app-top-nav__inner {
  display: flex;
  gap: 18px;
  align-items: center;
  justify-content: flex-end;
  width: min(100%, var(--ov-content-wide));
  margin: 0 auto;
  padding: 0 var(--ov-page-inline);
}

.app-top-nav__pills {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
  pointer-events: auto;
}

.app-top-nav__theme {
  align-self: center;
}

.app-top-nav__pills :deep(.ov-nav-pill) {
  gap: 7px;
  min-width: 102px;
  min-height: 36px;
  border-color: transparent;
  border-radius: 6px;
  padding: 7px 10px;
  background: transparent;
  color: var(--ov-nav-text);
  font-size: 13px;
  font-weight: 650;
  box-shadow: none;
}

.app-brand {
  display: inline-flex;
  gap: 11px;
  align-items: center;
  margin-right: auto;
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

.runtime-blocked {
  display: flex;
  gap: 16px;
  align-items: center;
  justify-content: center;
  width: min(100%, 760px);
  min-height: 280px;
  margin: 48px auto;
  padding: 32px var(--ov-page-inline);
  color: var(--ov-text);
  text-align: left;
}

.runtime-blocked :deep(.app-icon) {
  flex: 0 0 auto;
  width: 42px;
  height: 42px;
}

.runtime-blocked div {
  display: grid;
  gap: 6px;
}

.runtime-blocked strong {
  font-size: 20px;
}

.runtime-blocked p {
  max-width: 620px;
  margin: 0;
  color: var(--ov-text-muted);
  line-height: 1.7;
}

@media (max-width: 1120px) {
  .app-top-nav {
    padding-top: 10px;
  }

  .app-top-nav__inner {
    flex-wrap: wrap;
    padding: 0 12px;
  }

  .app-top-nav__pills {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(146px, 1fr));
    gap: 8px;
    width: 100%;
  }


  .app-top-nav__theme {
    justify-self: end;
  }

  .app-top-nav__pills :deep(.ov-nav-pill) {
    min-height: 42px;
    padding: 9px 10px;
    font-size: 14px;
  }
}

</style>
