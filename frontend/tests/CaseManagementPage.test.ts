import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CaseManagementPage from "../src/pages/CaseManagementPage.vue";
import { apiClient } from "../src/services/apiClient";
import { useCaseStore } from "../src/stores/caseStore";
import type { CaseRecord } from "../src/types/case";

const demoCases = ["张三", "李四", "王五", "赵六", "陈七"].map((name, index) => ({
  case_id: `case_demo_${index + 1}`,
  title: `${name} · 工程演示病例`,
  status: "draft" as const,
  version: 1,
  created_at: "2026-07-26T10:00:00Z",
  updated_at: "2026-07-26T10:00:00Z",
  disclaimer_version: "platform-safety-v1",
  clinical_context: {},
  review_summary: { display_name_is_synthetic: true },
  three_d_evidence: {},
  three_d_modeling: {},
  inputs: [],
  analysis_runs: [],
  review_events: [],
  artifacts: [],
  rois: [],
  quality_flags: [],
  warnings: [],
  disclaimer: null,
})) as unknown as CaseRecord[];

describe("CaseManagementPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("initializes and shows the five demo cases, then selects the first case", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const legacyCase = { ...demoCases[0], case_id: "case_legacy", title: "旧工程病例" };
    vi.spyOn(apiClient, "ensureDemoCases").mockResolvedValue(demoCases);
    vi.spyOn(apiClient, "listCases").mockResolvedValue([legacyCase, ...demoCases]);
    vi.spyOn(apiClient, "getCase").mockResolvedValue(demoCases[0]);

    const wrapper = mount(CaseManagementPage, {
      global: {
        plugins: [pinia],
        stubs: {
          AppPageShell: { template: "<main><slot /></main>" },
          AppPageHeader: { template: "<header><slot /><slot name=\"actions\" /></header>" },
          AppButton: { template: "<button type=\"button\"><slot /></button>" },
          AppIcon: true,
          RouterLink: { template: "<a><slot /></a>" },
        },
      },
    });
    await flushPromises();

    expect(apiClient.ensureDemoCases).toHaveBeenCalledOnce();
    expect(apiClient.listCases).toHaveBeenCalledOnce();
    expect(apiClient.getCase).toHaveBeenCalledWith("case_demo_1");
    expect(wrapper.findAll("option")).toHaveLength(6);
    for (const name of ["张三", "李四", "王五", "赵六", "陈七"]) {
      expect(wrapper.text()).toContain(name);
    }
    expect(wrapper.findAll("option")[0].text()).toContain("张三");
    expect(wrapper.findAll("option")[5].text()).toContain("旧工程病例");
    expect((wrapper.find("select").element as HTMLSelectElement).value).toBe("case_demo_1");
    expect(useCaseStore().currentCase?.case_id).toBe("case_demo_1");
  });
});
