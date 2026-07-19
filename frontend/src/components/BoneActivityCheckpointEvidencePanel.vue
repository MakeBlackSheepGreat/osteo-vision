<template>
  <section v-if="evidence" class="checkpoint-panel" aria-label="骨活性 checkpoint 工程证据">
    <header>
      <div class="heading-copy">
        <span class="heading-icon" aria-hidden="true"><AppIcon name="clipboard" /></span>
        <div>
          <strong>骨活性 checkpoint 工程证据</strong>
          <small>{{ modelLabel }}</small>
        </div>
      </div>
      <span class="status-badge" :class="statusTone">{{ statusLabel }}</span>
    </header>

    <dl class="status-grid">
      <div>
        <dt>工程推理</dt>
        <dd>{{ executionLabel }}</dd>
      </div>
      <div>
        <dt>训练数据域</dt>
        <dd>{{ trainingDomainLabel }}</dd>
      </div>
      <div>
        <dt>空间候选</dt>
        <dd>{{ spatialStatusLabel }}</dd>
      </div>
      <div>
        <dt>主线替换</dt>
        <dd>{{ replacementLabel }}</dd>
      </div>
    </dl>

    <section class="integrity-section" aria-label="模型与证据完整性校验">
      <div class="section-heading">
        <strong>完整性校验</strong>
        <small>SHA256 全量显示</small>
      </div>
      <dl class="hash-grid">
        <div v-for="item in hashItems" :key="item.key">
          <dt>{{ item.label }}</dt>
          <dd><code>{{ item.sha256 || "未记录" }}</code></dd>
          <a
            v-if="item.path && downloadUrl"
            :href="downloadUrl(item.path)"
            :data-testid="`${item.key}-download`"
            :aria-label="`下载${item.label}`"
          >
            <AppIcon name="download" />
            <span>下载{{ item.fileLabel }}</span>
          </a>
        </div>
      </dl>
    </section>

    <section v-if="failureReasonLabels.length" class="failure-section" aria-label="安全门与失败原因">
      <strong>安全门记录</strong>
      <ul>
        <li v-for="reason in failureReasonLabels" :key="reason">{{ reason }}</li>
      </ul>
    </section>

    <p class="spatial-boundary" :class="{ available: spatialCandidatesAvailable }" role="status">
      <strong>{{ spatialBoundaryTitle }}</strong>
      <span>{{ spatialBoundaryText }}</span>
    </p>
    <p class="clinical-boundary">{{ medicalBoundaryLabel }}</p>
    <p class="clinical-boundary fixed">
      仅用于研发验证、模型审计和医生复核辅助；不得作为诊断、切除范围或切除成功率依据。
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";

import AppIcon from "@/components/AppIcon.vue";

type UrlBuilder = (path: string) => string;

interface HashItem {
  key: "checkpoint" | "manifest" | "raw-npz" | "evidence-json";
  label: string;
  fileLabel: string;
  sha256: string;
  path: string;
}

const props = defineProps<{
  evidence?: Record<string, unknown> | null;
  downloadUrl?: UrlBuilder;
}>();

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function firstString(...values: unknown[]): string {
  const value = values.find((item) => typeof item === "string" && item.trim());
  return typeof value === "string" ? value.trim() : "";
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string" && Boolean(item.trim()));
}

function validSha256(value: unknown): string {
  const text = typeof value === "string" ? value.trim().toLowerCase() : "";
  return /^[0-9a-f]{64}$/.test(text) ? text : "";
}

function firstValidSha256(...values: unknown[]): string {
  for (const value of values) {
    const sha256 = validSha256(value);
    if (sha256) return sha256;
  }
  return "";
}

const rawEngineeringOutputs = computed(() => record(props.evidence?.raw_engineering_outputs));
const modelLabel = computed(() => firstString(
  props.evidence?.model_id,
  props.evidence?.model_family,
) || "模型版本未记录");
const inferenceExecuted = computed(() => props.evidence?.engineering_inference_executed === true);
const proxyCheckpoint = computed(() => props.evidence?.proxy_checkpoint === true);
const spatialCandidatesAvailable = computed(() => (
  props.evidence?.spatial_candidates_available === true
  && props.evidence?.spatial_effect_applied !== false
));
const statusLabel = computed(() => {
  if (spatialCandidatesAvailable.value) return "医生复核候选已生成";
  if (inferenceExecuted.value) return "工程证据已生成";
  return "安全关闭";
});
const statusTone = computed(() => spatialCandidatesAvailable.value ? "ready" : inferenceExecuted.value ? "evidence" : "closed");
const executionLabel = computed(() => inferenceExecuted.value ? "已执行并保存证据" : "未执行或执行失败");
const spatialStatusLabel = computed(() => spatialCandidatesAvailable.value ? "已生成，等待医生复核" : "已关闭，仅保留工程数组");
const replacementLabel = computed(() => props.evidence?.runtime_replacement_allowed === true
  ? "已获严格运行授权"
  : "禁止替换比赛主线");

