export interface AnalysisPreviewPanel {
  title: string;
  tag: string;
  label: string;
  scale: string;
  path?: string;
  previewSrc?: string;
  overlays?: AnalysisPreviewOverlay[];
}

export interface AnalysisPreviewOverlay {
  key: string;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
  tone: "candidate" | "roi";
}

export interface HotspotTimelineItem {
  key: string;
  frameLabel: string;
  timestampLabel: string;
  candidateCountLabel: string;
  positiveAreaLabel: string;
  roiAreaLabel: string;
  score: number;
  roiScore: number;
  candidateCount: number;
  previewSrc?: string;
}

export interface HotspotFrameDetail {
  key: string;
  frameIndex: number | null;
  timestampSec: number | null;
  frameLabel: string;
  timestampLabel: string;
  candidateCountLabel: string;
  positiveAreaLabel: string;
  roiAreaLabel: string;
  topBBoxLabel: string;
  evidenceLabel: string;
  domainBoundary: string;
  reviewRequired: boolean;
  evidenceHref?: string;
  overlayHref?: string;
  maskHref?: string;
}

export interface TimelineTraceItem {
  key: string;
  frameLabel: string;
  rankLabel: string;
  scoreLabel: string;
  statusLabel: string;
  duplicateLabel: string;
}

export interface TimelineManifestSummary {
  manifestPath: string;
  manifestHref?: string;
  scopeLabel: string;
  samplingLabel: string;
  frameCountLabel: string;
  durationLabel: string;
  fpsLabel: string;
  coverageLabel: string;
  selectedFrameCountLabel: string;
  candidateFrameCountLabel: string;
  duplicateCountLabel: string;
  skippedDuplicateCountLabel: string;
  traceItems: TimelineTraceItem[];
  duplicateItems: TimelineTraceItem[];
}

export interface FusionEvidenceSummary {
  algorithmVersionLabel: string;
  methodLabel: string;
  thresholdLabel: string;
  alphaLabel: string;
  backgroundLabel: string;
  registrationLabel: string;
  translationLabel: string;
  responseLabel: string;
  resizeLabel: string;
  colorbarPath?: string;
  colorbarPreviewSrc?: string;
}

export type HotspotTimelineFilter = "all" | "positive_area" | "roi_hit" | "with_candidates";

export const hotspotTimelineFilterOptions: Array<{ value: HotspotTimelineFilter; label: string }> = [
  { value: "all", label: "全部" },
  { value: "positive_area", label: "阳性面积" },
  { value: "roi_hit", label: "ROI 命中" },
  { value: "with_candidates", label: "有候选" },
];

interface RunLike {
  fused_outputs?: Record<string, unknown>;
}

type PreviewUrlBuilder = (path: string) => string;

export function videoPreviewPanelsFromRun(
  run: RunLike | null | undefined,
  previewUrl: PreviewUrlBuilder,
  selectedHotspotKey = "",
): AnalysisPreviewPanel[] {
  const hotspots = hotspotOutputsFromRun(run);
  if (hotspots.length) {
    const selectedHotspot =
      hotspots.find((hotspot, index) => hotspotKey(hotspot, index) === selectedHotspotKey) ?? hotspots[0];
    const lesionEvidence = recordFrom(selectedHotspot.lesion_evidence) ? selectedHotspot.lesion_evidence : {};
    const sourcePath = stringFrom(selectedHotspot.source_path);
    const overlayPath = stringFrom(lesionEvidence.overlay_path);
    const maskPath = stringFrom(lesionEvidence.mask_path);
    const pseudoColorPath = stringFrom(lesionEvidence.pseudo_color_path);
    const frameIndex = stringFrom(selectedHotspot.frame_index) || "-";
    const timestamp = formatSeconds(selectedHotspot.timestamp_sec);
    const panels = [
      panelFromPath("关键帧", `帧序号: ${frameIndex}`, `时间: ${timestamp}`, "MP4", sourcePath, previewUrl),
      panelFromPath("热点叠加", `帧序号: ${frameIndex}`, "候选区叠加预览", "mask + frame", overlayPath, previewUrl),
      panelFromPath("热点掩膜", `帧序号: ${frameIndex}`, "二值 ROI 掩膜", "threshold", maskPath || pseudoColorPath, previewUrl),
    ];
    return panels.filter((item): item is AnalysisPreviewPanel => item !== null);
  }

  return keyframesFromRun(run)
    .slice(0, 3)
    .map((frame, index) =>
      panelFromPath(
        `关键帧 ${index + 1}`,
        `帧序号: ${stringFrom(frame.frame_index) || "-"}`,
        `时间: ${formatSeconds(frame.timestamp_sec)}`,
        "MP4",
        stringFrom(frame.path) || stringFrom(frame.preview_path),
        previewUrl,
      ),
    )
    .filter((item): item is AnalysisPreviewPanel => item !== null);
}

