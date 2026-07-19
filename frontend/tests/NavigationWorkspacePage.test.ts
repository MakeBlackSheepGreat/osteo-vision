import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

import NavigationWorkspacePage from "../src/pages/NavigationWorkspacePage.vue";
import { useCaseStore } from "../src/stores/caseStore";

describe("NavigationWorkspacePage", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("reads candidates and registration evidence from the shared case store", async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: "/navigation", component: NavigationWorkspacePage },
        { path: "/case", component: { template: "<div />" } },
        { path: "/cases", component: { template: "<div />" } },
      ],
    });
    await router.push("/navigation?caseId=case_001");
    await router.isReady();

    const store = useCaseStore();
    store.currentCase = {
      case_id: "case_001",
      title: "术中病例 001",
      status: "analyzed",
      version: 1,
      disclaimer_version: "platform-safety-v1",
      review_summary: {},
      three_d_evidence: {
        model_path: "artifacts/models/case_001.stl",
        registration_status: "registered",
        registration_error_mm: 0.8,
        navigation_ready: true,
        navigation_level: "L2",
        failure_reasons: [],
        microscope_pose_evidence: {
          magnification: 10,
          working_distance_mm: 250,
          calibration_status: "valid",
          pose_tracking_status: "tracking",
          tre_mm: 0.8,
          tre_threshold_mm: 1.5,
          drift_mm: 0.2,
          drift_threshold_mm: 0.5,
        },
      },
      inputs: [
        {
          input_id: "input_video",
          channel: "video",
          path: "artifacts/uploads/case_001.mp4",
          mime_type: "video/mp4",
          dimensions: [3840, 2160],
          metadata: {},
          quality_flags: [],
        },
      ],
      analysis_runs: [
        {
          run_id: "run_001",
          case_id: "case_001",
          parameters: {},
          status: "completed",
          candidate_regions: [
            {
              candidate_id: "candidate_001",
              run_id: "run_001",
              risk_type: "boundary_risk",
              status: "review_required",
              metadata: { frame_key: "frame_8", frame_index: 8, timestamp_sec: 0.8 },
            },
          ],
          fused_outputs: { mode: "video_file_keyframes" },
          quantitative_summary: {},
          warnings: [],
        },
      ],
      rois: [],
      quality_flags: [],
      artifacts: [],
      warnings: [],
    };
    store.loadCase = vi.fn(async () => null);

    const wrapper = mount(NavigationWorkspacePage, {
      global: {
        plugins: [router],
        stubs: {
          Anatomy3DPanel: {
            props: ["caseId", "candidates", "metrics", "modeLabel", "threeDEvidence"],
            emits: ["selectCandidateFrame"],
            template: `
              <div class="three-d-stub">
                {{ caseId }} / {{ candidates.length }} / {{ modeLabel }}
                <button
                  type="button"
                  @click="$emit('selectCandidateFrame', { candidateId: 'candidate_001', frameKey: 'frame_8', frameIndex: 8, timestampSec: 0.8 })"
                >选择候选帧</button>
              </div>
            `,
          },
          AppIcon: true,
        },
      },
    });
    await flushPromises();

    expect(wrapper.get("h1").text()).toBe("病例三维导航工作台");
    expect(wrapper.text()).toContain("术中病例 001");
    expect(wrapper.text()).toContain("case_001.mp4");
    expect(wrapper.text()).toContain("1 个");
    expect(wrapper.text()).toContain("导航前置条件已记录");
    expect(wrapper.text()).toContain("配准误差 0.80 mm");
    expect(wrapper.text()).toContain("L2 · 动态 AR 验证");
    expect(wrapper.text()).toContain("0.80 mm / 阈值 1.50 mm");
    expect(wrapper.get(".three-d-stub").text()).toContain("case_001 / 1 / MP4 候选区空间证据");
    expect(wrapper.get(".navigation-workspace__back").attributes("href")).toContain("caseId=case_001");

    const pageSections = Array.from(wrapper.get("main").element.children);
    const safetyIndex = pageSections.indexOf(wrapper.get(".navigation-safety").element);
    const anatomyIndex = pageSections.indexOf(wrapper.get(".three-d-stub").element);
    const evidenceHeadingIndex = pageSections.indexOf(wrapper.get(".navigation-workspace__evidence-heading").element);
    const l1Index = pageSections.indexOf(wrapper.get(".l1-panel").element);
    const l2Index = pageSections.indexOf(wrapper.get(".l2-panel").element);
    expect(safetyIndex).toBeLessThan(anatomyIndex);
    expect(anatomyIndex).toBeLessThan(evidenceHeadingIndex);
    expect(evidenceHeadingIndex).toBeLessThan(l1Index);
    expect(l1Index).toBeLessThan(l2Index);

    store.currentCase.three_d_evidence = {
      ...store.currentCase.three_d_evidence,
      navigation_level: "L1",
      navigation_ready: true,
    };
    await flushPromises();
    expect(wrapper.text()).toContain("导航前置条件已记录");
    expect(wrapper.text()).toContain("L1 · 静态配准验证");

    await wrapper.get(".three-d-stub button").trigger("click");
    await flushPromises();
    expect(store.navigationFrameSelection).toMatchObject({
      caseId: "case_001",
      candidateId: "candidate_001",
      frameKey: "frame_8",
      frameIndex: 8,
      timestampSec: 0.8,
    });
    expect(router.currentRoute.value.query.frameKey).toBe("frame_8");
    expect(wrapper.get(".navigation-workspace__back").attributes("href")).toContain("frameKey=frame_8");
  });

  it("shows a case loading error even when no case could be loaded", async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: "/navigation", component: NavigationWorkspacePage },
        { path: "/case", component: { template: "<div />" } },
        { path: "/cases", component: { template: "<div />" } },
      ],
    });
    await router.push("/navigation");
    await router.isReady();

    const store = useCaseStore();
    store.currentCase = null;
    store.error = "病例读取失败，请检查病例编号。";

    const wrapper = mount(NavigationWorkspacePage, {
      global: {
        plugins: [router],
        stubs: {
          Anatomy3DPanel: { template: '<div data-testid="anatomy-3d-mounted" />' },
          AppIcon: true,
        },
      },
    });
    await flushPromises();

    expect(wrapper.get(".navigation-workspace__error").text()).toContain("病例读取失败");
    const workbench = wrapper.get(".navigation-empty-workbench");
    expect(workbench.text()).toContain("尚未载入病例");
    expect(workbench.find(".navigation-empty-workbench__imports").exists()).toBe(true);
    expect(workbench.find(".navigation-empty-workbench__tree").exists()).toBe(true);
    expect(workbench.find(".navigation-empty-workbench__viewport").exists()).toBe(true);
    expect(workbench.find(".navigation-empty-workbench__checks").exists()).toBe(true);
    expect(workbench.find(".navigation-empty-workbench__review").exists()).toBe(true);
    expect(workbench.get(".navigation-empty-workbench__notice > a").attributes("href")).toBe("/cases");
    expect(workbench.get('[data-state="awaiting-case"]').attributes("aria-label")).toBe("空三维视口");

    const caseActions = workbench.findAll('[data-requires-case="true"]');
    expect(caseActions.length).toBeGreaterThanOrEqual(6);
    for (const action of caseActions) {
      expect(action.attributes("disabled")).toBeDefined();
      expect(action.attributes("title")).toBe("请先载入病例");
    }
    expect(wrapper.find('[data-testid="anatomy-3d-mounted"]').exists()).toBe(false);
  });
});