const trainingDomainLabel = computed(() => {
  const trainingDomain = props.evidence?.training_domain ?? props.evidence?.input_domain;
  if (typeof trainingDomain === "string" && trainingDomain.trim()) {
    return proxyCheckpoint.value ? `非目标域代理 · ${trainingDomain.trim()}` : trainingDomain.trim();
  }
  const domain = record(trainingDomain);
  const detailValues = [
    firstString(domain.label, domain.name, domain.dataset_id, domain.data_domain, domain.source_domain),
    ...stringList(domain.dataset_ids),
    ...stringList(domain.source_dataset_ids),
  ].filter(Boolean);
  const details = Array.from(new Set(detailValues)).join("、");
  if (proxyCheckpoint.value) return details ? `非目标域代理 · ${details}` : "非目标域代理 checkpoint";
  if (domain.target_domain === true) return details ? `目标域 · ${details}` : "目标域训练证据已记录";
  return details || "训练数据域未记录";
});

const hashItems = computed<HashItem[]>(() => [
  {
    key: "checkpoint",
    label: "Checkpoint SHA256",
    fileLabel: "checkpoint",
    sha256: validSha256(props.evidence?.checkpoint_sha256),
    path: firstString(props.evidence?.checkpoint_path),
  },
  {
    key: "manifest",
    label: "Manifest SHA256",
    fileLabel: "manifest",
    sha256: validSha256(props.evidence?.manifest_sha256),
    path: firstString(props.evidence?.manifest_path),
  },
  {
    key: "raw-npz",
    label: "原始工程 NPZ SHA256",
    fileLabel: "NPZ",
    sha256: firstValidSha256(
      rawEngineeringOutputs.value.sha256,
      record(props.evidence?.asset_sha256).raw_engineering_outputs_path,
    ),
    path: firstString(
      rawEngineeringOutputs.value.path,
      props.evidence?.raw_engineering_outputs_path,
    ),
  },
  {
    key: "evidence-json",
    label: "证据 JSON SHA256",
    fileLabel: "JSON",
    sha256: firstValidSha256(
      props.evidence?.evidence_manifest_sha256,
      props.evidence?.evidence_json_sha256,
    ),
    path: firstString(
      props.evidence?.evidence_manifest_path,
      props.evidence?.evidence_json_path,
    ),
  },
]);

const reasonLabels: Record<string, string> = {
  non_target_domain_proxy: "当前 checkpoint 来源于非目标域代理数据",
  engineering_utility_gate_failed: "冻结工程效用门未通过",
  dual_channel_registration_not_verified: "白光与荧光配准证据未通过核验",
  dual_channel_registration_unverified: "白光与荧光配准证据未通过核验",
  target_domain_input_not_verified: "当前输入尚未通过目标域数据准入",
  physician_reviewed_bone_gate_missing: "可信医生骨面门控缺失",
  physician_reviewed_bone_gate_untrusted: "骨面门控缺少可信医生复核",
  physician_reviewed_bone_gate_status_invalid: "骨面门控复核状态无效",
  physician_reviewed_bone_gate_reviewer_identity_untrusted: "骨面门控复核者身份未通过可信校验",
  physician_reviewed_bone_gate_annotation_binding_missing: "骨面门控标注版本绑定信息不完整",
  physician_reviewed_bone_gate_source_checksum_mismatch: "骨面门控与源图校验码不一致",
  physician_reviewed_bone_gate_evidence_missing: "骨面门控证据字段不完整",
  physician_reviewed_bone_gate_file_missing: "骨面门控文件缺失",
  physician_reviewed_bone_gate_sha256_mismatch: "骨面门控文件校验码不一致",
  physician_reviewed_bone_gate_dimension_mismatch: "骨面门控尺寸与当前影像不一致",
  physician_reviewed_bone_gate_positive_pixel_count_mismatch: "骨面门控像素数绑定校验失败",
  model_promotion_not_ready: "模型尚未通过目标域晋级",
  bone_activity_inference_failed: "骨活性 checkpoint 工程推理失败",
  registered_white_light_and_fluorescence_inputs_required: "缺少已配准的白光与荧光输入",
};
const failureReasonLabels = computed(() => Array.from(new Set(
  stringList(props.evidence?.failure_reasons).map((reason) => reasonLabels[reason] ?? reason),
)));

const spatialBoundaryTitle = computed(() => spatialCandidatesAvailable.value
  ? "空间候选等待医生复核"
  : "空间输出已关闭");
const spatialBoundaryText = computed(() => spatialCandidatesAvailable.value
  ? "低活性候选、过渡复核区、高活性参考和无法判断区仅作为医生复核图层。"
  : "未生成低活性、过渡、高活性空间候选、面积比例或连续评分图层；原始 NPZ 禁止直接用于空间判读。");

