import { createRouter, createWebHistory } from "vue-router";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/case" },
    { path: "/cases", component: () => import("@/pages/CaseManagementPage.vue") },
    { path: "/case", component: () => import("@/pages/CaseOpenPage.vue") },
    { path: "/data", component: () => import("@/pages/DataLibraryPage.vue") },
    { path: "/dataset-review", component: () => import("@/pages/DatasetReviewPage.vue") },
    { path: "/navigation", component: () => import("@/pages/NavigationWorkspacePage.vue") },
    { path: "/intake", component: () => import("@/pages/HospitalIntakePage.vue") },
    { path: "/review", component: () => import("@/pages/ReviewWorkspacePage.vue") },
    { path: "/annotations", component: () => import("@/pages/ManualAnnotationPage.vue") },
    { path: "/report", component: () => import("@/pages/ReportPreviewPage.vue") },
    { path: "/:pathMatch(.*)*", redirect: "/case" },
  ],
});
