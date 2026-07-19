<template>
  <details class="clinical-panel">
    <summary>患者结构化上下文 <span>{{ statusLabel }}</span></summary>
    <form class="clinical-form" @submit.prevent="save">
      <div class="field-grid">
        <label>年龄<input v-model.number="draft.age_years" type="number" min="0" max="130" /></label>
        <label>出生性别<select v-model="draft.sex_at_birth"><option value="not_recorded">未记录</option><option value="female">女</option><option value="male">男</option><option value="intersex">间性</option><option value="unknown">未知</option></select></label>
        <label>来源机构<input v-model="draft.source_organization" /></label>
        <label>复核状态<select v-model="draft.review_status"><option value="unreviewed">未复核</option><option value="review_required">待复核</option><option value="verified">已核验</option></select></label>
        <label>患者变量用途<select v-model="draft.clinical_use_boundary"><option value="risk_prior_and_calibration_only_no_spatial_boundary_effect">风险提示与校准</option><option value="restricted_spatial_conditioning_with_physician_review">受限患者条件分割</option></select></label>
      </div>
      <label>基础病（每行一项）<textarea v-model="comorbidityText" rows="3" /></label>
      <label class="review-checkbox"><input v-model="draft.comorbidities_reviewed" type="checkbox" />基础病清单已完整核对</label>
      <label>用药（每行一项）<textarea v-model="medicationText" rows="2" /></label>
      <label class="review-checkbox"><input v-model="draft.medications_reviewed" type="checkbox" />用药清单已完整核对</label>
      <fieldset>
        <legend>血液指标</legend>
        <div v-for="(lab, index) in draft.labs" :key="index" class="lab-row">
          <input v-model="lab.name" aria-label="指标名称" placeholder="如 CRP" />
          <input v-model="lab.value" aria-label="指标值" placeholder="数值" />
          <input v-model="lab.unit" aria-label="指标单位" placeholder="单位" />
          <input v-model="lab.reference_range" aria-label="参考范围" placeholder="参考范围" />
          <input v-model="lab.measured_at" aria-label="采样时间" type="datetime-local" />
          <select v-model="lab.abnormal_flag" aria-label="异常状态"><option value="unknown">待判定</option><option value="low">偏低</option><option value="normal">正常</option><option value="high">偏高</option></select>
          <button type="button" @click="draft.labs.splice(index, 1)">移除</button>
        </div>
        <button type="button" @click="addLab">添加指标</button>
      </fieldset>
      <p class="boundary">{{ boundaryText }}</p>
      <div v-if="draft.review_status === 'verified' && draft.verified_by" class="verification-evidence" aria-label="临床上下文核验凭证">
        <strong>可信核验凭证</strong>
        <span>{{ reviewerRoleLabel(draft.verified_by.role) }} · {{ draft.verified_by.actor_id }}</span>
        <span>{{ draft.verified_by.institution }} · {{ authSourceLabel(draft.verified_by.auth_source) }}</span>
        <span>{{ formatVerifiedAt(draft.verified_at) }}</span>
      </div>
      <p v-else-if="draft.review_status === 'verified'" class="save-message error" role="alert">核验身份凭证缺失，请重新提交可信复核。</p>
      <p v-if="saveStatus === 'success'" class="save-message success" role="status">临床上下文已保存。</p>
      <p v-if="saveStatus === 'error'" class="save-message error" role="alert">{{ saveError || "临床上下文保存失败，请重试。" }}</p>
      <button type="submit" :disabled="disabled || saveStatus === 'saving'">{{ saveStatus === "saving" ? "保存中…" : "保存临床上下文" }}</button>
    </form>
    <section v-if="assessment" class="assessment" aria-label="最新分析临床上下文评估">
      <h3>最新分析中的临床上下文评估</h3>
      <div class="assessment-grid">
        <span>完整性</span><strong>{{ qualityLabel }}</strong>
        <span>可用化验</span><strong>{{ quality.usable_lab_count ?? 0 }} / {{ quality.recorded_lab_count ?? 0 }}</strong>
        <span>校准</span><strong>{{ assessment.calibration_evidence?.applied ? "已应用" : "尚未应用（等待目标域验证）" }}</strong>
        <span>特征向量</span><strong>{{ featureVectorLabel }}</strong>
        <span>可用特征</span><strong>{{ eligibleFeatureLabel }}</strong>
        <span>声明用途</span><strong>{{ assessmentBoundaryLabel }}</strong>
        <span>上下文校验码</span><code>{{ assessment.clinical_context_checksum || "未记录" }}</code>
      </div>
      <div v-if="assessmentFeatureNames.length" class="assessment-list feature-coverage">
        <strong>平台特征覆盖</strong>
        <ul>
          <li>可用：{{ featureNameList(assessmentEligibleFeatureNames, "无") }}</li>
          <li>缺失：{{ featureNameList(assessmentMissingFeatureNames, "无") }}</li>
          <li>超出范围：{{ featureNameList(assessmentOodFeatureNames, "无") }}</li>
        </ul>
      </div>
      <div v-if="quality.missing_critical_fields?.length" class="assessment-list"><strong>完整性缺项</strong><ul><li v-for="item in quality.missing_critical_fields" :key="item">{{ issueLabel(item) }}</li></ul></div>
      <div v-if="quality.issues?.length" class="assessment-list warning"><strong>单位或时效问题</strong><ul><li v-for="item in quality.issues" :key="item">{{ issueLabel(item) }}</li></ul></div>
      <div v-if="contributingFactors.length" class="assessment-list"><strong>规则贡献项（供医生复核）</strong><ul><li v-for="(item, index) in contributingFactors" :key="index">{{ factorLabel(item) }}</li></ul></div>
    </section>
  </details>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import type { ClinicalContext, ClinicalContextAssessment } from "@/types/case";

