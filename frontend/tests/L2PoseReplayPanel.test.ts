import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";

import L2PoseReplayPanel from "@/components/L2PoseReplayPanel.vue";
import { apiClient } from "@/services/apiClient";
import type { CaseInputAsset, ThreeDEvidence } from "@/types/case";

const L1_TRANSFORM_SHA = "a".repeat(64);
const CALIBRATION_SHA = "b".repeat(64);
const VIDEO_SHA = "c".repeat(64);
const POSE_SHA = "d".repeat(64);

function l1Evidence(): ThreeDEvidence {
  return {
    navigation_ready: true,
    navigation_level: "L1",
    registration_status: "registered",
    transform_sha256: L1_TRANSFORM_SHA,
    camera_intrinsics_id: "scope_4x_300mm",
    reprojection_error_px: 0.31,
    reprojection_error_threshold_px: 1,
    camera_calibration_evidence: {
      artifact_path: "artifacts/navigation/calibration/scope_4x_300mm.json",
      artifact_sha256: CALIBRATION_SHA,
      artifact_validation: { valid: true, failure_reasons: [] },
    },
    threshold_approval: {
      status: "approved",
      protocol_version: "l1_phantom_v1",
      data_version: "phantom_set_v1",
    },
  };
}

function admittedVideo(): CaseInputAsset {
  return {
    input_id: "input_video_001",
    channel: "video",
    path: "artifacts/uploads/case_001.mp4",
    mime_type: "video/mp4",
    dimensions: [3840, 2160],
    metadata: {
      input_type: "video_file",
      sha256: VIDEO_SHA,
      frame_count: 90,
      fps: 30,
      authorization_status: "approved",
      deidentification_confirmed: true,
      intake_record_id: "intake_video_001",
      source_type: "institutional_handover",
      admission_status: "admitted",
      video_timestamp_source: "container_pts",
    },
    quality_flags: [],
  };
}

