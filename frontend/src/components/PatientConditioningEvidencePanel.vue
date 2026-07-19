<template>
  <section v-if="evidence" class="conditioning-panel" aria-label="患者条件分割对照">
    <header>
      <div>
        <strong>患者条件分割对照</strong>
        <small>{{ modelLabel }}</small>
      </div>
      <span :class="{ applied: spatialEffectApplied }">{{ statusLabel }}</span>
    </header>

    <div class="evidence-grid" aria-label="基础、条件与差异证据">
      <figure v-for="item in imageItems" :key="item.key">
        <img v-if="item.path && previewUrl" :src="previewUrl(item.path)" :alt="item.label" />
        <div v-else class="image-empty">当前证据未生成</div>
        <figcaption>
          <strong>{{ item.label }}</strong>
          <a v-if="item.path && downloadUrl" :href="downloadUrl(item.path)">下载</a>
        </figcaption>
      </figure>
    </div>

    <dl>
      <div><dt>空间调制</dt><dd>{{ spatialEffectApplied ? "已受限应用" : "已回退影像基础结果" }}</dd></div>
      <div><dt>差异面积</dt><dd>{{ differenceAreaLabel }}</dd></div>
      <div><dt>临床变量可用率</dt><dd>{{ presentFractionLabel }}</dd></div>
      <div><dt>目标域晋级</dt><dd>{{ promotionLabel }}</dd></div>
      <div><dt>可信骨面</dt><dd>{{ reviewedBoneGateLabel }}</dd></div>
      <div><dt>上下文校验码</dt><dd><code>{{ checksumLabel }}</code></dd></div>
    </dl>

    <section v-if="clinicalFeatureVectorAvailable" class="feature-vector" aria-label="临床特征向量消费证据">
      <header class="feature-vector-header">
        <strong>临床特征向量</strong>
        <code>{{ clinicalFeatureVectorSchema }} · {{ clinicalFeatureVersion }}</code>
      </header>
      <dl class="feature-vector-metrics">
        <div><dt>已录入</dt><dd>{{ recordedInputDomains.length }} 类</dd></div>
        <div><dt>checkpoint 实际消费</dt><dd>{{ checkpointConsumedFeatureNames.length }} 项</dd></div>
        <div class="spatial-metric"><dt>最终空间应用</dt><dd>{{ spatiallyAppliedFeatureNames.length }} 项</dd></div>
        <div><dt>缺失</dt><dd>{{ missingFeatureNames.length }} 项</dd></div>
        <div><dt>超出分布</dt><dd>{{ oodFeatureNames.length }} 项</dd></div>
      </dl>
      <div class="feature-groups">
        <div>
          <strong>已录入输入</strong>
          <p>{{ featureListLabel(recordedInputDomains, "未记录可核验输入") }}</p>
          <small>{{ recordedInputSummaryLabel }}</small>
        </div>
        <div>
          <strong>有效向量特征</strong>
          <p>{{ featureListLabel(recordedFeatureNames, "无可进入 checkpoint 的有效特征") }}</p>
        </div>
        <div>
          <strong>checkpoint 实际消费</strong>
          <p>{{ featureListLabel(checkpointConsumedFeatureNames, "checkpoint 未消费任何患者特征") }}</p>
        </div>
        <div>
          <strong>最终空间应用</strong>
          <p>{{ featureListLabel(spatiallyAppliedFeatureNames, "0 项，当前患者特征未改变空间分割区域") }}</p>
        </div>
        <div>
          <strong>缺失 / 超出分布</strong>
          <p>缺失：{{ featureListLabel(missingFeatureNames, "无") }}</p>
          <p>超出分布：{{ featureListLabel(oodFeatureNames, "无") }}</p>
        </div>
      </div>
      <div class="unconsumed-inputs">
        <strong>未消费输入及原因</strong>
        <p v-if="!unconsumedInputs.length">无</p>
        <ul v-else>
          <li v-for="item in unconsumedInputs" :key="`${item.name}:${item.reason}`">
            <span>{{ featureLabel(item.name) }}</span>
            <small>{{ unconsumedReasonLabel(item.reason) }}</small>
          </li>
        </ul>
      </div>
      <div class="vector-checksums">
        <span>向量校验码 <code>{{ vectorChecksumLabel }}</code></span>
        <span>运行时校验码 <code>{{ runtimeVectorChecksumLabel }}</code></span>
      </div>
    </section>

    <div v-if="failureReasons.length" class="failure-list" role="status">
      <strong>安全回退原因</strong>
      <ul><li v-for="reason in failureReasons" :key="reason">{{ reasonLabel(reason) }}</li></ul>
    </div>
    <p class="boundary">
      患者变量的空间作用仅允许落在可信医生骨面与影像不确定区的交集内。任一安全门未通过时，条件结果与影像基础结果保持一致。
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";