const props = withDefaults(defineProps<{ context: ClinicalContext; assessment?: ClinicalContextAssessment | null; disabled?: boolean; saveStatus?: "idle" | "saving" | "success" | "error"; saveError?: string }>(), { assessment: null, saveStatus: "idle", saveError: "" });
const emit = defineEmits<{ save: [context: ClinicalContext] }>();
const cloneContext = (value: ClinicalContext): ClinicalContext => JSON.parse(JSON.stringify(value)) as ClinicalContext;
const draft = reactive<ClinicalContext>(cloneContext(props.context));
const comorbidityText = ref("");
const medicationText = ref("");
const statusLabel = computed(() => ({ verified: "已核验", review_required: "待复核", unreviewed: "未复核" })[draft.review_status]);
const quality = computed(() => props.assessment?.clinical_context_quality ?? {});
const qualityLabel = computed(() => ({ ready_for_rule_summary: "可用于规则摘要", review_required: "需要复核", limited: "信息有限" }[quality.value.status ?? ""] ?? "未评估"));
const contributingFactors = computed(() => props.assessment?.rule_based_risk_summary?.contributing_factors ?? []);
const featureVector = computed(() => props.assessment?.clinical_feature_vector ?? {});
const featureVectorLabel = computed(() => featureVector.value.feature_version || "未生成");
const eligibleFeatureLabel = computed(() => {
  const names = featureVector.value.feature_names ?? [];
  const present = featureVector.value.present_mask ?? [];
  return `${present.filter(Boolean).length} / ${names.length}`;
});
const assessmentFeatureNames = computed(() => featureVector.value.feature_names ?? []);
function featureNamesFromMask(mask: boolean[] | undefined): string[] {
  return assessmentFeatureNames.value.filter((_name, index) => mask?.[index] === true);
}
const assessmentEligibleFeatureNames = computed(() => featureVector.value.eligible_feature_names ?? featureNamesFromMask(featureVector.value.present_mask));
const assessmentMissingFeatureNames = computed(() => featureVector.value.missing_feature_names ?? featureNamesFromMask(featureVector.value.missing_mask));
const assessmentOodFeatureNames = computed(() => featureVector.value.ood_feature_names ?? featureNamesFromMask(featureVector.value.ood_mask));
const boundaryText = computed(() => draft.clinical_use_boundary === "restricted_spatial_conditioning_with_physician_review"
  ? "仅允许在目标域模型晋级、可信医生骨面、配准与不确定区等安全门全部通过后进行受限空间调制；任一条件未通过时回退影像基础结果。"
  : "该信息只参与风险先验、概率校准和不确定性提示，当前不改变像素级空间边界。");
const assessmentBoundaryLabel = computed(() => props.assessment?.clinical_context_snapshot?.clinical_use_boundary === "restricted_spatial_conditioning_with_physician_review"
  ? "已声明受限患者条件分割，最终作用以运行时安全证据为准"
  : "保持影像边界：风险提示与校准，不授权空间调制");

watch(() => props.context, (value) => {
  Object.assign(draft, cloneContext(value));
  comorbidityText.value = value.comorbidities.join("\n");
  medicationText.value = value.medications.join("\n");
}, { immediate: true, deep: true });

