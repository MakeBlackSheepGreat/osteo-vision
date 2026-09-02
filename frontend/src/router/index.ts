import { createRouter, createWebHashHistory, createWebHistory } from "vue-router";

import { navigationMetaByPath } from "@/router/navigation";

export const router = createRouter({
  history: import.meta.env.VITE_OSTEO_DESKTOP === "true" ? createWebHashHistory() : createWebHistory(),
  routes: [
    { path: "/", redirect: "/case" },
    {
      path: "/cases",
      component: () => import("@/pages/CaseManagementPage.vue"),
      meta: { navigation: navigationMetaByPath["/cases"] },
    },
    {
      path: "/case",
      component: () => import("@/pages/CaseOpenPage.vue"),
      meta: { navigation: navigationMetaByPath["/case"] },
    },
    {
      path: "/data",
      component: () => import("@/pages/DataLibraryPage.vue"),
      meta: { navigation: navigationMetaByPath["/data"] },
    },
    {
      path: "/dataset-review",
      component: () => import("@/pages/DatasetReviewPage.vue"),
      meta: { navigation: navigationMetaByPath["/dataset-review"] },
    },
    {
      path: "/navigation",
      component: () => import("@/pages/NavigationWorkspacePage.vue"),
      meta: { navigation: navigationMetaByPath["/navigation"] },
    },
    {
      path: "/intake",
      component: () => import("@/pages/HospitalIntakePage.vue"),
      meta: { navigation: navigationMetaByPath["/intake"] },
    },
    {
      path: "/review",
      redirect: (to) => ({ path: "/annotations", query: to.query }),
    },
    {
      path: "/annotations",
      component: () => import("@/pages/ManualAnnotationPage.vue"),
      meta: { navigation: navigationMetaByPath["/annotations"] },
    },
    {
      path: "/report",
      component: () => import("@/pages/ReportPreviewPage.vue"),
      meta: { navigation: navigationMetaByPath["/report"] },
    },
    { path: "/:pathMatch(.*)*", redirect: "/case" },
  ],
});