const knownMedicalBoundaries: Record<string, string> = {
  "Bone-activity outputs remain research validation evidence requiring physician review.": "骨活性输出仅作为研发验证证据，必须由医生复核。",
  "Engineering outputs remain unavailable for spatial clinical use.": "工程输出当前禁止用于临床空间判读。",
};
const medicalBoundaryLabel = computed(() => {
  const boundary = firstString(props.evidence?.medical_boundary);
  return knownMedicalBoundaries[boundary] ?? (boundary || "骨活性 checkpoint 输出保持研发验证边界，并由医生复核。");
});
</script>

<style scoped>
.checkpoint-panel {
  display: grid;
  gap: 12px;
  border: 1px solid var(--ov-border);
  border-radius: 8px;
  padding: 14px;
  background: var(--ov-bg-elevated);
}

header,
.heading-copy,
.section-heading,
.hash-grid a {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.heading-copy {
  min-width: 0;
  justify-content: flex-start;
}

.heading-copy > div {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.heading-copy strong,
.section-heading strong {
  color: var(--ov-text);
}

.heading-copy small,
.section-heading small {
  color: var(--ov-text-muted);
  font-size: 11px;
  overflow-wrap: anywhere;
}

.heading-icon {
  display: grid;
  flex: 0 0 30px;
  width: 30px;
  height: 30px;
  place-items: center;
  border-radius: 6px;
  background: var(--ov-bg-info);
  color: var(--ov-primary);
}

.heading-icon :deep(svg),
.hash-grid a :deep(svg) {
  width: 16px;
  height: 16px;
}

.status-badge {
  flex: 0 0 auto;
  border-radius: 999px;
  padding: 4px 9px;
  background: var(--ov-bg-warning);
  color: var(--ov-warning);
  font-size: 11px;
  font-weight: 800;
  overflow-wrap: anywhere;
}

.status-badge.ready {
  background: var(--ov-bg-success);
  color: var(--ov-success);
}

.status-badge.closed {
  background: var(--ov-bg-danger);
  color: var(--ov-danger);
}

.status-grid,
.hash-grid {
  display: grid;
  gap: 8px;
  margin: 0;
}

.status-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.hash-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.status-grid > div,
.hash-grid > div {
  min-width: 0;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 6px;
  padding: 9px;
  background: var(--ov-bg-soft);
}

dt,
dd {
  margin: 0;
  overflow-wrap: anywhere;
}

dt {
  color: var(--ov-text-muted);
  font-size: 10px;
  font-weight: 700;
}

dd {
  margin-top: 3px;
  color: var(--ov-text);
  font-size: 11px;
  font-weight: 800;
}

code {
  display: block;
  color: var(--ov-text-secondary);
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 10px;
  line-height: 1.45;
  white-space: normal;
  overflow-wrap: anywhere;
}

.integrity-section,
.failure-section {
  display: grid;
  gap: 8px;
}

.hash-grid a {
  width: fit-content;
  margin-top: 8px;
  justify-content: flex-start;
  color: var(--ov-primary-strong);
  font-size: 11px;
  font-weight: 800;
  text-decoration: none;
  overflow-wrap: anywhere;
}

.hash-grid a:hover {
  text-decoration: underline;
}

.failure-section {
  border: 1px solid var(--ov-border-subtle);
  border-left: 4px solid var(--ov-warning);
  border-radius: 6px;
  padding: 10px 12px;
  background: var(--ov-bg-warning);
}

.failure-section > strong {
  color: var(--ov-warning);
  font-size: 11px;
}

.failure-section ul {
  display: grid;
  gap: 4px;
  margin: 0;
  padding-left: 18px;
  color: var(--ov-text-secondary);
  font-size: 11px;
  line-height: 1.45;
}

.spatial-boundary,
.clinical-boundary {
  margin: 0;
  overflow-wrap: anywhere;
}

.spatial-boundary {
  display: grid;
  gap: 3px;
  border: 1px solid var(--ov-danger-border);
  border-radius: 6px;
  padding: 10px 12px;
  background: var(--ov-bg-danger);
  color: var(--ov-danger);
  font-size: 11px;
  line-height: 1.5;
}

.spatial-boundary.available {
  border-color: var(--ov-border-accent);
  background: var(--ov-bg-info);
  color: var(--ov-primary);
}

.clinical-boundary {
  color: var(--ov-text-secondary);
  font-size: 11px;
  line-height: 1.5;
}

.clinical-boundary.fixed {
  color: var(--ov-warning);
  font-weight: 700;
}

@media (max-width: 1050px) {
  header {
    align-items: flex-start;
  }

  .status-grid,
  .hash-grid {
    grid-template-columns: 1fr;
  }
}
</style>