function addLab() { draft.labs.push({ name: "", value: "", unit: "", reference_range: "", measured_at: "", abnormal_flag: "unknown" }); }
function lines(value: string) { return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean); }
function save() {
  draft.comorbidities = lines(comorbidityText.value);
  draft.medications = lines(medicationText.value);
  draft.labs = draft.labs.filter((lab) => lab.name.trim());
  emit("save", cloneContext(draft));
}
function reviewerRoleLabel(value: string) { return ({ physician: "医生", project_reviewer: "项目复核者", engineering_reviewer: "工程复核者", legacy_unverified: "历史未核验身份" } as Record<string, string>)[value] ?? value; }
function authSourceLabel(value: string) { return ({ institution_sso: "机构单点认证", signed_session: "签名会话", verified_identity_token: "可信身份令牌" } as Record<string, string>)[value] ?? value; }
function formatVerifiedAt(value?: string | null) { if (!value) return "核验时间未记录"; const date = new Date(value); return Number.isNaN(date.getTime()) ? value : `核验时间 ${date.toLocaleString("zh-CN", { hour12: false })}`; }
const issueLabels: Record<string, string> = { age_years: "年龄", sex_at_birth: "出生性别", verified_review: "医生核验", fresh_unit_valid_labs: "具有有效单位和采样时间的近期化验", lab_unit_missing: "化验单位缺失", lab_unit_unsupported: "化验单位暂不支持", lab_timestamp_missing: "采样时间缺失", lab_timestamp_in_future: "采样时间晚于分析时间", lab_result_stale: "化验结果超过 7 天", lab_value_non_numeric: "化验值无法转为数值", lab_indicator_unsupported: "指标暂未纳入规则质控", lab_abnormal_flag_conflict: "人工异常状态与参考规则不一致", lab_latest_result_conflict: "同一采样时间存在相互冲突的最新化验结果", context_deidentification_not_confirmed: "脱敏状态未确认" };
const featureLabels: Record<string, string> = { age_years: "年龄", sex_at_birth_female: "出生时生理性别（女性编码）", diabetes: "糖尿病", hypertension: "高血压", renal_disease: "肾脏基础病", immunosuppression: "免疫抑制状态", antiresorptive_medication: "抗骨吸收用药", wbc_10e9_l: "白细胞计数", neutrophil_percent: "中性粒细胞百分比", crp_mg_l: "C 反应蛋白", esr_mm_h: "红细胞沉降率", hemoglobin_g_l: "血红蛋白", egfr_ml_min_1_73m2: "估算肾小球滤过率" };
function issueLabel(value: string) { return issueLabels[value] ?? value; }
function featureNameList(values: string[], empty: string) { return values.length ? values.map((value) => featureLabels[value] ?? value).join("、") : empty; }
function factorLabel(item: Record<string, unknown>) { const label = String(item.label ?? "未命名项"); const direction = item.direction ? `（${issueLabel(String(item.direction))}）` : ""; const value = item.value == null ? "" : `：${item.value} ${String(item.unit ?? "")}`; return `${label}${direction}${value}`; }
</script>

<style scoped>
.clinical-panel { border: 1px solid var(--ov-border); border-radius: 6px; padding: 10px; background: var(--ov-bg-elevated); }
summary { display: flex; justify-content: space-between; cursor: pointer; color: var(--ov-text); font-weight: 900; }
summary span { color: var(--ov-primary); font-size: 11px; }
.clinical-form { display: grid; gap: 10px; margin-top: 12px; }
.field-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
label { display: grid; gap: 4px; color: var(--ov-text-secondary); font-size: 11px; font-weight: 800; }
.review-checkbox { display: flex; align-items: center; gap: 7px; }
.review-checkbox input { width: 15px; height: 15px; margin: 0; }
input, select, textarea, button { min-width: 0; border: 1px solid var(--ov-border-strong); border-radius: 5px; padding: 7px; background: var(--ov-bg-elevated); color: var(--ov-text); font: inherit; overflow-wrap: anywhere; }
fieldset { display: grid; gap: 7px; margin: 0; border: 1px solid var(--ov-border-subtle); border-radius: 5px; padding: 8px; }
legend { color: var(--ov-text-secondary); font-size: 11px; font-weight: 800; }
.lab-row { display: grid; grid-template-columns: 1fr .65fr .65fr .8fr 1.25fr .8fr auto; gap: 5px; }
.boundary { margin: 0; color: var(--ov-warning); font-size: 11px; line-height: 1.5; }
button { cursor: pointer; font-weight: 800; }
.save-message { margin: 0; font-size: 12px; } .success { color: var(--ov-success); } .error { color: var(--ov-danger); }
.verification-evidence { display: grid; gap: 4px; padding: 9px; border: 1px solid var(--ov-success); border-radius: 5px; background: var(--ov-bg-soft); color: var(--ov-text-secondary); font-size: 11px; overflow-wrap: anywhere; }
.verification-evidence strong { color: var(--ov-success); }
.assessment { display: grid; gap: 9px; margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--ov-border-subtle); }
.assessment h3 { margin: 0; font-size: 12px; color: var(--ov-text); }
.assessment-grid { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 6px 10px; font-size: 11px; color: var(--ov-text-secondary); }
.assessment-grid strong, .assessment-grid code { color: var(--ov-text); overflow-wrap: anywhere; white-space: normal; }
.assessment-list { font-size: 11px; color: var(--ov-text-secondary); } .assessment-list ul { margin: 5px 0 0; padding-left: 18px; } .assessment-list.warning { color: var(--ov-warning); }
@media (max-width: 1200px) { .lab-row { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
