import { createRouter, createWebHistory } from "vue-router";

import { navigationMetaByPath } from "@/router/navigation";

export const router = createRouter({
  history: createWebHistory(),
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
      component: () => import("@/pages/ReviewWorkspacePage.vue"),
      meta: { navigation: navigationMetaByPath["/review"] },
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
    {
      path: "/showcase",
      component: () => import("@/pages/ChallengeCupShowcasePage.vue"),
      meta: { navigation: navigationMetaByPath["/showcase"] },
    },
    { path: "/:pathMatch(.*)*", redirect: "/case" },
  ],
});
