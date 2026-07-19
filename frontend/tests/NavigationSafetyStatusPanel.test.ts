import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import NavigationSafetyStatusPanel from "@/components/NavigationSafetyStatusPanel.vue";

describe("NavigationSafetyStatusPanel", () => {
  it("shows a passed L1 static registration gate without calling it degraded", () => {
    const wrapper = mount(NavigationSafetyStatusPanel, {
      props: {
        evidence: {
          navigation_level: "L1",
          navigation_ready: true,
          failure_reasons: [],
          microscope_pose_evidence: {
            magnification: 4,
            working_distance_mm: 250,
            calibration_status: "verified",
          },
        },
      },
    });

    expect(wrapper.text()).toContain("L1 · 静态配准验证");
    expect(wrapper.text()).toContain("静态配准证据已满足");
    expect(wrapper.text()).not.toContain("已降级为三维参考");
  });

  it("translates transform, coordinate-chain, error, and calibration-range failures", () => {
    const wrapper = mount(NavigationSafetyStatusPanel, {
      props: {
        evidence: {
          navigation_level: "L0",
          navigation_ready: false,
          failure_reasons: [
            "transform_sha256_mismatch",
            "transform_matrix_not_invertible",
            "coordinate_chain_discontinuous",
            "registration_error_threshold_exceeded",
            "magnification_out_of_calibration_range",
            "working_distance_calibration_range_missing",
            "reprojection_error_threshold_exceeded",
          ],
          camera_intrinsics_id: "scope_4x_250mm",
          reprojection_error_px: 3.4,
          reprojection_error_threshold_px: 2,
          camera_calibration_evidence: { artifact_validation: { valid: false } },
          threshold_approval: { status: "approved", protocol_version: "phantom_v1" },
          microscope_pose_evidence: {},
        },
      },
    });

    expect(wrapper.text()).toContain("变换文件校验码不一致");
    expect(wrapper.text()).toContain("变换矩阵不可逆");
    expect(wrapper.text()).toContain("坐标链不连续");
    expect(wrapper.text()).toContain("配准误差超限");
    expect(wrapper.text()).toContain("倍率超出标定范围");
    expect(wrapper.text()).toContain("工作距离标定范围缺失");
    expect(wrapper.text()).toContain("scope_4x_250mm");
    expect(wrapper.text()).toContain("3.40 px / 阈值 2.00 px");
    expect(wrapper.text()).toContain("独立重投影误差超限");
    expect(wrapper.text()).toContain("标定文件待核验");
    expect(wrapper.text()).toContain("phantom_v1 · 已批准");
  });

  it("translates temporal calibration failures after L2 falls back to L0", () => {
    const wrapper = mount(NavigationSafetyStatusPanel, {
      props: {
        evidence: {
          navigation_level: "L0",
          navigation_ready: false,
          failure_reasons: [
            "magnification_rate_exceeded",
            "working_distance_rate_exceeded",
            "calibration_switch_rate_exceeded",
            "calibration_selection_ambiguous",
            "calibration_selection_oscillation",
            "video_variable_frame_rate_unsupported",
          ],
          microscope_pose_evidence: {},
        },
      },
    });

    expect(wrapper.text()).toContain("倍率变化率超限");
    expect(wrapper.text()).toContain("工作距离变化率超限");
    expect(wrapper.text()).toContain("内参切换率超限");
    expect(wrapper.text()).toContain("标定选择存在歧义");
    expect(wrapper.text()).toContain("出现 A/B/A 内参振荡");
    expect(wrapper.text()).toContain("视频帧间隔不满足已验证恒定帧率门");
  });
});
