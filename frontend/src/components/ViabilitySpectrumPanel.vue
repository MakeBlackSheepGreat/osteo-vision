<template>
  <section v-if="spectrum" class="spectrum-panel" aria-label="骨活性连续谱">
    <header>
      <div>
          <strong>规则派生骨活性连续谱</strong>
        <small>{{ gateStatusLabel }}</small>
      </div>
      <span :class="{ ready: spatialCandidatesAvailable }">{{ statusLabel }}</span>
    </header>

    <div class="candidate-grid" aria-label="骨活性空间候选统计">
      <article v-for="candidate in candidates" :key="candidate.key" :class="`candidate candidate--${candidate.tone}`">
        <div class="candidate__heading">
          <strong>{{ candidate.label }}</strong>
          <span>{{ candidate.available ? formatPercent(candidate.fraction) : "待复核" }}</span>
        </div>
        <p v-if="candidate.available">
          骨面占比 {{ formatPercent(candidate.fraction) }} · {{ formatPixels(candidate.areaPx) }}
        </p>
        <p v-else>可信骨面门控完成后生成空间区域。</p>
        <small v-if="candidate.available && candidate.sources.length">来源 {{ candidate.sources.join("、") }}</small>
        <a
          v-if="candidate.available && candidate.path && previewUrl"
          :href="previewUrl(candidate.path)"
          target="_blank"
          rel="noopener noreferrer"
        >查看候选掩膜</a>
      </article>
    </div>

    <div v-if="activityScorePath || safeClassMapPath" class="evidence-grid" aria-label="骨活性图层证据">
      <figure v-if="activityScorePath">
        <img v-if="previewUrl" :src="previewUrl(activityScorePath)" alt="连续骨活性评分图" />
        <figcaption>
          <strong>连续活性评分图</strong>
          <a v-if="downloadUrl" :href="downloadUrl(activityScorePath)">下载证据</a>
        </figcaption>
      </figure>
      <figure v-if="safeClassMapPath">
        <img v-if="previewUrl" :src="previewUrl(safeClassMapPath)" alt="骨活性三分类与无法判断区图" />
        <figcaption>
          <strong>三分类与无法判断区图</strong>
          <a v-if="downloadUrl" :href="downloadUrl(safeClassMapPath)">下载证据</a>
        </figcaption>
      </figure>
    </div>

    <dl>
      <div><dt>连续活动评分</dt><dd>{{ activityAvailable ? activityScaleLabel : "暂无" }}</dd></div>
      <div><dt>分类阈值</dt><dd>{{ thresholdLabel }}</dd></div>
      <div><dt>校准状态</dt><dd>{{ calibrationLabel }}</dd></div>
    </dl>
    <p>{{ confidenceStatement }}</p>
    <p v-if="!spatialCandidatesAvailable" class="degradation" role="status">
      安全降级已启用：连续评分仅作为全帧荧光/灌注参考，三类空间候选、无法判断区、面积比例和分类图层保持不可用。
    </p>
    <p class="boundary">空间候选和边界需医生复核；当前输出不得解释为可切除比例或切除成功率。</p>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";

type UrlBuilder = (path: string) => string;
type CandidateTone = "low" | "transition" | "high" | "ignore";

interface CandidateView {
  key: string;
  label: string;
  tone: CandidateTone;
  available: boolean;
  areaPx: number | null;
  fraction: number | null;
  path: string;
  sources: string[];
}

const props = defineProps<{
  spectrum?: Record<string, unknown> | null;
  previewUrl?: UrlBuilder;
  downloadUrl?: UrlBuilder;
}>();

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function pathFrom(value: Record<string, unknown>): string {
  for (const key of ["path", "mask_path", "preview_path"]) {
    if (typeof value[key] === "string" && value[key]) return value[key] as string;
  }
  return "";
}

const spatialCandidatesAvailable = computed(() => (
  props.spectrum?.available === true && props.spectrum?.spatial_effect_applied === true
));
const statusLabel = computed(() => spatialCandidatesAvailable.value ? "医生复核可用" : "安全降级");
const gateStatusLabel = computed(() => {
  const status = String(props.spectrum?.status || "pending_reviewed_bone_gate");
  return status === "available_for_physician_review" ? "可信骨面门控已应用" : "等待可信医生骨面门控";
});
const activityScore = computed(() => record(props.spectrum?.activity_score));
const activityAvailable = computed(() => activityScore.value.available === true);
const activityScorePath = computed(() => pathFrom(activityScore.value));
const safeClassMapPath = computed(() => {
  if (!spatialCandidatesAvailable.value) return "";
  return typeof props.spectrum?.activity_class_map_path === "string" ? props.spectrum.activity_class_map_path : "";
});
const activityScaleLabel = computed(() => {
  const scale = activityScore.value.scale;
  return Array.isArray(scale) && scale.length === 2 ? `${scale[0]}–${scale[1]}` : "0.00–1.00";
});
const calibrationLabel = computed(() => props.spectrum?.calibration_status === "pending_target_domain_validation"
  ? "等待目标域验证"
  : String(props.spectrum?.calibration_status || "未记录"));
