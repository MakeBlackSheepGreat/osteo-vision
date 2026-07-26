import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CandidateRegionList from "../src/components/CandidateRegionList.vue";
import ReviewWorkspacePage from "../src/pages/ReviewWorkspacePage.vue";
import { useCaseStore } from "../src/stores/caseStore";
import type { CandidateRegion, CaseRecord } from "../src/types/case";

describe("review workspace", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("marks the ROI surface empty until reviewable case output exists", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const wrapper = mountReviewWorkspace(pinia);

    expect(wrapper.get(".roi-canvas-stub").attributes("data-has-output")).toBe("false");
    expect(wrapper.get(".roi-canvas-stub").attributes("data-disabled")).toBe("true");

    const store = useCaseStore();
    store.currentCase = caseWithCandidate();
    await wrapper.vm.$nextTick();

    expect(wrapper.get(".roi-canvas-stub").attributes("data-has-output")).toBe("true");
    expect(wrapper.get(".roi-canvas-stub").attributes("data-disabled")).toBe("false");
  });

  it("loads the case identified by the navigation query before enabling review actions", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useCaseStore();
    vi.spyOn(store, "loadCase").mockImplementation(async (caseId) => {
      const loaded = { ...caseWithCandidate(), case_id: caseId };
      store.currentCase = loaded;
      return loaded;
    });
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/review", component: ReviewWorkspacePage }],
    });
    await router.push("/review?caseId=case_review_from_navigation");
    await router.isReady();

    const wrapper = mountReviewWorkspace(pinia, router);
    await flushPromises();

    expect(store.loadCase).toHaveBeenCalledWith("case_review_from_navigation");
    expect(wrapper.get(".roi-canvas-stub").attributes("data-disabled")).toBe("false");
    expect(wrapper.text()).toContain("病例 case_review_from_navigation 已载入");
  });

  it("renders store write failures in an assertive alert", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useCaseStore();
    store.currentCase = caseWithCandidate();
    const wrapper = mountReviewWorkspace(pinia);

    store.error = "候选区复核状态写入失败：后端不可用";
    await wrapper.vm.$nextTick();

    const alert = wrapper.get('[role="alert"]');
    expect(alert.attributes("aria-live")).toBe("assertive");
    expect(alert.text()).toContain("复核操作未完成");
    expect(alert.text()).toContain("候选区复核状态写入失败：后端不可用");
  });

  it("shows pending and success feedback for a candidate status write", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useCaseStore();
    store.currentCase = caseWithCandidate();
    let releaseWrite!: () => void;
    const updateSpy = vi.spyOn(store, "updateCandidateRegionState").mockImplementation(
      () => new Promise<void>((resolve) => {
        releaseWrite = resolve;
      }),
    );
    const wrapper = mountReviewWorkspace(pinia);

    wrapper.findComponent(CandidateRegionList).vm.$emit("updateCandidateStatus", "candidate_review_001", "accepted");
    await wrapper.vm.$nextTick();

    expect(wrapper.get('[role="status"]').text()).toContain("正在将候选区 candidate_review_001 更新为已接受");

    releaseWrite();
    await flushPromises();

    expect(updateSpy).toHaveBeenCalledWith("candidate_review_001", "accepted");
    expect(wrapper.get(".review-feedback--success").text()).toContain("候选区 candidate_review_001 已更新为已接受");
  });

  it("disables every candidate write action while a review write is loading", async () => {
    const wrapper = mount(CandidateRegionList, {
      props: {
        candidates: [candidateWithGeometry()],
        loading: true,
      },
    });

    const writeLabels = ["转为 ROI", "编辑框", "接受", "修改", "拒绝"];
    for (const label of writeLabels) {
      const button = wrapper.findAll("button").find((item) => item.text() === label);
      expect(button, `${label} button`).toBeDefined();
      expect((button!.element as HTMLButtonElement).disabled, `${label} button`).toBe(true);
    }

    await wrapper.get(".promote-button").trigger("click");
    expect(wrapper.emitted("promoteCandidate")).toBeUndefined();
  });

  it("prevents a candidate from being promoted to ROI more than once", async () => {
    const wrapper = mount(CandidateRegionList, {
      props: {
        candidates: [candidateWithGeometry()],
        promotedCandidateIds: ["candidate_review_001"],
      },
    });

    const promoteButton = wrapper.get(".promote-button");
    expect(promoteButton.text()).toBe("已转为 ROI");
    expect((promoteButton.element as HTMLButtonElement).disabled).toBe(true);
    expect(promoteButton.attributes("title")).toContain("已转为 ROI");

    await promoteButton.trigger("click");
    expect(wrapper.emitted("promoteCandidate")).toBeUndefined();
  });
});

function mountReviewWorkspace(pinia: ReturnType<typeof createPinia>, router?: ReturnType<typeof createRouter>) {
  const reviewRouter = router ?? createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", component: { template: "<div />" } },
      { path: "/review", component: ReviewWorkspacePage },
    ],
  });
  return mount(ReviewWorkspacePage, {
    global: {
      plugins: [pinia, reviewRouter],
      stubs: {
        AppPageHeader: true,
        CandidateRegionList: true,
        ReviewStateControls: true,
        QuantificationPanel: true,
        ReviewIdentityPanel: true,
        RoiCanvas: {
          props: ["hasOutput", "disabled"],
          template: '<div class="roi-canvas-stub" :data-has-output="String(hasOutput)" :data-disabled="String(disabled)" />',
        },
      },
    },
  });
}

function candidateWithGeometry(): CandidateRegion {
  return {
    candidate_id: "candidate_review_001",
    run_id: "run_review_001",
    risk_type: "boundary_risk",
    status: "review_required",
    metadata: {
      bbox_normalized: { x: 0.2, y: 0.2, width: 0.4, height: 0.4 },
    },
  };
}

function caseWithCandidate(): CaseRecord {
  return {
    case_id: "case_review_001",
    title: "医生复核病例",
    status: "analyzed",
    version: 1,
    disclaimer_version: "platform-safety-v1",
    review_summary: {},
    inputs: [],
    analysis_runs: [
      {
        run_id: "run_review_001",
        case_id: "case_review_001",
        parameters: {},
        status: "completed",
        candidate_regions: [
          {
            candidate_id: "candidate_review_001",
            run_id: "run_review_001",
            risk_type: "boundary_risk",
            status: "review_required",
            metadata: {},
          },
        ],
        fused_outputs: {},
        quantitative_summary: {},
        warnings: [],
      },
    ],
    rois: [],
    quality_flags: [],
    artifacts: [],
    warnings: [],
  };
}