export function hotspotOutputsFromRun(run: RunLike | null | undefined): Array<Record<string, unknown>> {
  const hotspotOutputs = run?.fused_outputs?.hotspot_outputs;
  return Array.isArray(hotspotOutputs) ? hotspotOutputs.filter(recordFrom) : [];
}

export function keyframesFromRun(run: RunLike | null | undefined): Array<Record<string, unknown>> {
  const keyframes = run?.fused_outputs?.keyframes;
  return Array.isArray(keyframes) ? keyframes.filter(recordFrom) : [];
}

export function candidateOverlaysFromRegions(
  candidates: Array<{ candidate_id: string; risk_type?: string; metadata?: Record<string, unknown> | null }>,
): AnalysisPreviewOverlay[] {
  return candidates
    .map((candidate) => {
      const geometry = recordFrom(candidate.metadata?.bbox_normalized) ? candidate.metadata.bbox_normalized : null;
      return overlayFromGeometry({
        key: `candidate-${candidate.candidate_id}`,
        label: candidate.risk_type || "AI 候选区",
        geometry,
        tone: "candidate",
      });
    })
    .filter((overlay): overlay is AnalysisPreviewOverlay => overlay !== null);
}

export function roiOverlaysFromRegions(
  rois: Array<{ roi_id: string; label?: string | null; source?: string; geometry?: Record<string, unknown> | null }>,
): AnalysisPreviewOverlay[] {
  return rois
    .map((roi) =>
      overlayFromGeometry({
        key: `roi-${roi.roi_id}`,
        label: roi.label || (roi.source === "ai" ? "AI ROI" : "手动 ROI"),
        geometry: roi.geometry,
        tone: "roi",
      }),
    )
    .filter((overlay): overlay is AnalysisPreviewOverlay => overlay !== null);
}

export function hotspotTimelineFromRun(
  run: RunLike | null | undefined,
  previewUrl: PreviewUrlBuilder,
): HotspotTimelineItem[] {
  return hotspotOutputsFromRun(run).map((hotspot, index) => {
    const quantification = recordFrom(hotspot.quantification) ? hotspot.quantification : {};
    const lesionEvidence = recordFrom(hotspot.lesion_evidence) ? hotspot.lesion_evidence : {};
    const sourcePath = stringFrom(lesionEvidence.overlay_path) || stringFrom(hotspot.source_path);
    const frameIndex = stringFrom(hotspot.frame_index) || stringFrom(hotspot.frame_order) || String(index + 1);
    const positiveArea = numberFrom(quantification.positive_area_fraction);
    const roiArea = numberFrom(quantification.roi_positive_area_fraction);
    const componentCount = numberFrom(quantification.component_count);
    return {
      key: hotspotKey(hotspot, index),
      frameLabel: `帧 ${frameIndex}`,
      timestampLabel: formatSeconds(hotspot.timestamp_sec),
      candidateCountLabel: `${Math.max(0, Math.round(componentCount))} 个候选`,
      positiveAreaLabel: formatPercent(positiveArea),
      roiAreaLabel: roiArea > 0 ? formatPercent(roiArea) : "未命中 ROI",
      score: positiveArea,
      roiScore: roiArea,
      candidateCount: Math.max(0, Math.round(componentCount)),
      previewSrc: sourcePath ? previewUrl(sourcePath) : undefined,
    };
  });
}