const confidenceStatement = computed(() => String(props.spectrum?.confidence_statement || "置信度仅表示信号候选可信程度。"));
const thresholdLabel = computed(() => {
  const thresholds = record(props.spectrum?.thresholds);
  const low = finiteNumber(thresholds.low_max);
  const high = finiteNumber(thresholds.high_min);
  return low === null || high === null ? "未记录" : `低 ≤ ${low.toFixed(2)}；高 ≥ ${high.toFixed(2)}`;
});

function candidate(key: string, fallbackLabel: string, tone: CandidateTone): CandidateView {
  const value = record(props.spectrum?.[key]);
  const permitted = spatialCandidatesAvailable.value && value.available === true;
  const sourceValues = Array.isArray(value.sources) ? value.sources : [];
  return {
    key,
    label: typeof value.label === "string" ? value.label : fallbackLabel,
    tone,
    available: permitted,
    areaPx: permitted ? finiteNumber(value.positive_area_px) : null,
    fraction: permitted ? finiteNumber(value.bone_gate_fraction) : null,
    path: permitted ? pathFrom(value) : "",
    sources: permitted ? sourceValues.map(sourceName).filter(Boolean) : [],
  };
}

function sourceName(value: unknown): string {
  if (typeof value === "string") return sourceLabel(value);
  const source = record(value);
  return typeof source.source_type === "string" ? sourceLabel(source.source_type) : "";
}

function sourceLabel(value: string): string {
  return ({
    model_uncertainty: "模型不确定性",
    signal_uncertainty: "信号不确定性",
    uncertain_mask: "模型不确定性",
    physician_ignore: "医生标注",
    physician_ignore_mask: "医生标注",
    explicit_ignore_mask: "显式排除",
    quality_exclusion: "质量排除",
    compatibility_default_empty: "未提供排除区域",
  } as Record<string, string>)[value] ?? value;
}

const candidates = computed(() => [
  candidate("low_activity_candidate", "低活性候选", "low"),
  candidate("transition_candidate", "过渡复核区", "transition"),
  candidate("high_activity_candidate", "高活性参考", "high"),
  candidate("ignore_region", "无法判断区", "ignore"),
]);

function formatPercent(value: number | null): string {
  return value === null ? "未记录" : `${(Math.max(0, Math.min(1, value)) * 100).toFixed(1)}%`;
}

function formatPixels(value: number | null): string {
  return value === null ? "面积未记录" : `${Math.max(0, Math.round(value)).toLocaleString("zh-CN")} px`;
}
</script>

<style scoped>
.spectrum-panel { display: grid; gap: 12px; border: 1px solid var(--ov-border); border-radius: 8px; padding: 14px; background: var(--ov-bg-elevated); }
header, header > div, .candidate__heading, figcaption { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
header > div { align-items: flex-start; flex-direction: column; }
header strong { color: var(--ov-text); }
header small { color: var(--ov-text-muted); font-size: 11px; }
header > span { color: var(--ov-warning); font-size: 11px; font-weight: 800; }
header > span.ready { color: var(--ov-success); }
.candidate-grid, .evidence-grid, dl { display: grid; gap: 8px; }
.candidate-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.candidate { min-width: 0; padding: 10px; border: 1px solid var(--ov-border); border-top: 4px solid #52657a; border-radius: 6px; background: var(--ov-bg-soft); }
.candidate--transition { border-top-color: #b07c22; }
.candidate--high { border-top-color: #27876f; }
.candidate--ignore { border-top-color: #68717c; }
.candidate__heading strong, .candidate__heading span { overflow-wrap: anywhere; color: var(--ov-text); font-size: 12px; }
.candidate p { min-height: 32px; }
.candidate small { color: var(--ov-text-muted); font-size: 10px; overflow-wrap: anywhere; }
a { color: var(--ov-accent); font-size: 11px; font-weight: 700; overflow-wrap: anywhere; }
.evidence-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
figure { min-width: 0; margin: 0; overflow: hidden; border: 1px solid var(--ov-border); border-radius: 6px; background: var(--ov-bg-soft); }
figure img { display: block; width: 100%; max-height: 220px; object-fit: contain; background: var(--ov-bg-soft); }
figcaption { padding: 8px; color: var(--ov-text); font-size: 11px; }
dl { margin: 0; }
dl { grid-template-columns: repeat(3, minmax(0, 1fr)); }
dl div { min-width: 0; padding: 8px; background: var(--ov-bg-soft); }
dt, dd { margin: 0; overflow-wrap: anywhere; }
dt { color: var(--ov-text-muted); font-size: 10px; }
dd { color: var(--ov-text); font-size: 11px; font-weight: 800; }
p { margin: 0; color: var(--ov-text-secondary); font-size: 11px; line-height: 1.5; overflow-wrap: anywhere; }
.degradation, .boundary { color: var(--ov-warning); }
@media (max-width: 1050px) { .candidate-grid, dl { grid-template-columns: 1fr; } .evidence-grid { grid-template-columns: 1fr; } }
</style>
