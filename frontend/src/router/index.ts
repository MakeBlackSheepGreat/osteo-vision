import { createRouter, createWebHistory } from "vue-router";

import CaseOpenPage from "@/pages/CaseOpenPage.vue";
import ReportPreviewPage from "@/pages/ReportPreviewPage.vue";
import ReviewWorkspacePage from "@/pages/ReviewWorkspacePage.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/case" },
    { path: "/case", component: CaseOpenPage },
    { path: "/review", component: ReviewWorkspacePage },
    { path: "/report", component: ReportPreviewPage },
  ],
});