type UrlBuilder = (path: string) => string;

const props = defineProps<{
  evidence?: Record<string, unknown> | null;
  previewUrl?: UrlBuilder;
  downloadUrl?: UrlBuilder;
}>();

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function stringValue(...values: unknown[]): string {
  const value = values.find((item) => typeof item === "string" && item.trim());
  return typeof value === "string" ? value : "";
}

function finiteNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) return Number(value);
  return null;
}

function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string" && Boolean(item.trim()))
    : [];
}

function binaryMask(value: unknown): number[] {
  return Array.isArray(value) ? value.map((item) => item === true || item === 1 ? 1 : 0) : [];
}

const lesionEvidence = computed(() => record(props.evidence?.lesion_evidence));
const outputs = computed(() => record(props.evidence?.outputs));
const spatialEffectApplied = computed(() => props.evidence?.spatial_effect_applied === true);
const statusLabel = computed(() => spatialEffectApplied.value ? "受限空间作用已应用" : "安全回退");
const modelLabel = computed(() => stringValue(props.evidence?.model_id, props.evidence?.model_family) || "模型版本未记录");
const failureReasons = computed(() => Array.isArray(props.evidence?.failure_reasons)
  ? props.evidence.failure_reasons.filter((item): item is string => typeof item === "string" && Boolean(item))
  : []);
const differenceAreaLabel = computed(() => {
  const pixels = finiteNumber(props.evidence?.difference_area_px);
  const fraction = finiteNumber(props.evidence?.difference_area_fraction);
  if (pixels === null && fraction === null) return "未记录";
  const parts = [];
  if (pixels !== null) parts.push(`${Math.max(0, Math.round(pixels)).toLocaleString("zh-CN")} px`);
  if (fraction !== null) parts.push(`${(Math.max(0, Math.min(1, fraction)) * 100).toFixed(2)}%`);
  return parts.join(" · ");
});
const presentFractionLabel = computed(() => {
  const value = finiteNumber(
    props.evidence?.effective_present_fraction,
  ) ?? finiteNumber(props.evidence?.clinical_present_fraction);
  return value === null ? "未记录" : `${(Math.max(0, Math.min(1, value)) * 100).toFixed(0)}%`;
});
const promotionLabel = computed(() => props.evidence?.target_domain_promotion_ready === true ? "已通过" : "未通过，禁止替换主线");
const reviewedBoneGateLabel = computed(() => props.evidence?.physician_reviewed_bone_gate === true ? "已绑定" : "未满足");
const checksumLabel = computed(() => stringValue(props.evidence?.clinical_context_checksum) || "未记录");
const clinicalFeatureVector = computed(() => record(props.evidence?.clinical_feature_vector));
const clinicalFeatureVectorAvailable = computed(() => Object.keys(clinicalFeatureVector.value).length > 0);
const clinicalFeatureVectorSchema = computed(() => stringValue(clinicalFeatureVector.value.schema_version) || "版本未记录");
const clinicalFeatureVersion = computed(() => stringValue(clinicalFeatureVector.value.feature_version) || "特征版本未记录");
const clinicalFeatureNames = computed(() => stringList(clinicalFeatureVector.value.feature_names));
const recordedInputSummary = computed(() => record(clinicalFeatureVector.value.recorded_input_summary));