export function filterHotspotTimelineItems(
  items: HotspotTimelineItem[],
  filter: HotspotTimelineFilter,
): HotspotTimelineItem[] {
  if (filter === "positive_area") return items.filter((item) => item.score > 0);
  if (filter === "roi_hit") return items.filter((item) => item.roiScore > 0);
  if (filter === "with_candidates") return items.filter((item) => item.candidateCount > 0);
  return items;
}

export function hotspotFrameDetailsFromRun(
  run: RunLike | null | undefined,
  previewUrl: PreviewUrlBuilder,
): HotspotFrameDetail[] {
  const explicitDetails = run?.fused_outputs?.frame_details;
  const sourceItems = Array.isArray(explicitDetails)
    ? explicitDetails.filter(recordFrom)
    : hotspotOutputsFromRun(run).map((hotspot) => frameDetailLikeFromHotspot(hotspot));
  return sourceItems.map((detail, index) => {
    const frameIndex = stringFrom(detail.frame_index) || stringFrom(detail.frame_order) || String(index + 1);
    const key = stringFrom(detail.frame_key) || `${frameIndex}-${index}`;
    const componentCount = Math.max(0, Math.round(numberFrom(detail.component_count)));
    const positiveArea = numberFrom(detail.positive_area_fraction);
    const roiArea = numberFrom(detail.roi_positive_area_fraction);
    const evidencePath = stringFrom(detail.evidence_path) || stringFrom(detail.source_path);
    const overlayPath = stringFrom(detail.overlay_path);
    const maskPath = stringFrom(detail.mask_path) || stringFrom(detail.pseudo_color_path);
    return {
      key,
      frameIndex: finiteNumberOrNull(detail.frame_index),
      timestampSec: finiteNumberOrNull(detail.timestamp_sec),
      frameLabel: `帧 ${frameIndex}`,
      timestampLabel: formatSeconds(detail.timestamp_sec),
      candidateCountLabel: `${componentCount} 个候选`,
      positiveAreaLabel: formatPercent(positiveArea),
      roiAreaLabel: roiArea > 0 ? formatPercent(roiArea) : "未命中 ROI",
      topBBoxLabel: bboxLabel(detail.top_component_bbox_xyxy) || bboxLabel(detail.bbox_xyxy) || "暂无",
      evidenceLabel: shortPath(overlayPath || evidencePath || maskPath),
      domainBoundary:
        stringFrom(detail.domain_boundary) ||
        "Heuristic keyframe hotspot analysis; requires physician review and is not a diagnosis.",
      reviewRequired: booleanFrom(detail.review_required) || componentCount > 0 || positiveArea > 0,
      evidenceHref: evidencePath ? previewUrl(evidencePath) : undefined,
      overlayHref: overlayPath ? previewUrl(overlayPath) : undefined,
      maskHref: maskPath ? previewUrl(maskPath) : undefined,
    };
  });
}

export function selectedHotspotFrameDetailFromRun(
  run: RunLike | null | undefined,
  previewUrl: PreviewUrlBuilder,
  selectedKey: string,
): HotspotFrameDetail | null {
  const details = hotspotFrameDetailsFromRun(run, previewUrl);
  if (!details.length) return null;
  return details.find((detail) => detail.key === selectedKey) ?? details[0];
}