describe("L2PoseReplayPanel", () => {
  afterEach(() => vi.restoreAllMocks());

  it("keeps manual timestamps and calibration in pose-only engineering mode with an explicit L0 boundary", async () => {
    const start = vi.spyOn(apiClient, "startL2PoseReplayJob").mockResolvedValue({
      job_id: "job_pose_only",
      kind: "l2_offline_pose_replay",
      status: "queued",
    });
    vi.spyOn(apiClient, "getL2PoseReplayJob").mockResolvedValue({
      job_id: "job_pose_only",
      kind: "l2_offline_pose_replay",
      status: "completed",
      result: { navigation_ready: false, navigation_level: "L0", replay_mode: "pose_only_engineering" },
    });
    const wrapper = mount(L2PoseReplayPanel, {
      props: { caseId: "case_001", evidence: l1Evidence() },
    });

    expect(wrapper.get("[data-testid='pose-only-boundary']").text()).toContain("固定为 L0");
    expect(wrapper.text()).toContain("L1 标定证据已锁定");
    await wrapper.get("[data-testid='run-replay']").trigger("click");
    await flushPromises();

    expect(start).toHaveBeenCalledWith(expect.objectContaining({
      case_id: "case_001",
      replay_mode: "pose_only_engineering",
      input_mode: "manual_metadata",
      frame_timestamps_s: [0, 0.033, 0.066],
      poses: expect.any(Array),
      calibration_table: expect.any(Array),
      failure_injections: {},
      tre_proxy_threshold_mm: 2,
      dynamic_target_error_threshold_mm: 1.5,
      minimum_visible_projection_points: 3,
      doctor_review_status: "review_required",
    }));
    expect(wrapper.emitted("completed")).toHaveLength(1);
  });

  it("checksum-binds a pose-only offline manifest while keeping the result mode at L0", async () => {
    const start = vi.spyOn(apiClient, "startL2PoseReplayJob").mockResolvedValue({
      job_id: "job_pose_manifest",
      kind: "l2_offline_pose_replay",
      status: "queued",
    });
    vi.spyOn(apiClient, "getL2PoseReplayJob").mockResolvedValue({
      job_id: "job_pose_manifest",
      kind: "l2_offline_pose_replay",
      status: "completed",
      result: { navigation_ready: false, navigation_level: "L0", replay_mode: "pose_only_engineering" },
    });
    const wrapper = mount(L2PoseReplayPanel, {
      props: { caseId: "case_001", evidence: l1Evidence() },
    });

    await wrapper.get("[data-testid='input-mode']").setValue("offline_manifest");
    expect(wrapper.get("[data-testid='run-replay']").attributes("disabled")).toBeDefined();
    await wrapper.get("[data-testid='pose-only-manifest-path']").setValue("artifacts/navigation/pose_only.json");
    await wrapper.get("[data-testid='pose-only-manifest-sha256']").setValue(POSE_SHA);
    expect(wrapper.get("[data-testid='run-replay']").attributes("disabled")).toBeUndefined();

    await wrapper.get("[data-testid='run-replay']").trigger("click");
    await flushPromises();

    expect(start).toHaveBeenCalledWith(expect.objectContaining({
      replay_mode: "pose_only_engineering",
      input_mode: "offline_manifest",
      pose_manifest_path: "artifacts/navigation/pose_only.json",
      pose_manifest_sha256: POSE_SHA,
    }));
  });

  it("submits only transport fields for SHA-bound dynamic AR validation", async () => {
    const start = vi.spyOn(apiClient, "startL2PoseReplayJob").mockResolvedValue({
      job_id: "job_l2",
      kind: "l2_offline_pose_replay",
      status: "queued",
    });
    vi.spyOn(apiClient, "getL2PoseReplayJob").mockResolvedValue({
      job_id: "job_l2",
      kind: "l2_offline_pose_replay",
      status: "completed",
      result: { navigation_ready: true, navigation_level: "L2" },
    });
    const wrapper = mount(L2PoseReplayPanel, {
      props: {
        caseId: "case_001",
        evidence: l1Evidence(),
        videoInputs: [admittedVideo()],
        caseAdmissionStatus: "engineering_analysis_ready",
        caseAuthorizationStatus: "approved",
        caseDeidentificationConfirmed: true,
      },
    });

    await wrapper.get("[data-testid='replay-mode']").setValue("dynamic_ar_validation");
    await wrapper.get("[data-testid='video-input']").setValue("input_video_001");
    await wrapper.get("[data-testid='pose-manifest-path']").setValue("artifacts/navigation/pose_manifest.json");
    await wrapper.get("[data-testid='pose-manifest-sha256']").setValue(POSE_SHA);
    await wrapper.get("[data-testid='doctor-review-status']").setValue("accepted");

    expect(wrapper.get("[data-testid='input-mode']").attributes("disabled")).toBeDefined();
    expect(wrapper.get("[data-testid='video-sha256']").element).toHaveProperty("value", VIDEO_SHA);
    expect(wrapper.get("[data-testid='video-frame-count']").element).toHaveProperty("value", "90 帧");
    expect(wrapper.get("[data-testid='run-replay']").attributes("disabled")).toBeUndefined();

    await wrapper.get("[data-testid='run-replay']").trigger("click");
    await flushPromises();

    const payload = start.mock.calls[0][0];
    expect(payload).toEqual({
      case_id: "case_001",
      replay_mode: "dynamic_ar_validation",
      input_mode: "offline_manifest",
      video_input_id: "input_video_001",
      pose_manifest_path: "artifacts/navigation/pose_manifest.json",
      pose_manifest_sha256: POSE_SHA,
      doctor_review_status: "accepted",
    });
    expect(payload).not.toHaveProperty("frame_timestamps_s");
    expect(payload).not.toHaveProperty("calibration_table");
    expect(payload).not.toHaveProperty("max_time_offset_ms");
    expect(payload).not.toHaveProperty("drift_threshold_mm");
    expect(payload).not.toHaveProperty("tre_proxy_threshold_mm");
    expect(payload).not.toHaveProperty("dynamic_target_error_threshold_mm");
    expect(payload).not.toHaveProperty("minimum_visible_projection_points");
    expect(payload).not.toHaveProperty("l2_threshold_approval");
    expect(wrapper.text()).toContain("安全关键阈值与批准记录不能由客户端覆盖");
    expect(wrapper.emitted("completed")).toHaveLength(1);
  });

  it("blocks dynamic validation when the case has no admitted MP4 or complete L1 calibration", async () => {
    const wrapper = mount(L2PoseReplayPanel, {
      props: {
        caseId: "case_001",
        evidence: { navigation_ready: true, navigation_level: "L1", registration_status: "registered" },
        videoInputs: [{ ...admittedVideo(), metadata: { input_type: "video_file", frame_count: 90 } }],
      },
    });

    await wrapper.get("[data-testid='replay-mode']").setValue("dynamic_ar_validation");

    expect(wrapper.get("[data-testid='run-replay']").attributes("disabled")).toBeDefined();
    expect(wrapper.text()).toContain("等待完整 L1 安全证据");
    expect(wrapper.text()).toContain("当前病例没有可用于 L2 的已准入 MP4");
  });

  it("renders automatic timing, projection, drift, dynamic error, and artifact evidence", () => {
    const wrapper = mount(L2PoseReplayPanel, {
      props: {
        caseId: "case_001",
        evidence: {
          replay_mode: "dynamic_ar_validation",
          navigation_ready: true,
          navigation_level: "L2",
          video_evidence: {
            input_id: "input_video_001",
            sha256: VIDEO_SHA,
            frame_count: 90,
            timestamp_source: "container_pts",
          },
          overlay_evidence: {
            path: "artifacts/navigation/overlay.mp4",
            sha256: "e".repeat(64),
            frame_count: 90,
          },
          pose_replay_manifest_path: "artifacts/navigation/replay.json",
          pose_replay_manifest_sha256: "f".repeat(64),
          projection_evidence: { minimum_visible_count_observed: 270, point_count: 300 },
          l2_threshold_approval: {
            status: "approved",
            protocol_version: "dynamic_ar_protocol_v1.0",
            data_version: "phantom_video_set_v1",
            max_time_offset_ms: 50,
            max_magnification_rate_per_s: 25,
            max_working_distance_rate_mm_per_s: 600,
            max_intrinsics_switch_rate_hz: 10,
            calibration_ambiguity_margin: 0.05,
          },
          calibration_selection: {
            status: "passed",
            switch_count: 1,
            ambiguous_frame_count: 0,
            oscillation_count: 0,
            max_magnification_rate_per_s: 20,
            max_working_distance_rate_mm_per_s: 500,
            max_intrinsics_switch_rate_hz_observed: 10,
            approved_thresholds: {
              max_magnification_rate_per_s: 25,
              max_working_distance_rate_mm_per_s: 600,
              max_intrinsics_switch_rate_hz: 10,
              calibration_ambiguity_margin: 0.05,
            },
          },
          microscope_pose_evidence: {
            time_offset_ms: 4.2,
            drift_mm: 0.18,
            drift_threshold_mm: 1,
            tre_mm: 0.74,
            tre_threshold_mm: 1.2,
          },
        },
      },
    });

    expect(wrapper.text()).toContain("container_pts · 4.20 ms / 阈值 50.00 ms");
    expect(wrapper.text()).toContain("0.18 mm / 阈值 1.00 mm");
    expect(wrapper.text()).toContain("0.74 mm / 阈值 1.20 mm");
    expect(wrapper.text()).toContain("每帧最少可见 270/300 点");
    expect(wrapper.get("[data-testid='temporal-safety-gate']").text()).toBe("已通过连续性检查");
    expect(wrapper.get("[data-testid='intrinsics-switch-summary']").text()).toBe("1 次 · 峰值 10.00 Hz / 阈值 10.00 Hz");
    expect(wrapper.get("[data-testid='magnification-rate-summary']").text()).toBe("20.00 ×/s / 阈值 25.00 ×/s");
    expect(wrapper.get("[data-testid='working-distance-rate-summary']").text()).toBe("500.00 mm/s / 阈值 600.00 mm/s");
    expect(wrapper.get("[data-testid='calibration-ambiguity-summary']").text()).toBe("0 帧 · 未检出标定选择歧义");
    expect(wrapper.get("[data-testid='calibration-oscillation-summary']").text()).toBe("0 次 · 未检出A/B/A 内参振荡");
    expect(wrapper.text()).toContain("overlay.mp4");
    expect(wrapper.text()).toContain("dynamic_ar_protocol_v1.0 · phantom_video_set_v1");
  });

  it("shows calibration ambiguity and A/B/A oscillation as a failed-closed L0 result", () => {
    const wrapper = mount(L2PoseReplayPanel, {
      props: {
        caseId: "case_001",
        evidence: {
          replay_mode: "dynamic_ar_validation",
          navigation_ready: false,
          navigation_level: "L0",
          fallback_mode: "unregistered_3d_reference",
          failure_reasons: [
            "calibration_selection_ambiguous",
            "calibration_selection_oscillation",
          ],
          pose_replay_manifest_path: "artifacts/navigation/failed_replay.json",
          calibration_transition_summary: {
            status: "failed_closed",
            switch_count: 2,
            ambiguous_frame_count: 1,
            oscillation_count: 1,
            max_magnification_rate_per_s: 40,
            max_working_distance_rate_mm_per_s: 1500,
            max_intrinsics_switch_rate_hz_observed: 20,
            approved_thresholds: {
              max_magnification_rate_per_s: 25,
              max_working_distance_rate_mm_per_s: 600,
              max_intrinsics_switch_rate_hz: 10,
              calibration_ambiguity_margin: 0.05,
            },
            failure_reasons: [
              "calibration_selection_ambiguous",
              "calibration_selection_oscillation",
            ],
          },
        },
      },
    });

    expect(wrapper.get("[data-testid='temporal-safety-gate']").text()).toBe("已失败闭合 · L2 已撤销并回退 L0");
    expect(wrapper.get("[data-testid='intrinsics-switch-summary']").text()).toBe("2 次 · 峰值 20.00 Hz / 阈值 10.00 Hz");
    expect(wrapper.get("[data-testid='calibration-ambiguity-summary']").text()).toBe("1 帧 · 已触发失败闭合");
    expect(wrapper.get("[data-testid='calibration-oscillation-summary']").text()).toBe("1 次 · 已触发失败闭合");
    expect(wrapper.get("[data-testid='temporal-failure-closure']").text()).toContain("标定选择存在歧义、出现 A/B/A 内参振荡");
    expect(wrapper.get("[data-testid='temporal-failure-closure']").text()).toContain("本次 L2 已撤销并回退 L0 未配准三维参考");
  });
});