function namesFromMask(maskValue: unknown): string[] {
  const mask = binaryMask(maskValue);
  return clinicalFeatureNames.value.filter((_name, index) => mask[index] === 1);
}

function explicitNamesOrMask(explicitKey: string, maskKey: string): string[] {
  const explicit = clinicalFeatureVector.value[explicitKey];
  return Array.isArray(explicit) ? stringList(explicit) : namesFromMask(clinicalFeatureVector.value[maskKey]);
}

const recordedFeatureNames = computed(() => namesFromMask(clinicalFeatureVector.value.present_mask));
const recordedInputDomains = computed(() => {
  const summary = recordedInputSummary.value;
  const domains: string[] = [];
  if (summary.age_recorded === true) domains.push("age");
  if (summary.sex_recorded === true) domains.push("sex_at_birth");
  if ((finiteNumber(summary.comorbidity_record_count) ?? 0) > 0 || summary.comorbidities_reviewed === true) {
    domains.push("comorbidities");
  }
  if ((finiteNumber(summary.medication_record_count) ?? 0) > 0 || summary.medications_reviewed === true) {
    domains.push("medications");
  }
  if ((finiteNumber(summary.lab_record_count) ?? 0) > 0) domains.push("laboratory_results");
  return domains.length ? domains : recordedFeatureNames.value;
});
const recordedInputSummaryLabel = computed(() => {
  const summary = recordedInputSummary.value;
  if (!Object.keys(summary).length) return "录入摘要未记录";
  const comorbidities = finiteNumber(summary.comorbidity_record_count) ?? 0;
  const medications = finiteNumber(summary.medication_record_count) ?? 0;
  const labs = finiteNumber(summary.lab_record_count) ?? 0;
  const eligibleLabs = finiteNumber(summary.eligible_lab_record_count) ?? 0;
  return `基础病 ${comorbidities} 条；用药 ${medications} 条；化验 ${labs} 项（可用 ${eligibleLabs} 项）`;
});
const checkpointConsumedFeatureNames = computed(() => explicitNamesOrMask(
  "checkpoint_consumed_feature_names",
  "checkpoint_consumed_mask",
));
const spatiallyAppliedFeatureNames = computed(() => explicitNamesOrMask(
  "spatially_applied_feature_names",
  "spatial_effect_applied_mask",
));
const missingFeatureNames = computed(() => explicitNamesOrMask("missing_feature_names", "missing_mask"));
const oodFeatureNames = computed(() => explicitNamesOrMask("ood_feature_names", "ood_mask"));
const vectorChecksumLabel = computed(() => stringValue(clinicalFeatureVector.value.vector_checksum) || "未记录");
const runtimeVectorChecksumLabel = computed(() => stringValue(
  clinicalFeatureVector.value.runtime_vector_checksum,
) || "未记录");

type UnconsumedInput = { name: string; reason: string };

const unconsumedInputs = computed<UnconsumedInput[]>(() => {
  const value = clinicalFeatureVector.value.unconsumed_recorded_inputs;
  if (Array.isArray(value)) {
    return value.flatMap((item): UnconsumedInput[] => {
      if (typeof item === "string" && item.trim()) return [{ name: item, reason: "checkpoint_did_not_consume" }];
      const payload = record(item);
      const name = stringValue(payload.feature_name, payload.input_domain, payload.input_name, payload.name);
      if (!name) return [];
      const reasonCodes = stringList(payload.reason_codes ?? payload.reasons);
      const reason = stringValue(payload.reason, payload.reason_code, payload.code, payload.status)
        || reasonCodes.join("|")
        || "checkpoint_did_not_consume";
      return [{ name, reason }];
    });
  }
  const payload = record(value);
  return Object.entries(payload).map(([name, detail]) => {
    const detailRecord = record(detail);
    const reason = stringValue(
      detailRecord.reason,
      detailRecord.reason_code,
      detailRecord.code,
      detailRecord.status,
      detail,
    ) || "checkpoint_did_not_consume";
    return { name, reason };
  });
});