export function timelineManifestSummaryFromRun(
  run: RunLike | null | undefined,
  downloadUrl: PreviewUrlBuilder,
): TimelineManifestSummary | null {
  const fusedOutputs = run?.fused_outputs ?? {};
  const summary = recordFrom(fusedOutputs.timeline_summary) ? fusedOutputs.timeline_summary : {};
  const manifestPath = stringFrom(summary.timeline_manifest_path) || stringFrom(fusedOutputs.timeline_manifest_path);
  if (!manifestPath) return null;
  const frameCount = numberFrom(summary.frame_count);
  const durationSec = numberFrom(summary.duration_sec);
  const fps = numberFrom(summary.fps);
  const stride = Math.max(1, Math.round(numberFrom(summary.timeline_stride) || 1));
  const selectedCount = Math.max(0, Math.round(numberFrom(summary.selected_frame_count)));
  const candidateCount = Math.max(0, Math.round(numberFrom(summary.candidate_frame_count)));
  const duplicateCount = Math.max(0, Math.round(numberFrom(summary.duplicate_candidate_count)));
  const skippedDuplicateCount = Math.max(0, Math.round(numberFrom(summary.skipped_duplicate_count)));
  const traceItems = traceItemsFromValue(summary.candidate_trace).slice(0, 6);
  const duplicateItems = traceItemsFromValue(summary.duplicate_trace).slice(0, 6);
  return {
    manifestPath,
    manifestHref: downloadUrl(manifestPath),
    scopeLabel: scopeLabel(stringFrom(summary.timeline_scope)),
    samplingLabel: stringFrom(summary.sampling_strategy) || "暂无",
    frameCountLabel: frameCount > 0 ? `${Math.round(frameCount)} 帧` : "暂无",
    durationLabel: durationSec > 0 ? formatSeconds(durationSec) : "暂无",
    fpsLabel: fps > 0 ? `${fps.toFixed(2)} fps` : "暂无",
    coverageLabel: stride <= 1 ? "逐帧索引" : `每 ${stride} 帧索引`,
    selectedFrameCountLabel: `${selectedCount} 帧`,
    candidateFrameCountLabel: `${candidateCount} 帧`,
    duplicateCountLabel: `${duplicateCount} 帧`,
    skippedDuplicateCountLabel: `${skippedDuplicateCount} 帧`,
    traceItems,
    duplicateItems,
  };
}

export function fusionEvidenceSummaryFromRun(
  run: RunLike | null | undefined,
  previewUrl: PreviewUrlBuilder,
): FusionEvidenceSummary | null {
  const fusedOutputs = run?.fused_outputs ?? {};
  const fusion = recordFrom(fusedOutputs.fusion) ? fusedOutputs.fusion : {};
  const outputs = recordFrom(fusedOutputs.outputs) ? fusedOutputs.outputs : {};
  const colorbar = recordFrom(fusion.colorbar) ? fusion.colorbar : {};
  const background = recordFrom(fusion.background_correction) ? fusion.background_correction : {};
  const registration = recordFrom(fusion.registration_details) ? fusion.registration_details : {};
  const quantification = recordFrom(fusedOutputs.quantification) ? fusedOutputs.quantification : {};
  const colorbarPath = stringFrom(outputs.colorbar_path) || stringFrom(colorbar.path);
  const hasFusionEvidence = Boolean(Object.keys(fusion).length || colorbarPath);
  if (!hasFusionEvidence) return null;

  const threshold = finiteNumberOrNull(colorbar.threshold_marker) ?? finiteNumberOrNull(quantification.threshold);
  const alpha = finiteNumberOrNull(fusion.alpha);
  const registrationApplied = registration.applied === true;
  const registrationMethod = stringFrom(registration.method) || stringFrom(fusion.registration);
  const translation = arrayNumberLabel(registration.translation_xy, "px");
  const response = finiteNumberOrNull(registration.response);
  const backgroundApplied = background.applied === true;
  const backgroundPercentile = finiteNumberOrNull(background.percentile);
  const backgroundBaseline = finiteNumberOrNull(background.baseline);
  return {
    algorithmVersionLabel: stringFrom(fusion.algorithm_version) || "暂无",
    methodLabel: methodLabel(stringFrom(fusion.method)),
    thresholdLabel: threshold === null ? "暂无" : threshold.toFixed(2),
    alphaLabel: alpha === null ? "暂无" : alpha.toFixed(2),
    backgroundLabel: [
      backgroundApplied ? "已扣除" : "未扣除",
      backgroundPercentile === null ? "" : `P${trimNumber(backgroundPercentile)}`,
      backgroundBaseline === null ? "" : `baseline ${trimNumber(backgroundBaseline)}`,
    ]
      .filter(Boolean)
      .join(" · "),
    registrationLabel: [
      registrationApplied ? "已应用" : "未应用",
      registrationMethod ? registrationMethodLabel(registrationMethod) : "",
      stringFrom(registration.reason),
    ]
      .filter(Boolean)
      .join(" · "),
    translationLabel: translation || "暂无",
    responseLabel: response === null ? "暂无" : response.toFixed(3),
    resizeLabel: sizeResizeLabel(fusion),
    colorbarPath: colorbarPath || undefined,
    colorbarPreviewSrc: colorbarPath ? previewUrl(colorbarPath) : undefined,
  };
}

