import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import L1RegistrationPanel from "@/components/L1RegistrationPanel.vue";
import { apiClient } from "@/services/apiClient";

describe("L1RegistrationPanel", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("submits traceable phantom points and keeps the L0 safety boundary visible", async () => {
    const start = vi.spyOn(apiClient, "startL1RegistrationJob").mockResolvedValue({ job_id: "job_l1", kind: "l1_static_registration", status: "queued" });
    vi.spyOn(apiClient, "getL1RegistrationJob").mockResolvedValue({ job_id: "job_l1", kind: "l1_static_registration", status: "completed", result: { registration_status: "registered" } });
    const wrapper = mount(L1RegistrationPanel, { props: { caseId: "case_001", evidence: { model_path: "artifacts/models/mandible.stl" } } });

    expect(wrapper.text()).toContain("L0 静态几何工程检查");
    expect(wrapper.text()).toContain("不能显示 L1 就绪状态");
    await wrapper.get("button").trigger("click");
    await wrapper.findAll("button").find((button) => button.text().includes("运行 L0"))!.trigger("click");
    await flushPromises();

    expect(start).toHaveBeenCalledWith(expect.objectContaining({
      case_id: "case_001",
      input_mode: "manual_metadata",
      model_path: "artifacts/models/mandible.stl",
      source_points: expect.any(Array),
      validation_source_points: [[10, 10, 10]],
      doctor_review_status: "review_required",
    }));
    expect(wrapper.emitted("completed")).toHaveLength(1);
  });

  it("rejects malformed point JSON before calling the backend", async () => {
    const start = vi.spyOn(apiClient, "startL1RegistrationJob");
    const wrapper = mount(L1RegistrationPanel, { props: { caseId: "case_001" } });
    await wrapper.findAll("button").find((button) => button.text().includes("运行 L0"))!.trigger("click");
    await flushPromises();
    expect(start).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("JSON");
  });

  it("submits calibrated PnP correspondences and an independent pixel gate", async () => {
    const start = vi.spyOn(apiClient, "startL1RegistrationJob").mockResolvedValue({ job_id: "job_pnp", kind: "l1_static_registration", status: "queued" });
    vi.spyOn(apiClient, "getL1RegistrationJob").mockResolvedValue({ job_id: "job_pnp", kind: "l1_static_registration", status: "completed", result: { registration_status: "registered" } });
    const wrapper = mount(L1RegistrationPanel, { props: { caseId: "case_pnp", evidence: { model_path: "artifacts/models/mandible.stl" } } });

    await wrapper.get('[data-testid="registration-method"]').setValue("rigid_points_with_pnp");
    await wrapper.findAll("button").find((button) => button.text().includes("载入固定仿体"))!.trigger("click");
    await wrapper.findAll("button").find((button) => button.text().includes("运行 L0"))!.trigger("click");
    await flushPromises();

    expect(start).toHaveBeenCalledWith(expect.objectContaining({
      registration_method: "rigid_points_with_pnp",
      camera_object_points: expect.arrayContaining([expect.any(Array)]),
      camera_image_points: expect.arrayContaining([expect.any(Array)]),
      validation_camera_object_points: expect.arrayContaining([expect.any(Array)]),
      validation_camera_image_points: expect.arrayContaining([expect.any(Array)]),
      camera_matrix: [[920, 0, 640], [0, 910, 360], [0, 0, 1]],
      distortion_coefficients: [0, 0, 0, 0, 0],
      image_size_px: [1280, 720],
      intrinsics_id: "scope_4x_250mm",
      reprojection_threshold_px: 2,
      camera_calibration_evidence: { artifact_path: "", artifact_sha256: "" },
      threshold_approval: expect.objectContaining({
        status: "pending",
        fre_threshold_mm: 1,
        tre_threshold_mm: 1,
        reprojection_threshold_px: 2,
      }),
    }));
  });

  it("submits a checksum-bound registration manifest for L1 evidence validation", async () => {
    const start = vi.spyOn(apiClient, "startL1RegistrationJob").mockResolvedValue({ job_id: "job_manifest", kind: "l1_static_registration", status: "queued" });
    vi.spyOn(apiClient, "getL1RegistrationJob").mockResolvedValue({ job_id: "job_manifest", kind: "l1_static_registration", status: "completed", result: { navigation_level: "L1" } });
    const wrapper = mount(L1RegistrationPanel, { props: { caseId: "case_manifest" } });
    const digest = "A".repeat(64);

    await wrapper.get('[data-testid="registration-input-mode"]').setValue("offline_manifest");
    await wrapper.get('[data-testid="registration-manifest-path"]').setValue("artifacts/navigation/registration_input.json");
    await wrapper.get('[data-testid="registration-manifest-sha256"]').setValue(digest);
    expect(wrapper.text()).toContain("L1 离线配准证据校验");
    await wrapper.findAll("button").find((button) => button.text().includes("运行 L1"))!.trigger("click");
    await flushPromises();

    expect(start).toHaveBeenCalledWith({
      case_id: "case_manifest",
      input_mode: "offline_manifest",
      registration_method: "rigid_points",
      unit: "mm",
      doctor_review_status: "review_required",
      registration_manifest_path: "artifacts/navigation/registration_input.json",
      registration_manifest_sha256: digest.toLowerCase(),
    });
    expect(wrapper.emitted("completed")).toHaveLength(1);
  });

  it("rejects an offline manifest without a valid SHA256", async () => {
    const start = vi.spyOn(apiClient, "startL1RegistrationJob");
    const wrapper = mount(L1RegistrationPanel, { props: { caseId: "case_manifest" } });

    await wrapper.get('[data-testid="registration-input-mode"]').setValue("offline_manifest");
    await wrapper.get('[data-testid="registration-manifest-path"]').setValue("registration_input.json");
    await wrapper.get('[data-testid="registration-manifest-sha256"]').setValue("invalid");
    await wrapper.findAll("button").find((button) => button.text().includes("运行 L1"))!.trigger("click");
    await flushPromises();

    expect(start).not.toHaveBeenCalled();
    expect(wrapper.get('[role="alert"]').text()).toContain("64 位十六进制摘要");
  });

  it("aborts the active poll and suppresses a stale completion after the case changes", async () => {
    let resolveJob: ((job: Awaited<ReturnType<typeof apiClient.getL1RegistrationJob>>) => void) | undefined;
    let pollSignal: AbortSignal | undefined;
    vi.spyOn(apiClient, "startL1RegistrationJob").mockResolvedValue({
      job_id: "job_old_case",
      kind: "l1_static_registration",
      status: "queued",
    });
    vi.spyOn(apiClient, "getL1RegistrationJob").mockImplementation((_jobId, signal) => {
      pollSignal = signal;
      return new Promise((resolve) => {
        resolveJob = resolve;
      });
    });
    const wrapper = mount(L1RegistrationPanel, { props: { caseId: "case_old" } });

    await wrapper.findAll("button").find((button) => button.text().includes("载入固定仿体"))!.trigger("click");
    await wrapper.findAll("button").find((button) => button.text().includes("运行 L0"))!.trigger("click");
    await flushPromises();
    expect(pollSignal?.aborted).toBe(false);

    await wrapper.setProps({ caseId: "case_new" });
    expect(pollSignal?.aborted).toBe(true);
    resolveJob?.({
      job_id: "job_old_case",
      kind: "l1_static_registration",
      status: "completed",
    });
    await flushPromises();

    expect(wrapper.emitted("completed")).toBeUndefined();
    expect(wrapper.text()).toContain("待运行");
  });

  it("clears the scheduled L1 poll when the panel unmounts", async () => {
    vi.useFakeTimers();
    let pollSignal: AbortSignal | undefined;
    vi.spyOn(apiClient, "startL1RegistrationJob").mockResolvedValue({
      job_id: "job_unmount",
      kind: "l1_static_registration",
      status: "queued",
    });
    const getJob = vi.spyOn(apiClient, "getL1RegistrationJob").mockImplementation((_jobId, signal) => {
      pollSignal = signal;
      return Promise.resolve({ job_id: "job_unmount", kind: "l1_static_registration", status: "running" });
    });
    const wrapper = mount(L1RegistrationPanel, { props: { caseId: "case_unmount" } });

    await wrapper.findAll("button").find((button) => button.text().includes("载入固定仿体"))!.trigger("click");
    await wrapper.findAll("button").find((button) => button.text().includes("运行 L0"))!.trigger("click");
    await flushPromises();
    expect(getJob).toHaveBeenCalledTimes(1);

    wrapper.unmount();
    expect(pollSignal?.aborted).toBe(true);
    await vi.advanceTimersByTimeAsync(1000);
    expect(getJob).toHaveBeenCalledTimes(1);
  });
});