function outputPath(...keys: string[]): string {
  for (const key of keys) {
    const path = stringValue(props.evidence?.[key], outputs.value[key], lesionEvidence.value[key]);
    if (path) return path;
  }
  return "";
}

const imageItems = computed(() => [
  { key: "image-only", label: "影像基础概率", path: outputPath("image_only_probability_path", "image_only_path") },
  { key: "conditioned", label: "患者条件概率", path: outputPath("conditioned_probability_path", "conditioned_path") },
  { key: "difference", label: "空间差异图", path: outputPath("difference_mask_path", "delta_map_path") },
  { key: "uncertainty", label: "模型不确定性", path: outputPath("uncertainty_path") },
]);

const reasonLabels: Record<string, string> = {
  dual_channel_registration_unverified: "白光与荧光配准证据未通过安全门",
  dual_channel_registration_not_verified: "白光与荧光配准证据未通过安全门",
  non_target_domain_proxy: "当前输入或模型证据属于非目标域代理",
  model_target_domain_promotion_missing: "患者条件模型尚未通过目标域晋级",
  clinical_context_schema_invalid: "患者结构化上下文格式未通过校验",
  clinical_context_checksum_mismatch: "患者结构化上下文校验码不一致",
  clinical_context_assessment_checksum_missing: "患者上下文派生证据缺少完整性校验码",
  clinical_context_assessment_checksum_mismatch: "患者上下文派生证据完整性校验失败",
  clinical_context_not_verified: "患者结构化上下文尚未可信核验",
  clinical_context_verified_by_missing: "患者结构化上下文缺少可信核验者",
  clinical_context_verified_at_missing: "患者结构化上下文缺少核验时间",
  clinical_context_verified_at_in_future: "患者结构化上下文核验时间晚于当前时间",
  clinical_context_verification_expired: "患者结构化上下文核验已超过有效期",
  clinical_context_verified_actor_role_untrusted: "患者结构化上下文核验者角色不受信任",
  clinical_context_verified_actor_auth_source_untrusted: "患者结构化上下文核验认证来源不受信任",
  clinical_context_verified_actor_institution_missing: "患者结构化上下文核验机构缺失",
  clinical_feature_vector_missing: "临床特征向量缺失",
  clinical_feature_vector_schema_invalid: "临床特征向量格式版本无效",
  clinical_feature_vector_version_invalid: "临床特征编码版本无效",
  clinical_feature_vector_context_checksum_mismatch: "临床特征向量与患者上下文校验码不一致",
  clinical_feature_vector_checkpoint_features_mismatch: "临床特征顺序与 checkpoint 声明不一致",
  clinical_feature_vector_model_input_values_invalid: "临床特征输入向量长度无效",
  clinical_feature_vector_present_mask_invalid: "临床特征有效值掩码无效",
  clinical_feature_vector_missing_mask_invalid: "临床特征缺失掩码无效",
  clinical_feature_vector_ood_mask_invalid: "临床特征分布外掩码无效",
  clinical_feature_vector_feature_rows_invalid: "临床特征逐项证据无效",
  clinical_feature_vector_mask_type_invalid: "临床特征掩码类型无效",
  clinical_feature_vector_mask_state_invalid: "临床特征掩码状态冲突",
  clinical_feature_vector_checksum_mismatch: "临床特征向量校验码不一致",
  clinical_feature_vector_rebuild_mismatch: "运行时重建的临床特征向量不一致",
  clinical_feature_vector_feature_names_invalid: "临床特征名称清单无效",
  clinical_feature_vector_features_unsupported: "临床特征包含当前运行时尚未支持的项目",
  clinical_spatial_conditioning_not_authorized: "患者变量尚未获准参与空间调制",
  clinical_use_boundary_disallows_spatial_conditioning: "病例声明用途未授权患者变量改变空间分割",
  clinical_context_ineligible: "临床变量完整性或有效性未达到门槛",
  physician_reviewed_bone_gate_missing: "可信医生骨面掩膜缺失",
  physician_reviewed_bone_gate_empty: "可信医生骨面掩膜为空",
  physician_reviewed_bone_gate_invalid: "可信医生骨面掩膜无法校验",
  physician_reviewed_bone_gate_untrusted: "骨面掩膜缺少可信医生复核",
  physician_reviewed_bone_gate_evidence_missing: "骨面掩膜证据字段不完整",
  physician_reviewed_bone_gate_file_missing: "骨面掩膜文件缺失",
  physician_reviewed_bone_gate_sha256_mismatch: "骨面掩膜文件校验码不一致",
  physician_reviewed_bone_gate_unreadable: "骨面掩膜文件无法读取",
  physician_reviewed_bone_gate_dimension_mismatch: "骨面掩膜尺寸与当前影像不一致",
  target_domain_input_not_verified: "当前输入尚未通过目标域数据准入",
  non_finite_model_output: "模型输出包含无效数值",
  checkpoint_runtime_not_authorized: "checkpoint 未获运行替换授权",
  patient_conditioned_model_unavailable: "患者条件模型当前不可用",
  patient_conditioned_model_not_configured: "患者条件模型尚未配置",
  patient_conditioned_inference_failed: "患者条件推理失败，已回退影像基础结果",
};
function reasonLabel(value: string): string { return reasonLabels[value] ?? value; }

