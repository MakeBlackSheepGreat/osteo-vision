<template>
  <section v-if="quality" class="quality-panel" aria-label="三路影像离线质控">
    <header><div><strong>三路影像离线质控</strong><small>原彩图 · 原始荧光图 · 设备叠加图</small></div><span :class="{ pass: overallStatus === 'pass' }">{{ statusLabel(overallStatus) }}</span></header>
    <div class="status-grid">
      <article><span>通道配对</span><strong>{{ pairingLabel }}</strong><small>{{ pairingDetail }}</small></article>
      <article><span>时间同步</span><strong>{{ statusLabel(syncStatus) }}</strong><small>{{ syncDetail }}</small></article>
      <article><span>几何一致性</span><strong>{{ statusLabel(geometryStatus) }}</strong><small>{{ geometryDetail }}</small></article>
      <article><span>叠加图比较</span><strong>{{ comparisonLabel }}</strong><small>{{ comparisonDetail }}</small></article>
    </div>
    <div v-if="comparisonAvailable" class="comparison">
      <dl><div><dt>MAE</dt><dd>{{ metric(comparison.mae_rgb) }}</dd></div><div><dt>RMSE</dt><dd>{{ metric(comparison.rmse_rgb) }}</dd></div><div><dt>SSIM</dt><dd>{{ metric(comparison.ssim_luma) }}</dd></div><div><dt>边缘差异</dt><dd>{{ percent(comparison.edge_disagreement) }}</dd></div></dl>
      <figure v-if="heatmapPath"><img :src="previewUrl ? previewUrl(heatmapPath) : heatmapPath" alt="设备叠加图与软件融合图差异热图" /><figcaption><strong>差异热图</strong><a v-if="downloadUrl" :href="downloadUrl(heatmapPath)">下载证据</a></figcaption></figure>
    </div>
    <p v-else class="degradation" role="status">安全降级已启用：{{ comparisonDetail }}。分析仍可继续，叠加图差异指标和热图保持不可用。</p>
    <p class="boundary">{{ medicalBoundary }}</p><p class="boundary">设备叠加图仅用于显示一致性和证据核对，模型输入始终限定为原彩图与原始荧光图。</p>
  </section>
</template>
<script setup lang="ts">
import { computed } from "vue";
type UrlBuilder = (path: string) => string;
const props = defineProps<{ quality?: Record<string, unknown> | null; previewUrl?: UrlBuilder; downloadUrl?: UrlBuilder }>();
function record(v: unknown): Record<string, unknown> { return v && typeof v === "object" && !Array.isArray(v) ? v as Record<string, unknown> : {}; }
function text(v: unknown): string { return typeof v === "string" ? v : ""; } function number(v: unknown): number | null { return typeof v === "number" && Number.isFinite(v) ? v : null; }
const overall = computed(() => record(props.quality?.overall)); const sync = computed(() => record(props.quality?.synchronization)); const geometry = computed(() => record(props.quality?.geometry)); const comparison = computed(() => record(props.quality?.overlay_comparison));
const overallStatus = computed(() => text(overall.value.status) || "review_required"); const syncStatus = computed(() => text(sync.value.status) || "unavailable"); const geometryStatus = computed(() => text(geometry.value.status) || "unavailable"); const comparisonAvailable = computed(() => comparison.value.available === true); const heatmapPath = computed(() => text(comparison.value.difference_heatmap_path));
const pairingLabel = computed(() => { const c = Array.isArray(overall.value.model_input_channels) ? overall.value.model_input_channels : []; return c.includes("white_light") && c.includes("fluorescence") ? "白光/荧光已成对" : "等待成对输入"; }); const pairingDetail = computed(() => comparisonAvailable.value ? "设备叠加证据已关联" : "设备叠加图为可选证据");
const syncDetail = computed(() => { const d = number(sync.value.white_fluorescence_delta_ms), t = number(sync.value.tolerance_ms); return d === null ? "缺少时间戳，需人工核对" : `白光/荧光偏差 ${d.toFixed(1)} ms${t === null ? "" : `（阈值 ${t.toFixed(1)} ms）`}`; });
const geometryDetail = computed(() => geometry.value.pixel_comparison_allowed === true ? "宽高比允许像素级比较" : "尺寸或宽高比需复核"); const comparisonLabel = computed(() => comparisonAvailable.value ? statusLabel(text(comparison.value.status)) : "安全降级"); const comparisonDetail = computed(() => comparisonAvailable.value ? "设备/软件叠加差异已量化" : reasonLabel(text(comparison.value.reason))); const medicalBoundary = computed(() => text(overall.value.medical_boundary) || text(comparison.value.boundary) || "离线工程质控结果不得用于疾病判断或手术边界确定。");
function statusLabel(v: string): string { return v === "pass" ? "通过" : v === "unavailable" ? "不可用" : "需要复核"; } function reasonLabel(v: string): string { if (v === "device_or_software_overlay_missing") return "缺少设备叠加图或软件融合图"; if (v === "geometry_unusable") return "几何一致性不足"; return "缺少可比较证据"; } function metric(v: unknown): string { const n = number(v); return n === null ? "未记录" : n.toFixed(4); } function percent(v: unknown): string { const n = number(v); return n === null ? "未记录" : `${(n * 100).toFixed(2)}%`; }
</script>
<style scoped>
.quality-panel{display:grid;gap:12px;padding:14px;border:1px solid var(--ov-border);border-radius:8px;background:var(--ov-bg-elevated)}header,header div,figcaption{display:flex;align-items:center;justify-content:space-between;gap:8px}header div{align-items:flex-start;flex-direction:column}header small{color:var(--ov-text-muted)}header>span{color:var(--ov-warning);font-size:11px;font-weight:800}header>span.pass{color:var(--ov-success)}.status-grid,dl{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.status-grid article,dl div{display:grid;gap:4px;min-width:0;padding:9px;background:var(--ov-bg-soft)}.status-grid span,dt{color:var(--ov-text-muted);font-size:10px}.status-grid strong,dd{margin:0;color:var(--ov-text);font-size:12px;overflow-wrap:anywhere}.status-grid small{color:var(--ov-text-secondary);line-height:1.4;overflow-wrap:anywhere}.comparison{display:grid;grid-template-columns:minmax(0,1fr) minmax(260px,.8fr);gap:10px}dl{margin:0;grid-template-columns:repeat(2,minmax(0,1fr))}figure{min-width:0;margin:0;overflow:hidden;border:1px solid var(--ov-border);border-radius:6px;background:var(--ov-bg-soft)}figure img{display:block;width:100%;max-height:240px;object-fit:contain}figcaption{padding:8px;font-size:11px}a{color:var(--ov-accent);font-weight:700}p{margin:0;color:var(--ov-text-secondary);font-size:11px;line-height:1.5;overflow-wrap:anywhere}.degradation,.boundary{color:var(--ov-warning)}@media(max-width:1100px){.status-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.comparison{grid-template-columns:1fr}}
</style>
