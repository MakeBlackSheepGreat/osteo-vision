import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import ClinicalContextPanel from "../src/components/ClinicalContextPanel.vue";
import type { ClinicalContext } from "../src/types/case";

describe("ClinicalContextPanel", () => {
  it("keeps the spatial safety boundary visible", async () => {
    const wrapper = mount(ClinicalContextPanel, { props: { context: {
      age_years: 66, age_group: "older_adult", sex_at_birth: "male", comorbidities: [], medications: [], labs: [],
      review_status: "review_required", deidentified: true, clinical_use_boundary: "risk_prior_and_calibration_only_no_spatial_boundary_effect",
    } } });
    expect(wrapper.text()).toContain("当前不改变像素级空间边界");
    const completenessChecks = wrapper.findAll("input[type='checkbox']");
    expect(completenessChecks).toHaveLength(2);
    await completenessChecks[0].setValue(true);
    await wrapper.find("form").trigger("submit");
    expect(wrapper.emitted("save")?.[0]?.[0]).toMatchObject({ age_years: 66, comorbidities_reviewed: true, deidentified: true });
  });

  it("captures laboratory provenance and shows the latest assessment safely", async () => {
    const wrapper = mount(ClinicalContextPanel, { props: { context: {
      age_years: 66, age_group: "older_adult", sex_at_birth: "male", comorbidities: ["糖尿病"], medications: [], labs: [],
      review_status: "verified", deidentified: true, clinical_use_boundary: "risk_prior_and_calibration_only_no_spatial_boundary_effect",
    }, saveStatus: "success", assessment: {
      clinical_context_checksum: "abc123",
      clinical_context_quality: { status: "limited", missing_critical_fields: ["fresh_unit_valid_labs"], issues: ["lab_unit_missing", "lab_result_stale"], usable_lab_count: 0, recorded_lab_count: 1 },
      rule_based_risk_summary: { contributing_factors: [{ label: "糖尿病", type: "recorded_comorbidity" }] },
      calibration_evidence: { applied: false, status: "pending_target_domain_validation" },
      clinical_feature_vector: {
        feature_version: "clinical-feature-vector-v1",
        feature_names: ["age_years", "sex_at_birth_female", "diabetes"],
        present_mask: [true, true, true],
      },
      spatial_effect_applied: false,
    } } });

    expect(wrapper.text()).toContain("临床上下文已保存");
    expect(wrapper.text()).toContain("化验单位缺失");
    expect(wrapper.text()).toContain("化验结果超过 7 天");
    expect(wrapper.text()).toContain("糖尿病");
    expect(wrapper.text()).toContain("abc123");
    expect(wrapper.text()).toContain("尚未应用（等待目标域验证）");
    expect(wrapper.text()).toContain("clinical-feature-vector-v1");
    expect(wrapper.text()).toContain("3 / 3");
    expect(wrapper.text()).toContain("平台特征覆盖");
    expect(wrapper.text()).toContain("出生时生理性别（女性编码）");
    expect(wrapper.text()).toContain("保持影像边界");

    await wrapper.get("button[type='button']:last-of-type").trigger("click");
    const labs = wrapper.findAll(".lab-row");
    expect(labs).toHaveLength(1);
    await labs[0].get('[aria-label="指标名称"]').setValue("CRP");
    await labs[0].get('[aria-label="指标值"]').setValue("12");
    await labs[0].get('[aria-label="指标单位"]').setValue("mg/L");
    await labs[0].get('[aria-label="参考范围"]').setValue("0-10");
    await labs[0].get('[aria-label="采样时间"]').setValue("2026-07-17T09:30");
    await labs[0].get('[aria-label="异常状态"]').setValue("high");
    await wrapper.find("form").trigger("submit");
    expect(wrapper.emitted("save")?.at(-1)?.[0]).toMatchObject({ labs: [{ name: "CRP", value: "12", unit: "mg/L", reference_range: "0-10", measured_at: "2026-07-17T09:30", abnormal_flag: "high" }] });
  });

  it("renders saving and error feedback", async () => {
    const context: ClinicalContext = { age_group: "unknown", sex_at_birth: "not_recorded", comorbidities: [], medications: [], labs: [], review_status: "unreviewed", deidentified: true, clinical_use_boundary: "risk_prior_and_calibration_only_no_spatial_boundary_effect" };
    const wrapper = mount(ClinicalContextPanel, { props: { context, saveStatus: "saving" } });
    expect(wrapper.get("button[type='submit']").attributes("disabled")).toBeDefined();
    expect(wrapper.text()).toContain("保存中");
    await wrapper.setProps({ saveStatus: "error", saveError: "网络错误" });
    expect(wrapper.text()).toContain("网络错误");
  });

  it("shows trusted verification provenance and warns when the audit snapshot is missing", async () => {
    const verified: ClinicalContext = {
      age_group: "unknown", sex_at_birth: "not_recorded", comorbidities: [], medications: [], labs: [],
      review_status: "verified", deidentified: true, clinical_use_boundary: "risk_prior_and_calibration_only_no_spatial_boundary_effect",
      verified_by: { actor_id: "doctor-01", role: "physician", institution: "绵阳市第三人民医院", auth_source: "verified_identity_token" },
      verified_at: "2026-07-18T00:00:00Z",
    };
    const wrapper = mount(ClinicalContextPanel, { props: { context: verified } });
    expect(wrapper.text()).toContain("可信核验凭证");
    expect(wrapper.text()).toContain("医生 · doctor-01");
    expect(wrapper.text()).toContain("绵阳市第三人民医院 · 可信身份令牌");
    expect(wrapper.text()).toContain("核验时间");

    await wrapper.setProps({ context: { ...verified, verified_by: null, verified_at: null } });
    expect(wrapper.text()).toContain("核验身份凭证缺失");
  });
});
