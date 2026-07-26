import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";

import ThreeDEvidenceControlPanel from "@/components/ThreeDEvidenceControlPanel.vue";
import { apiClient } from "@/services/apiClient";

describe("ThreeDEvidenceControlPanel", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it("uploads CBCT data, submits the case-bound modeling job, and emits after persistence", async () => {
    const file = new File(["cbct-volume"], "case_001.nii", { type: "application/octet-stream" });
    const upload = vi.spyOn(apiClient, "uploadThreeDAsset").mockResolvedValue({
      path: "artifacts/uploads/case_001.nii",
      filename: "case_001.nii",
      original_filename: "case_001.nii",
      content_type: "application/octet-stream",
      size_bytes: file.size,
      sha256: "a".repeat(64),
    });
    const start = vi.spyOn(apiClient, "startThreeDModelingJob").mockResolvedValue({
      job_id: "job_cbct_001",
      kind: "cbct_surface_modeling",
      status: "queued",
    });
    vi.spyOn(apiClient, "getThreeDModelingJob").mockResolvedValue({
      job_id: "job_cbct_001",
      kind: "cbct_surface_modeling",
      status: "completed",
      result: {
        message: "模型证据已持久化。",
        three_d_evidence: {
          model_path: "artifacts/models/case_001.stl",
          registration_status: "unregistered",
          navigation_level: "L0",
          navigation_ready: false,
          doctor_review_status: "review_required",
          boundary_note: "建模结果需保留医生复核和未配准参考边界。",
        },
        case_persistence: { status: "persisted", case_id: "case_001", case_version: 2 },
      },
    });
    const wrapper = mount(ThreeDEvidenceControlPanel, { props: { caseId: "case_001" } });

    await selectFiles(wrapper, '[data-testid="cbct-file-input"]', [file]);
    await flushPromises();

    expect(upload).toHaveBeenCalledWith(file);
    expect(wrapper.text()).toContain("已写入后端");
    expect(wrapper.get('[data-testid="submit-modeling-job"]').attributes("disabled")).toBeUndefined();

    await wrapper.get('[data-testid="submit-modeling-job"]').trigger("click");
    await flushPromises();

    expect(start).toHaveBeenCalledWith(expect.objectContaining({
      case_id: "case_001",
      source_path: "artifacts/uploads/case_001.nii",
      source_paths: ["artifacts/uploads/case_001.nii"],
      source_role: "volume",
      source_original_filename: "case_001.nii",
    }));
    expect(wrapper.emitted("evidencePersisted")).toHaveLength(1);
    expect(wrapper.text()).toContain("模型证据已持久化。");
    expect(wrapper.text()).toContain("L0 未配准参考");
    expect(wrapper.find('[data-testid="modeling-progress"]').exists()).toBe(true);
    expect(wrapper.get('[data-testid="modeling-percent"]').text()).toBe("100%");
    expect(wrapper.get('[data-testid="modeling-phase"]').text()).toBe("建模完成");
    expect(wrapper.text()).toContain("case_001.nii");

    await wrapper.setProps({
      evidence: {
        model_path: "artifacts/models/case_001_reviewed.stl",
        registration_status: "registered",
        navigation_level: "L1",
        navigation_ready: true,
        doctor_review_status: "reviewed",
        boundary_note: "父级刷新后的权威三维证据。",
      },
    });

    expect(wrapper.text()).toContain("父级刷新后的权威三维证据。");
    expect(wrapper.text()).toContain("已记录工程配准");
    expect(wrapper.text()).not.toContain("建模结果需保留医生复核和未配准参考边界。");
  });

  it("cancels a still-running surface-model task without retaining the active polling session", async () => {
    const file = new File(["surface"], "mandible.glb", { type: "model/gltf-binary" });
    vi.spyOn(apiClient, "uploadThreeDAsset").mockResolvedValue({
      path: "artifacts/uploads/mandible.glb",
      filename: "mandible.glb",
      original_filename: "mandible.glb",
      content_type: "model/gltf-binary",
      size_bytes: file.size,
      sha256: "b".repeat(64),
    });
    vi.spyOn(apiClient, "startThreeDModelingJob").mockResolvedValue({
      job_id: "job_surface_001",
      kind: "cbct_surface_modeling",
      status: "queued",
    });
    const getJob = vi.spyOn(apiClient, "getThreeDModelingJob").mockResolvedValue({
      job_id: "job_surface_001",
      kind: "cbct_surface_modeling",
      status: "running",
      progress: {
        phase: "verify_surface",
        percent: 72,
        message: "正在检查表面模型。",
        details: { current_file: "mandible.glb" },
      },
      created_at: new Date(Date.now() - 12_000).toISOString(),
    });
    const cancel = vi.spyOn(apiClient, "cancelThreeDModelingJob").mockResolvedValue({
      job_id: "job_surface_001",
      kind: "cbct_surface_modeling",
      status: "canceled",
      progress: { message: "任务已取消。" },
    });
    const wrapper = mount(ThreeDEvidenceControlPanel, { props: { caseId: "case_surface" } });

    await selectFiles(wrapper, '[data-testid="surface-file-input"]', [file]);
    await flushPromises();
    await wrapper.get('[data-testid="submit-modeling-job"]').trigger("click");
    await flushPromises();

    expect(getJob).toHaveBeenCalledWith("job_surface_001");
    expect(wrapper.findAll('[data-testid="cancel-modeling-job"]')).toHaveLength(1);
    expect(wrapper.get('[data-testid="modeling-percent"]').text()).toBe("72%");
    expect(wrapper.get('[data-testid="modeling-phase"]').text()).toBe("校验表面模型");
    expect(wrapper.get('[data-testid="modeling-elapsed"]').text()).toContain("12 秒");
    expect(wrapper.text()).toContain("mandible.glb");

    await wrapper.get('[data-testid="cancel-modeling-job"]').trigger("click");
    await flushPromises();

    expect(cancel).toHaveBeenCalledWith("job_surface_001");
    expect(wrapper.text()).toContain("已取消");
    expect(wrapper.findAll('[data-testid="cancel-modeling-job"]')).toHaveLength(0);
  });

  it("restores a persisted modeling job after the page is remounted", async () => {
    window.localStorage.setItem("osteo-vision-three-d-modeling-job:case_restore", "job_restore_001");
    const getJob = vi.spyOn(apiClient, "getThreeDModelingJob").mockResolvedValue({
      job_id: "job_restore_001",
      kind: "cbct_surface_modeling",
      status: "completed",
      progress: {
        phase: "completed",
        percent: 100,
        message: "三维建模已完成。",
        details: { current_file: "restored_surface.stl" },
      },
      created_at: "2026-07-26T08:00:00Z",
      updated_at: "2026-07-26T08:02:05Z",
      result: {
        three_d_evidence: {
          model_path: "artifacts/models/restored_surface.stl",
          navigation_level: "L0",
          navigation_ready: false,
        },
      },
    });

    const wrapper = mount(ThreeDEvidenceControlPanel, { props: { caseId: "case_restore" } });
    await flushPromises();

    expect(getJob).toHaveBeenCalledWith("job_restore_001");
    expect(wrapper.get('[data-testid="modeling-percent"]').text()).toBe("100%");
    expect(wrapper.get('[data-testid="modeling-phase"]').text()).toBe("建模完成");
    expect(wrapper.get('[data-testid="modeling-elapsed"]').text()).toBe("2 分 5 秒");
    expect(wrapper.text()).toContain("restored_surface.stl");
  });

  it("renders a single panel section for the stable three-column navigation workbench", () => {
    const wrapper = mount(ThreeDEvidenceControlPanel, {
      props: {
        caseId: "case_panel",
        presentation: "panel",
        sections: ["imports"],
      },
    });

    expect(wrapper.classes()).toContain("three-d-evidence-control--panel");
    expect(wrapper.find(".three-d-evidence-control__header").exists()).toBe(false);
    expect(wrapper.find('[aria-label="三维文件导入"]').exists()).toBe(true);
    expect(wrapper.find('[aria-label="三维对象树"]').exists()).toBe(false);
    expect(wrapper.find('[aria-label="三维建模检查"]').exists()).toBe(false);
  });
});

async function selectFiles(wrapper: ReturnType<typeof mount>, selector: string, files: File[]) {
  const input = wrapper.get<HTMLInputElement>(selector);
  Object.defineProperty(input.element, "files", { configurable: true, value: files });
  await input.trigger("change");
}
