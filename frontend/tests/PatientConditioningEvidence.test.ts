import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import PatientConditioningEvidencePanel from "@/components/PatientConditioningEvidencePanel.vue";
import { patientConditioningEvidenceForFrame } from "@/utils/patientConditioningEvidence";

describe("PatientConditioningEvidencePanel", () => {
  it("renders baseline, conditioned, difference, uncertainty, and fail-closed evidence", () => {
    const wrapper = mount(PatientConditioningEvidencePanel, {
      props: {
        evidence: {
          model_id: "patient-conditioned-v1",
          spatial_effect_applied: false,
          difference_area_px: 0,
          difference_area_fraction: 0,
          effective_present_fraction: 0.8,
          target_domain_promotion_ready: false,
          physician_reviewed_bone_gate: true,
          clinical_context_checksum: "abc123",
          clinical_feature_vector: {
            schema_version: "osteo-vision-clinical-feature-vector-v1",
            feature_version: "clinical-feature-vector-v1",
            feature_names: [
              "age_years",
              "sex_at_birth_female",
              "diabetes",
              "renal_disease",
              "egfr_ml_min_1_73m2",
            ],
            present_mask: [true, true, true, false, false],
            missing_mask: [false, false, false, true, false],
            ood_mask: [false, false, false, false, true],
            checkpoint_consumed_mask: [true, true, true, false, false],
            spatial_effect_applied_mask: [false, false, false, false, false],
            recorded_input_summary: {
              age_recorded: true,
              sex_recorded: true,
              comorbidity_record_count: 2,
              comorbidities_reviewed: true,
              medication_record_count: 1,
              medications_reviewed: true,
              lab_record_count: 3,
              eligible_lab_record_count: 1,
            },
            checkpoint_consumed_feature_names: ["age_years", "sex_at_birth_female", "diabetes"],
            spatially_applied_feature_names: [],
            missing_feature_names: ["renal_disease"],
            ood_feature_names: ["egfr_ml_min_1_73m2"],
            unconsumed_recorded_inputs: [
              {
                input_domain: "medications",
                record_count: 1,
                reason_codes: ["checkpoint_declares_no_medication_features"],
              },
              {
                input_domain: "laboratory_results",
                record_count: 2,
                reason_codes: ["recorded_lab_not_consumed_by_checkpoint"],
              },
            ],
            vector_checksum: "vector-checksum",
            runtime_vector_checksum: "runtime-vector-checksum",
          },
          failure_reasons: [
            "model_target_domain_promotion_missing",
            "dual_channel_registration_unverified",
            "clinical_spatial_conditioning_not_authorized",
            "physician_reviewed_bone_gate_untrusted",
            "target_domain_input_not_verified",
          ],
          outputs: {
            image_only_probability_path: "base.png",
            conditioned_probability_path: "conditioned.png",
            difference_mask_path: "difference.png",
            uncertainty_path: "uncertainty.png",
          },
        },
        previewUrl: (path: string) => `/preview/${path}`,
        downloadUrl: (path: string) => `/download/${path}`,
      },
    });

    expect(wrapper.text()).toContain("患者条件分割对照");
    expect(wrapper.text()).toContain("已回退影像基础结果");
    expect(wrapper.text()).toContain("患者条件模型尚未通过目标域晋级");
    expect(wrapper.text()).toContain("白光与荧光配准证据未通过安全门");
    expect(wrapper.text()).toContain("患者变量尚未获准参与空间调制");
    expect(wrapper.text()).toContain("骨面掩膜缺少可信医生复核");
    expect(wrapper.text()).toContain("当前输入尚未通过目标域数据准入");
    expect(wrapper.text()).toContain("临床特征向量");
    expect(wrapper.text()).toContain("已录入5 类");
    expect(wrapper.text()).toContain("checkpoint 实际消费3 项");
    expect(wrapper.text()).toContain("最终空间应用0 项");
    expect(wrapper.text()).toContain("缺失1 项");
    expect(wrapper.text()).toContain("超出分布1 项");
    expect(wrapper.text()).toContain("基础病 2 条；用药 1 条；化验 3 项（可用 1 项）");
    expect(wrapper.text()).toContain("当前 checkpoint 未声明用药特征");
    expect(wrapper.text()).toContain("已录入化验指标未被 checkpoint 消费");
    expect(wrapper.text()).toContain("0 项，当前患者特征未改变空间分割区域");
    expect(wrapper.text()).toContain("vector-checksum");
    expect(wrapper.text()).toContain("runtime-vector-checksum");
    expect(wrapper.text()).not.toContain("dual_channel_registration_unverified");
    expect(wrapper.text()).not.toContain("clinical_spatial_conditioning_not_authorized");
    expect(wrapper.findAll("img").map((node) => node.attributes("src"))).toEqual([
      "/preview/base.png",
      "/preview/conditioned.png",
      "/preview/difference.png",
      "/preview/uncertainty.png",
    ]);
  });

  it("selects evidence only from the active frame", () => {
    const run = {
      fused_outputs: {
        frame_details: [
          { frame_index: 1, patient_conditioning_evidence: { evidence_id: "first" } },
          { frame_index: 2, patient_conditioning_evidence: { evidence_id: "second" } },
        ],
      },
    };
    expect(patientConditioningEvidenceForFrame(run, { frameIndex: 2 })?.evidence_id).toBe("second");
    expect(patientConditioningEvidenceForFrame(run, { frameIndex: 3 })).toBeNull();
  });

  it("renders the expanded training-contract feature names and medication review reason", () => {
    const featureNames = [
      "hypertension",
      "immunosuppression",
      "antiresorptive_medication",
      "wbc_10e9_l",
      "neutrophil_percent",
      "crp_mg_l",
      "esr_mm_h",
      "hemoglobin_g_l",
    ];
    const wrapper = mount(PatientConditioningEvidencePanel, {
      props: {
        evidence: {
          spatial_effect_applied: false,
          clinical_feature_vector: {
            feature_names: featureNames,
            present_mask: featureNames.map(() => true),
            missing_mask: featureNames.map(() => false),
            ood_mask: featureNames.map(() => false),
            checkpoint_consumed_mask: featureNames.map(() => false),
            spatial_effect_applied_mask: featureNames.map(() => false),
            unconsumed_recorded_inputs: [{
              input_domain: "medications",
              record_count: 1,
              reason_codes: ["recorded_medication_not_mapped_to_checkpoint_feature"],
            }],
          },
        },
      },
    });

    expect(wrapper.text()).toContain("高血压");
    expect(wrapper.text()).toContain("免疫抑制状态");
    expect(wrapper.text()).toContain("抗骨吸收用药");
    expect(wrapper.text()).toContain("白细胞计数");
    expect(wrapper.text()).toContain("中性粒细胞百分比");
    expect(wrapper.text()).toContain("红细胞沉降率");
    expect(wrapper.text()).toContain("血红蛋白");
    expect(wrapper.text()).toContain("已录入用药未映射到 checkpoint 特征");
  });
});
