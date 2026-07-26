import { mount } from "@vue/test-utils";
import { defineComponent } from "vue";
import { describe, expect, it } from "vitest";

import App from "../src/App.vue";
import { router } from "../src/router";

const RouterLinkStub = defineComponent({
  props: {
    to: { type: [String, Object], required: true },
  },
  template: '<a :data-to="typeof to === \'string\' ? to : \'\'"><slot /></a>',
});

describe("App navigation", () => {
  it("follows the clinical workflow before research support pages", () => {
    const wrapper = mount(App, {
      global: {
        stubs: {
          RouterLink: RouterLinkStub,
          RouterView: true,
        },
      },
    });

    const items = wrapper.findAll(".ov-nav-pill").map((item) => ({
      label: item.text().trim(),
      to: item.attributes("data-to"),
    }));

    expect(items).toEqual([
      { label: "数据准入", to: "/intake" },
      { label: "病例档案", to: "/cases" },
      { label: "病例工作台", to: "/case" },
      { label: "三维导航", to: "/navigation" },
      { label: "人工标注与复核", to: "/annotations" },
      { label: "报告导出", to: "/report" },
      { label: "视频库", to: "/data" },
      { label: "静态数据复核", to: "/dataset-review" },
      { label: "工程展示", to: "/showcase" },
    ]);

    expect(wrapper.get(".app-top-nav").attributes("aria-label")).toBe("顶部导航");
    expect(wrapper.findAll(".ov-nav-pill .app-icon")).toHaveLength(9);
    expect(wrapper.find(".app-sidebar").exists()).toBe(false);
    expect(wrapper.find(".runtime-status").exists()).toBe(false);
    expect(wrapper.text()).not.toContain("比赛严格运行");
  });

  it("keeps every page lazy-loaded and recovers unknown URLs", () => {
    const routes = router.getRoutes();
    const pageRoutes = routes.filter((route) => route.path !== "/" && route.path !== "/:pathMatch(.*)*");

    expect(pageRoutes).toHaveLength(10);
    const renderedRoutes = pageRoutes.filter((route) => route.path !== "/review");
    expect(renderedRoutes.every((route) => typeof route.components?.default === "function")).toBe(true);
    expect(routes.find((route) => route.path === "/review")?.redirect).toBeTypeOf("function");
    expect(routes.find((route) => route.path === "/:pathMatch(.*)*")?.redirect).toBe("/case");
  });
});
