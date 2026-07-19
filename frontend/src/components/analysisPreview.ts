import {
  arrayNumberLabel,
  bboxLabel,
  booleanFrom,
  clampUnitNumber,
  finiteNumberOrNull,
  formatPercent,
  formatSeconds,
  methodLabel,
  numberFrom,
  recordFrom,
  registrationMethodLabel,
  shortPath,
  sizeResizeLabel,
  stringFrom,
  trimNumber,
} from "@/components/analysisPreviewFormatters";

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
  displayAllowed?: boolean;
  stale?: boolean;
  frameAgeLabel?: string;
  evidenceHref?: string;
  overlayHref?: string;
  maskHref?: string;
  boneGateMaskHref?: string;
  boneGateOverlayHref?: string;
  boneGateStatusLabel?: string;
  riskMaskHref?: string;
  uncertainMaskHref?: string;
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

export interface VideoPlaybackAnalysis {
  sourcePath: string;
  sourceLabel: string;
  videoSrc: string;
  modeLabel: string;
  analysisScopeLabel: string;
  frameDetails: HotspotFrameDetail[];
  overlayReviewVideoPath?: string;
  overlayReviewVideoSrc?: string;
  maskReviewVideoPath?: string;
  maskReviewVideoSrc?: string;
  boundaryLabel: string;
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

interface InputAssetLike {
  channel?: string;
  path?: string;
}

type PreviewUrlBuilder = (path: string) => string;

export function videoPlaybackAnalysisFromRun(
  run: RunLike | null | undefined,
  inputs: InputAssetLike[],
  videoUrl: PreviewUrlBuilder,
  previewUrl: PreviewUrlBuilder,
  preferredVideoPath = "",
): VideoPlaybackAnalysis | null {
  const fusedOutputs = run?.fused_outputs ?? {};
  const videoInput = [...inputs].reverse().find((asset) => asset.channel === "video" && stringFrom(asset.path));
  const sourcePath =
    stringFrom(fusedOutputs.source_path) || preferredVideoPath.trim() || stringFrom(videoInput?.path);
  if (!sourcePath) return null;

  const summary = recordFrom(fusedOutputs.video_segmentation_summary)
    ? fusedOutputs.video_segmentation_summary
    : {};
  const overlayReviewVideoPath = stringFrom(fusedOutputs.segmentation_review_video_path);
  const maskReviewVideoPath = stringFrom(fusedOutputs.mask_review_video_path);
  const mode = stringFrom(fusedOutputs.mode);
  const analysisScope = stringFrom(summary.analysis_scope);
  const hasFrameDetails = hotspotFrameDetailsFromRun(run, previewUrl);
  const boundaryLabel =
    stringFrom(summary.medical_boundary) ||
    "基于关键帧的播放同步分析；同步叠加结果需医生复核，不能作为临床诊断结论。";

  return {
    sourcePath,
    sourceLabel: shortPath(sourcePath),
    videoSrc: videoUrl(sourcePath),
    modeLabel: mode === "video_file_keyframes" ? "MP4 关键帧分析" : "MP4 输入播放",
    analysisScopeLabel:
      analysisScope === "selected_mp4_keyframes_video_signal_segmentation"
        ? "视频信号分割"
        : analysisScope === "selected_mp4_keyframes"
          ? "已选 MP4 关键帧"
        : hasFrameDetails.length
          ? "关键帧同步分析"
          : "待分析",
    frameDetails: hasFrameDetails,
    overlayReviewVideoPath: overlayReviewVideoPath || undefined,
    overlayReviewVideoSrc: overlayReviewVideoPath ? videoUrl(overlayReviewVideoPath) : undefined,
    maskReviewVideoPath: maskReviewVideoPath || undefined,
    maskReviewVideoSrc: maskReviewVideoPath ? videoUrl(maskReviewVideoPath) : undefined,
    boundaryLabel,
  };
}

export function videoPreviewPanelsFromRun(
  run: RunLike | null | undefined,
  previewUrl: PreviewUrlBuilder,
  selectedHotspotKey = "",
): AnalysisPreviewPanel[] {
  const hotspots = hotspotOutputsFromRun(run);
  if (hotspots.length) {
    const displayableHotspots = hotspots.filter(
      (hotspot) => hotspot.display_allowed !== false && stringFrom(hotspot.display_allowed).toLowerCase() !== "false",
    );
    const selectableHotspots = displayableHotspots.length ? displayableHotspots : hotspots;
    const selectedHotspot =
      selectableHotspots.find((hotspot, index) => hotspotKey(hotspot, index) === selectedHotspotKey) ??
      selectableHotspots[0];
    const displayAllowed =
      selectedHotspot.display_allowed !== false && stringFrom(selectedHotspot.display_allowed).toLowerCase() !== "false";
    const lesionEvidence = recordFrom(selectedHotspot.lesion_evidence) ? selectedHotspot.lesion_evidence : {};
    const sourcePath = stringFrom(selectedHotspot.source_path);
    const overlayPath = displayAllowed ? stringFrom(lesionEvidence.overlay_path) : "";
    const segmentationMask = recordFrom(selectedHotspot.segmentation_mask) ? selectedHotspot.segmentation_mask : {};
    const signalMasks = recordFrom(selectedHotspot.video_signal_segmentation)
      ? selectedHotspot.video_signal_segmentation
      : recordFrom(selectedHotspot.signal_masks)
        ? selectedHotspot.signal_masks
        : recordFrom(lesionEvidence.video_signal_segmentation)
          ? lesionEvidence.video_signal_segmentation
          : recordFrom(lesionEvidence.signal_masks)
            ? lesionEvidence.signal_masks
            : {};
    const maskPath = displayAllowed
      ? stringFrom(segmentationMask.path) || stringFrom(lesionEvidence.mask_path)
      : "";
    const riskPath = displayAllowed
      ? stringFrom(lesionEvidence.risk_mask_path) || signalMaskPath(signalMasks, "risk_mask")
      : "";
    const uncertainPath =
      displayAllowed
        ? stringFrom(lesionEvidence.uncertain_mask_path) || signalMaskPath(signalMasks, "uncertain_mask")
        : "";
    const pseudoColorPath = displayAllowed ? stringFrom(lesionEvidence.pseudo_color_path) : "";
    const frameIndex = stringFrom(selectedHotspot.frame_index) || "-";
    const timestamp = formatSeconds(selectedHotspot.timestamp_sec);
    const panels = [
      panelFromPath("关键帧", `帧序号: ${frameIndex}`, `时间: ${timestamp}`, "MP4", sourcePath, previewUrl),
      panelFromPath("分割叠加", `帧序号: ${frameIndex}`, "荧光伪彩 + 分割候选", "掩膜 + 原帧", overlayPath, previewUrl),
      panelFromPath("分割掩膜", `帧序号: ${frameIndex}`, "二值 ROI 掩膜", "阈值掩膜", maskPath || pseudoColorPath, previewUrl),
      panelFromPath("风险图", `帧序号: ${frameIndex}`, "荧光灌注/活性风险提示", "风险提示", riskPath, previewUrl),
      panelFromPath("不确定性", `帧序号: ${frameIndex}`, "低置信或质量受限区域", "不确定性", uncertainPath, previewUrl),
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
    const signalMasks = recordFrom(detail.video_signal_segmentation)
      ? detail.video_signal_segmentation
      : recordFrom(detail.signal_masks)
        ? detail.signal_masks
        : {};
    const riskMaskPath = stringFrom(detail.risk_mask_path) || signalMaskPath(signalMasks, "risk_mask");
    const uncertainMaskPath =
      stringFrom(detail.uncertain_mask_path) || signalMaskPath(signalMasks, "uncertain_mask");
    const boneGateMaskPath = stringFrom(detail.bone_gate_mask_path) || signalMaskPath(signalMasks, "bone_gate_mask");
    const boneGateOverlayPath =
      stringFrom(detail.bone_gate_overlay_path) || signalMaskOverlayPath(signalMasks, "bone_gate_mask");
    const boneGateStatus = signalMaskStatus(signalMasks, "bone_gate_mask");
    const displayAllowed = detail.display_allowed !== false && stringFrom(detail.display_allowed).toLowerCase() !== "false";
    const frameAgeMs = finiteNumberOrNull(detail.analysis_frame_age_ms);
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
        "启发式关键帧热点分析，必须医生复核，不作为诊断结论。",
      reviewRequired: booleanFrom(detail.review_required) || componentCount > 0 || positiveArea > 0,
      displayAllowed,
      stale: !displayAllowed || booleanFrom(detail.stale),
      frameAgeLabel: frameAgeMs === null ? "帧龄未记录" : `帧龄 ${Math.round(frameAgeMs)} ms`,
      evidenceHref: evidencePath ? previewUrl(evidencePath) : undefined,
      overlayHref: displayAllowed && overlayPath ? previewUrl(overlayPath) : undefined,
      maskHref: displayAllowed && maskPath ? previewUrl(maskPath) : undefined,
      boneGateMaskHref: displayAllowed && boneGateMaskPath ? previewUrl(boneGateMaskPath) : undefined,
      boneGateOverlayHref: displayAllowed && boneGateOverlayPath ? previewUrl(boneGateOverlayPath) : undefined,
      boneGateStatusLabel:
        boneGateStatus === "prompt_assisted_review"
          ? "已生成骨面门控"
          : [
                "physician_modified_mask",
                "project_reviewer_modified_mask",
                "engineering_reviewer_modified_mask",
              ].includes(boneGateStatus)
            ? "已修改骨面掩膜"
          : boneGateStatus === "not_available_pending_review"
            ? "待生成骨面门控"
            : boneGateStatus || "待生成骨面门控",
      riskMaskHref: displayAllowed && riskMaskPath ? previewUrl(riskMaskPath) : undefined,
      uncertainMaskHref: displayAllowed && uncertainMaskPath ? previewUrl(uncertainMaskPath) : undefined,
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
    samplingLabel: samplingStrategyLabel(stringFrom(summary.sampling_strategy)),
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
    risk_mask_path: segmentationMask.risk_mask_path || lesionEvidence.risk_mask_path,
    uncertain_mask_path: segmentationMask.uncertain_mask_path || lesionEvidence.uncertain_mask_path,
    signal_masks: hotspot.signal_masks || lesionEvidence.signal_masks,
    video_signal_segmentation: hotspot.video_signal_segmentation || lesionEvidence.video_signal_segmentation,
    pseudo_color_path: lesionEvidence.pseudo_color_path,
    positive_area_fraction: quantification.positive_area_fraction,
    roi_positive_area_fraction: quantification.roi_positive_area_fraction,
    component_count: quantification.component_count,
    top_component_bbox_xyxy: topComponent.bbox_xyxy,
    domain_boundary: hotspot.domain_boundary,
    review_required: true,
  };
}

function signalMaskPath(signalMasks: unknown, key: "bone_gate_mask" | "risk_mask" | "uncertain_mask"): string {
  if (!recordFrom(signalMasks)) return "";
  const entry = recordFrom(signalMasks[key]) ? signalMasks[key] : {};
  return stringFrom(entry.path);
}

function signalMaskOverlayPath(signalMasks: unknown, key: "bone_gate_mask"): string {
  if (!recordFrom(signalMasks)) return "";
  const entry = recordFrom(signalMasks[key]) ? signalMasks[key] : {};
  return stringFrom(entry.overlay_path);
}

function signalMaskStatus(signalMasks: unknown, key: "bone_gate_mask"): string {
  if (!recordFrom(signalMasks)) return "";
  const entry = recordFrom(signalMasks[key]) ? signalMasks[key] : {};
  return stringFrom(entry.status);
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

function samplingStrategyLabel(value: string): string {
  const labels: Record<string, string> = {
    keyframe_stride: "关键帧步长采样",
    uniform_stride: "等间隔采样",
    positive_area_ranked: "按阳性面积排序",
    candidate_ranked: "按候选分数排序",
    quality_peak: "质量峰值采样",
  };
  return labels[value] ?? (value ? value.replaceAll("_", " ") : "暂无");
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