const featureLabels: Record<string, string> = {
  age: "年龄",
  age_years: "年龄",
  sex: "性别",
  biological_sex: "生理性别",
  sex_at_birth: "出生时生理性别",
  sex_at_birth_female: "出生时生理性别（女性编码）",
  comorbidities: "基础病",
  diabetes: "糖尿病",
  hypertension: "高血压",
  renal_disease: "肾脏基础病",
  immunosuppression: "免疫抑制状态",
  medications: "用药",
  antiresorptive_medication: "抗骨吸收用药",
  laboratory_results: "血液与实验室指标",
  crp: "C 反应蛋白",
  crp_mg_l: "C 反应蛋白",
  wbc: "白细胞计数",
  wbc_10e9_l: "白细胞计数",
  neutrophil_percent: "中性粒细胞百分比",
  albumin: "白蛋白",
  hemoglobin: "血红蛋白",
  hemoglobin_g_l: "血红蛋白",
  esr_mm_h: "红细胞沉降率",
  platelets: "血小板",
  creatinine: "肌酐",
  egfr_ml_min_1_73m2: "估算肾小球滤过率",
};
function featureLabel(value: string): string { return featureLabels[value] ?? value; }
function featureListLabel(values: string[], emptyLabel: string): string {
  return values.length ? values.map(featureLabel).join("、") : emptyLabel;
}

const unconsumedReasonLabels: Record<string, string> = {
  checkpoint_did_not_consume: "当前 checkpoint 未声明消费该输入",
  checkpoint_feature_not_declared: "当前 checkpoint 的特征清单未包含该输入",
  ood_blocked: "输入超出训练分布，已阻止消费",
  missing: "输入缺失",
  spatial_safety_gate_not_authorized: "空间作用安全门未获授权",
  proxy_checkpoint: "代理 checkpoint 仅记录输入，未用于空间作用",
  checkpoint_declares_no_medication_features: "当前 checkpoint 未声明用药特征",
  recorded_medication_not_mapped_to_checkpoint_feature: "已录入用药未映射到 checkpoint 特征",
  recorded_comorbidity_not_mapped_to_checkpoint_feature: "已录入基础病未映射到 checkpoint 特征",
  recorded_lab_not_consumed_by_checkpoint: "已录入化验指标未被 checkpoint 消费",
  category_not_encoded_by_feature_v1: "当前特征版本未编码该分类值",
  value_out_of_distribution: "数值超出当前特征版本安全范围",
  lab_value_invalid_stale_or_unsupported: "化验值无效、过期或单位暂不支持",
  comorbidity_absence_not_verified: "基础病阴性状态尚未复核",
  medication_absence_not_verified: "用药阴性状态尚未复核",
  ambiguous_comorbidity_text_requires_structured_confirmation: "基础病文本含义不明确，需要结构化确认",
  ambiguous_medication_text_requires_structured_confirmation: "用药文本含义不明确，需要结构化确认",
  multiple_eligible_lab_values_require_review: "同一指标存在多个可用值，需要复核",
  source_missing: "来源字段缺失",
  feature_value_not_eligible: "特征值未通过消费条件",
};
function unconsumedReasonLabel(value: string): string {
  return value.split("|").map((item) => unconsumedReasonLabels[item] ?? item).join("；");
}
</script>