function hotspotKey(hotspot: Record<string, unknown>, index: number): string {
  const frameIndex = stringFrom(hotspot.frame_index) || stringFrom(hotspot.frame_order) || String(index + 1);
  return `${frameIndex}-${index}`;
}

function frameDetailLikeFromHotspot(hotspot: Record<string, unknown>): Record<string, unknown> {
  const quantification = recordFrom(hotspot.quantification) ? hotspot.quantification : {};
  const lesionEvidence = recordFrom(hotspot.lesion_evidence) ? hotspot.lesion_evidence : {};
  const segmentationMask = recordFrom(hotspot.segmentation_mask) ? hotspot.segmentation_mask : {};
  const candidates = Array.isArray(lesionEvidence.candidates) ? lesionEvidence.candidates.filter(recordFrom) : [];
  const topComponent = candidates[0] ?? {};
  return {
    frame_order: hotspot.frame_order,
    frame_index: hotspot.frame_index,
    timestamp_sec: hotspot.timestamp_sec,
    source_path: hotspot.source_path,
    evidence_path: hotspot.source_path,
    overlay_path: lesionEvidence.overlay_path,
    mask_path: segmentationMask.path,
    pseudo_color_path: lesionEvidence.pseudo_color_path,
    positive_area_fraction: quantification.positive_area_fraction,
    roi_positive_area_fraction: quantification.roi_positive_area_fraction,
    component_count: quantification.component_count,
    top_component_bbox_xyxy: topComponent.bbox_xyxy,
    domain_boundary: hotspot.domain_boundary,
    review_required: true,
  };
}

function traceItemsFromValue(value: unknown): TimelineTraceItem[] {
  if (!Array.isArray(value)) return [];
  return value.filter(recordFrom).map((item, index) => {
    const frameIndex = stringFrom(item.frame_index) || String(index + 1);
    const score = finiteNumberOrNull(item.selection_score);
    const duplicateOf = stringFrom(item.duplicate_of_frame_index);
    const duplicateSimilarity = finiteNumberOrNull(item.duplicate_similarity);
    return {
      key: `${frameIndex}-${index}`,
      frameLabel: `帧 ${frameIndex}`,
      rankLabel: item.selection_rank ? `#${stringFrom(item.selection_rank)}` : "-",
      scoreLabel: score === null ? "-" : score.toFixed(3),
      statusLabel: traceStatusLabel(item),
      duplicateLabel: duplicateOf
        ? `近似帧 ${duplicateOf}${duplicateSimilarity === null ? "" : ` · ${duplicateSimilarity.toFixed(3)}`}`
        : "无重复",
    };
  });
}

