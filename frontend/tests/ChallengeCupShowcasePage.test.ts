import { mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";
import { describe, expect, it } from "vitest";

import ChallengeCupShowcasePage from "../src/pages/ChallengeCupShowcasePage.vue";

describe("ChallengeCupShowcasePage", () => {
  it("presents the four-stage evidence chain and switches real evidence layers", async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: "/showcase", component: ChallengeCupShowcasePage },
        { path: "/case", component: { template: "<main />" } },
        { path: "/navigation", component: { template: "<main />" } },
      ],
    });
    await router.push("/showcase");
    await router.isReady();

    const wrapper = mount(ChallengeCupShowcasePage, {
      global: {
        plugins: [router],
        stubs: {
          ThreeDRendererRuntimeEmbed: {
            props: ["referenceId"],
            template: '<div class="three-d-runtime-stub">{{ referenceId }} / 独立三维渲染</div>',
          },
          AppIcon: true,
        },
      },
    });

    expect(wrapper.get("h1").text()).toBe("荧光-三维证据闭环工作站");
    expect(wrapper.text()).toContain("三维参考与复核规划");
    expect(wrapper.text()).toContain("荧光融合与 AI 候选提示");
    expect(wrapper.text()).toContain("离线空间链验证");
    expect(wrapper.text()).toContain("医生复核与安全降级");
    expect(wrapper.get(".three-d-runtime-stub").text()).toContain("d024 / 独立三维渲染");
    expect(wrapper.get(".showcase-vision-frame img").attributes("src")).toBe("/showcase/d083_frame_05_overlay.png");
    expect(wrapper.text()).toContain("D083，CC BY 4.0");
    expect(wrapper.text()).toContain("L0 未配准参考");
    expect(wrapper.text()).toContain("工程复核方案快照");
    expect(wrapper.get(".showcase-planning-snapshot__detail").text()).toContain("公开解剖参考");
    expect(wrapper.text()).toContain("离线空间工程验证");
    expect(wrapper.text()).toContain("静态数字仿体配准");
    expect(wrapper.text()).toContain("离线动态 AR 回放");
    expect(wrapper.text()).toContain("当前挑战杯展示状态");
    expect(wrapper.text()).toContain("回顾验证与证据回流");
    expect(wrapper.text()).toContain("来源 + SHA256");

    const rawButton = wrapper.get('[aria-label="关键帧证据图层"] [role="tab"]:first-child');
    await rawButton.trigger("click");

    expect(rawButton.attributes("aria-selected")).toBe("true");
    expect(wrapper.get(".showcase-vision-frame img").attributes("src")).toBe("/showcase/d083_frame_05_raw.jpg");

    const guardButton = wrapper.get('[aria-label="术前工程复核焦点"] [role="tab"]:nth-child(3)');
    await guardButton.trigger("click");

    expect(guardButton.attributes("aria-selected")).toBe("true");
    expect(wrapper.get(".showcase-planning-snapshot__detail").text()).toContain("空间安全门控");
    expect(wrapper.get(".showcase-planning-snapshot__detail").text()).toContain("L0 未配准参考 / 非导航");
    expect(wrapper.get(".showcase-page__actions a").attributes("href")).toBe("/case");
  });
});