<style scoped>
.conditioning-panel { display: grid; gap: 12px; border: 1px solid var(--ov-border); border-radius: 8px; padding: 14px; background: var(--ov-bg-elevated); }
header, header > div, figcaption { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
header > div { align-items: flex-start; flex-direction: column; }
header strong { color: var(--ov-text); }
header small { color: var(--ov-text-muted); font-size: 11px; overflow-wrap: anywhere; }
header > span { color: var(--ov-warning); font-size: 11px; font-weight: 800; }
header > span.applied { color: var(--ov-success); }
.evidence-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
figure { min-width: 0; margin: 0; overflow: hidden; border: 1px solid var(--ov-border); border-radius: 6px; background: var(--ov-bg-soft); }
figure img, .image-empty { display: block; width: 100%; height: 170px; object-fit: contain; background: var(--ov-bg-soft); }
.image-empty { display: grid; place-items: center; color: var(--ov-text-muted); font-size: 11px; }
figcaption { padding: 8px; color: var(--ov-text); font-size: 11px; }
a { color: var(--ov-accent); font-weight: 700; }
dl { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin: 0; }
dl div { min-width: 0; padding: 8px; background: var(--ov-bg-soft); }
dt, dd { margin: 0; overflow-wrap: anywhere; }
dt { color: var(--ov-text-muted); font-size: 10px; }
dd { color: var(--ov-text); font-size: 11px; font-weight: 800; }
code { white-space: normal; overflow-wrap: anywhere; }
.feature-vector { display: grid; gap: 10px; padding: 12px 0; border-top: 1px solid var(--ov-border); border-bottom: 1px solid var(--ov-border); }
.feature-vector-header { align-items: baseline; }
.feature-vector-header code { color: var(--ov-text-muted); font-size: 10px; }
.feature-vector-metrics { grid-template-columns: repeat(5, minmax(0, 1fr)); }
.feature-vector-metrics .spatial-metric { border-left: 3px solid var(--ov-warning); }
.feature-groups { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 18px; }
.feature-groups > div { min-width: 0; padding-left: 10px; border-left: 2px solid var(--ov-border-strong); }
.feature-groups strong, .unconsumed-inputs > strong { color: var(--ov-text); font-size: 11px; }
.feature-groups small { display: block; margin-top: 4px; color: var(--ov-text-muted); font-size: 10px; line-height: 1.5; overflow-wrap: anywhere; }
.feature-groups p, .unconsumed-inputs p { margin: 4px 0 0; color: var(--ov-text-muted); font-size: 11px; line-height: 1.5; overflow-wrap: anywhere; }
.unconsumed-inputs ul { display: grid; gap: 5px; margin: 6px 0 0; padding: 0; list-style: none; }
.unconsumed-inputs li { display: grid; grid-template-columns: minmax(120px, .35fr) minmax(0, 1fr); gap: 8px; color: var(--ov-text); font-size: 11px; }
.unconsumed-inputs small { color: var(--ov-warning); overflow-wrap: anywhere; }
.vector-checksums { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; color: var(--ov-text-muted); font-size: 10px; }
.vector-checksums span, .vector-checksums code { min-width: 0; overflow-wrap: anywhere; }
.failure-list { padding: 10px; border: 1px solid var(--ov-warning); border-radius: 6px; color: var(--ov-warning); font-size: 11px; }
.failure-list ul { margin: 6px 0 0; padding-left: 18px; }
.boundary { margin: 0; color: var(--ov-warning); font-size: 11px; line-height: 1.5; overflow-wrap: anywhere; }
@media (max-width: 1100px) { .evidence-grid, dl, .feature-vector-metrics, .feature-groups, .vector-checksums { grid-template-columns: 1fr; } }
</style>