function traceStatusLabel(item: Record<string, unknown>): string {
  if (item.skipped_as_duplicate === true) return "重复跳过";
  if (item.selected_after_duplicate_backfill === true) return "回补选中";
  if (item.selected === true) return "已选中";
  return "候选";
}

function scopeLabel(value: string): string {
  if (value === "full_duration_index_with_scored_candidates") return "全时长低频索引";
  return value || "暂无";
}

function overlayFromGeometry({
  key,
  label,
  geometry,
  tone,
}: {
  key: string;
  label: string;
  geometry?: Record<string, unknown> | null;
  tone: "candidate" | "roi";
}): AnalysisPreviewOverlay | null {
  if (!recordFrom(geometry) || geometry.type !== "rect") return null;
  const x = clampUnitNumber(geometry.x);
  const y = clampUnitNumber(geometry.y);
  const width = clampUnitNumber(geometry.width);
  const height = clampUnitNumber(geometry.height);
  if (width <= 0 || height <= 0) return null;
  return {
    key,
    label,
    x,
    y,
    width: Math.min(width, 1 - x),
    height: Math.min(height, 1 - y),
    tone,
  };
}

function panelFromPath(
  title: string,
  tag: string,
  label: string,
  scale: string,
  path: string,
  previewUrl: PreviewUrlBuilder,
): AnalysisPreviewPanel | null {
  if (!path) return null;
  return {
    title,
    tag,
    label,
    scale,
    path,
    previewSrc: previewUrl(path),
  };
}

function recordFrom(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringFrom(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return "";
}

function numberFrom(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

function finiteNumberOrNull(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function booleanFrom(value: unknown): boolean {
  return value === true || value === "true";
}

function bboxLabel(value: unknown): string {
  if (!Array.isArray(value) || value.length !== 4) return "";
  return value.map((item) => Math.round(numberFrom(item))).join(", ");
}

function arrayNumberLabel(value: unknown, suffix = ""): string {
  if (!Array.isArray(value) || !value.length) return "";
  const numbers = value
    .map((item) => finiteNumberOrNull(item))
    .filter((item): item is number => item !== null)
    .map((item) => trimNumber(item));
  if (!numbers.length) return "";
  return `${numbers.join(", ")}${suffix ? ` ${suffix}` : ""}`;
}

function sizeResizeLabel(fusion: Record<string, unknown>): string {
  const whiteSize = arrayNumberLabel(fusion.white_light_size);
  const fluorescenceSize = arrayNumberLabel(fusion.fluorescence_original_size);
  const resized = fusion.fluorescence_resized_to_white_light === true;
  if (!whiteSize && !fluorescenceSize) return "暂无";
  const resizeLabel = resized ? "已重采样" : "原始匹配";
  return `${resizeLabel}${whiteSize ? ` · 白光 ${whiteSize}` : ""}${fluorescenceSize ? ` · 荧光 ${fluorescenceSize}` : ""}`;
}

function methodLabel(value: string): string {
  const labels: Record<string, string> = {
    background_corrected_registered_alpha_blend_pseudocolor: "背景扣除 + 平移配准 + 伪彩融合",
  };
  return labels[value] ?? (value || "暂无");
}

function registrationMethodLabel(value: string): string {
  const labels: Record<string, string> = {
    phase_correlation_translation: "相位相关平移",
    disabled: "已关闭",
    unsupported: "不支持",
  };
  return labels[value] ?? value;
}

function trimNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
}

function shortPath(path: string): string {
  if (!path) return "暂无";
  return path.split(/[\\/]/).filter(Boolean).at(-1) ?? path;
}

function clampUnitNumber(value: unknown): number {
  const numeric = numberFrom(value);
  return Math.max(0, Math.min(1, numeric));
}

function formatSeconds(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "-";
  return `${value.toFixed(2)}s`;
}

function formatPercent(value: number): string {
  return `${(Math.max(0, value) * 100).toFixed(2)}%`;
}
