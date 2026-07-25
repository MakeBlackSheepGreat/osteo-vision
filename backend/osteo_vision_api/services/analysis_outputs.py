from __future__ import annotations

from math import isfinite
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.osteo_vision_api.core.artifacts import checksum_for_file
from backend.osteo_vision_api.core.disclaimers import disclaimer_context
from backend.osteo_vision_api.domains.cases.enums import ArtifactKind, ReviewState
from backend.osteo_vision_api.domains.cases.schemas import (
    CandidateRegion,
    CaseInputAsset,
    CaseRecord,
    EvidenceArtifact,
)
from backend.osteo_vision_api.services.video_hotspot_outputs import (
    hotspot_artifacts,
    video_manifest_artifacts,
    video_segmentation_artifacts,
)


def _dict_payload(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_payload(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _finite_float(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return parsed if isfinite(parsed) else 0.0


def _positive_int(value: Any, *, default: int) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError, OverflowError):
        return default


def _verified_artifacts(
    case_id: str,
    run_id: str,
    paths: tuple[tuple[Any, ArtifactKind], ...],
) -> list[EvidenceArtifact]:
    """Build deduplicated artifact records and tolerate stale output paths."""

    artifacts: list[EvidenceArtifact] = []
    seen: set[Path] = set()
    for value, kind in paths:
        if not value:
            continue
        try:
            path = Path(str(value)).expanduser().resolve()
            if path in seen or not path.is_file():
                continue
            checksum = checksum_for_file(path)
        except (OSError, ValueError):
            continue
        seen.add(path)
        artifacts.append(
            EvidenceArtifact(
                artifact_id=f"artifact_{uuid4().hex[:10]}",
                case_id=case_id,
                run_id=run_id,
                kind=kind,
                path=str(path),
                checksum=checksum,
            )
        )
    return artifacts


def video_fused_outputs(
    *,
    source_path: str,
    video: CaseInputAsset | None,
    keyframes: list[dict[str, Any]],
    hotspot_outputs: list[dict[str, Any]],
    segmentation_model_id: str,
    frame_details: list[dict[str, Any]],
    keyframe_report: dict[str, Any],
    timeline_summary: dict[str, Any],
    temporal_summary: dict[str, Any],
    frame_details_manifest_path: str | None,
    video_segmentation_outputs: dict[str, Any],
    roi_hints: list[dict[str, Any]],
    three_d_evidence: dict[str, Any],
    analysis_mode: str = "video_file_keyframes",
) -> dict[str, Any]:
    # MP4 分析结果字段较多，集中装配可以让 AnalysisService 只保留流程编排。
    return {
        "mode": analysis_mode,
        "source_path": source_path,
        "video_metadata": video.metadata if video else {},
        "keyframes": keyframes,
        "hotspot_outputs": hotspot_outputs,
        "keyframe_segmentation_outputs": hotspot_outputs,
        "keyframe_segmentation_model_id": segmentation_model_id,
        "frame_details": frame_details,
        "quality_summary": keyframe_report.get("quality_summary", {}),
        "keyframe_report_source": keyframe_report.get("report_source", "new_analysis_extract"),
        "keyframe_manifest_path": keyframe_report.get("keyframe_manifest_path"),
        "frame_index_manifest_path": keyframe_report.get("frame_index_manifest_path"),
        "timeline_manifest_path": keyframe_report.get("timeline_manifest_path"),
        "timeline_summary": timeline_summary,
        "temporal_stability_summary": temporal_summary,
        "frame_details_manifest_path": frame_details_manifest_path,
        "video_segmentation_manifest_path": video_segmentation_outputs.get("video_segmentation_manifest_path"),
        "segmentation_review_video_path": video_segmentation_outputs.get("segmentation_review_video_path"),
        "mask_review_video_path": video_segmentation_outputs.get("mask_review_video_path"),
        "video_segmentation_summary": video_segmentation_outputs.get("summary", {}),
        "three_d_evidence": three_d_evidence,
        "roi_hints": roi_hints,
        "disclaimer_context": disclaimer_context(),
    }


def video_quantitative_summary(
    *,
    keyframe_report: dict[str, Any],
    keyframes: list[dict[str, Any]],
    roi_hints: list[dict[str, Any]],
    video_segmentation_outputs: dict[str, Any],
    temporal_summary: dict[str, Any],
    hotspot_summary: dict[str, Any],
    inference_performance: dict[str, Any] | None = None,
    fluorescence_dynamics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    segmentation_summary = video_segmentation_outputs.get("summary", {})
    segmentation_summary = segmentation_summary if isinstance(segmentation_summary, dict) else {}
    return {
        "frame_count": keyframe_report.get("frame_count"),
        "duration_sec": keyframe_report.get("duration_sec"),
        "keyframes_extracted": len(keyframes),
        "keyframe_source": keyframe_report.get("report_source", "new_analysis_extract"),
        "roi_hint_count": len(roi_hints),
        "roi_filter_applied": bool(roi_hints),
        "segmentation_frame_count": segmentation_summary.get("selected_frame_count", 0),
        "segmentation_overlay_video_available": bool(video_segmentation_outputs.get("segmentation_review_video_path")),
        "hotspot_temporal_instability_frame_count": temporal_summary.get("instability_frame_count", 0),
        "keyframe_inference_performance": inference_performance or {"available": False},
        "fluorescence_time_intensity_curve": fluorescence_dynamics or {"available": False},
        **hotspot_summary,
    }


def video_artifacts(
    case_id: str,
    run_id: str,
    *,
    keyframes: list[dict[str, Any]],
    hotspot_outputs: list[dict[str, Any]],
    keyframe_report: dict[str, Any],
    frame_details_manifest_path: str | None,
    video_segmentation_outputs: dict[str, Any],
) -> list[EvidenceArtifact]:
    return [
        *_keyframe_artifacts(case_id, run_id, keyframes),
        *hotspot_artifacts(case_id, run_id, hotspot_outputs),
        *video_manifest_artifacts(
            case_id,
            run_id,
            [
                keyframe_report.get("frame_index_manifest_path"),
                keyframe_report.get("timeline_manifest_path"),
                frame_details_manifest_path,
                video_segmentation_outputs.get("video_segmentation_manifest_path"),
            ],
        ),
        *video_segmentation_artifacts(case_id, run_id, video_segmentation_outputs),
    ]


def fusion_fused_outputs(
    fusion_report: dict[str, Any],
    *,
    outputs: dict[str, Any],
    roi_hints: list[dict[str, Any]],
    three_d_evidence: dict[str, Any],
) -> dict[str, Any]:
    # 双通道融合报告来自底层处理函数，这里只补平台层需要追踪的 ROI 和安全边界上下文。
    return {
        **fusion_report,
        "outputs": outputs,
        "roi_hints": roi_hints,
        "three_d_evidence": three_d_evidence,
        "disclaimer_context": disclaimer_context(),
    }


def fusion_quantitative_summary(
    fusion_report: dict[str, Any],
    *,
    roi_hints: list[dict[str, Any]],
) -> dict[str, Any]:
    quantification = fusion_report.get("quantification", {})
    quantification = quantification if isinstance(quantification, dict) else {}
    return {**quantification, "roi_hint_count": len(roi_hints)}


def fusion_candidate_regions(
    run_id: str,
    fusion_report: dict[str, Any],
    *,
    roi_hints: list[dict[str, Any]],
) -> list[CandidateRegion]:
    quantification = fusion_report.get("quantification", {})
    quantification = quantification if isinstance(quantification, dict) else {}
    score = quantification.get("roi_mean_intensity", quantification.get("mean_intensity", 0.0))
    confidence = quantification.get("roi_p95_intensity", quantification.get("p95_intensity", 0.0))
    return [
        CandidateRegion(
            candidate_id=f"cand_{uuid4().hex[:10]}",
            run_id=run_id,
            score=float(score or 0.0),
            risk_type="fluorescence_hotspot",
            confidence=float(confidence or 0.0),
            status=ReviewState.REVIEW_REQUIRED,
            explanation=(
                "Derived from ROI-constrained fluorescence quantification heuristics."
                if roi_hints
                else "Derived from fluorescence quantification heuristics."
            ),
        )
    ]


def fusion_ai_candidate_regions(
    run_id: str,
    evidence: dict[str, Any],
    *,
    max_per_boundary_type: int = 12,
) -> list[CandidateRegion]:
    boundary = _dict_payload(evidence.get("boundary_assessment"))
    candidates = _list_payload(boundary.get("candidates"))
    lesion = _dict_payload(evidence.get("lesion_evidence"))
    input_contract = _dict_payload(evidence.get("input_contract"))
    model_input = _dict_payload(input_contract.get("model_input"))
    source_path = str(lesion.get("overlay_path") or model_input.get("path") or "")
    source_dimensions = _list_payload(model_input.get("dimensions"))
    image_width = source_dimensions[0] if len(source_dimensions) >= 2 else None
    image_height = source_dimensions[1] if len(source_dimensions) >= 2 else None
    selected: list[CandidateRegion] = []
    type_counts: dict[str, int] = {}
    limit = _positive_int(max_per_boundary_type, default=12)
    for item in candidates:
        if not isinstance(item, dict):
            continue
        boundary_type = str(item.get("boundary_type") or "signal_candidate_boundary")
        if type_counts.get(boundary_type, 0) >= limit:
            continue
        type_counts[boundary_type] = type_counts.get(boundary_type, 0) + 1
        bbox = item.get("bbox_xyxy") if isinstance(item.get("bbox_xyxy"), list) else None
        selected.append(
            CandidateRegion(
                candidate_id=f"cand_task3_{uuid4().hex[:10]}",
                run_id=run_id,
                score=_finite_float(item.get("score")),
                risk_type=boundary_type,
                confidence=_finite_float(item.get("review_confidence") or item.get("confidence")),
                status=ReviewState.REVIEW_REQUIRED,
                explanation="Task 3 fused-image boundary candidate routed for physician review.",
                metadata={
                    "task_role": "task3_ai_on_task2_fused_image",
                    "source_candidate_id": item.get("candidate_id"),
                    "source_path": source_path or None,
                    "bbox_xyxy": bbox,
                    "image_width": image_width,
                    "image_height": image_height,
                    "boundary_pixel_count": item.get("boundary_pixel_count"),
                    "boundary_risk_fraction": item.get("boundary_risk_fraction"),
                    "boundary_uncertainty_fraction": item.get("boundary_uncertainty_fraction"),
                    "model_confidence": item.get("confidence"),
                    "review_confidence": item.get("review_confidence"),
                    "activity_class": item.get("activity_class"),
                    "activity_overlap_fraction": item.get("activity_overlap_fraction"),
                    "activity_evidence_available": item.get("activity_evidence_available") is True,
                    "semantic_scope": item.get("semantic_scope"),
                    "spatial_interpretation_allowed": boundary.get("spatial_interpretation_allowed") is True,
                    "clinical_claim_allowed": False,
                },
            )
        )
    return selected


def missing_dual_channel_warning() -> dict[str, Any]:
    return {
        "code": "missing_dual_channel_pair",
        "message": "Dual-channel white-light and fluorescence inputs are required for fusion.",
        "blocking": True,
    }


def fusion_artifacts(case_id: str, run_id: str, outputs: dict[str, Any]) -> list[EvidenceArtifact]:
    mapping = {
        "overlay_path": ArtifactKind.OVERLAY,
        "heatmap_path": ArtifactKind.HEATMAP,
        "normalized_fluorescence_path": ArtifactKind.NORMALIZED_FLUORESCENCE,
        "colorbar_path": ArtifactKind.COLORBAR,
        "report_path": ArtifactKind.REPORT_JSON,
        "markdown_report_path": ArtifactKind.REPORT_MD,
    }
    artifacts: list[EvidenceArtifact] = []
    for output_key, kind in mapping.items():
        path = outputs.get(output_key)
        if not path:
            continue
        artifacts.append(
            EvidenceArtifact(
                artifact_id=f"artifact_{uuid4().hex[:10]}",
                case_id=case_id,
                run_id=run_id,
                kind=kind,
                path=str(path),
                checksum=checksum_for_file(path),
            )
        )
    return artifacts


def fusion_ai_artifacts(case_id: str, run_id: str, evidence: dict[str, Any]) -> list[EvidenceArtifact]:
    lesion = _dict_payload(evidence.get("lesion_evidence"))
    input_contract = _dict_payload(evidence.get("input_contract"))
    boundary = _dict_payload(evidence.get("boundary_assessment"))
    paths = (
        (input_contract.get("contract_path"), ArtifactKind.REPORT_JSON),
        (boundary.get("summary_path"), ArtifactKind.REPORT_JSON),
        (lesion.get("mask_path"), ArtifactKind.ROI_MASK),
        (lesion.get("probability_path"), ArtifactKind.PROBABILITY_MAP),
        (lesion.get("uncertainty_path"), ArtifactKind.HEATMAP),
        (lesion.get("risk_mask_path"), ArtifactKind.ROI_MASK),
        (lesion.get("uncertain_mask_path"), ArtifactKind.ROI_MASK),
        (lesion.get("pseudo_color_path"), ArtifactKind.HEATMAP),
        (lesion.get("overlay_path"), ArtifactKind.OVERLAY),
    )
    return _verified_artifacts(case_id, run_id, paths)


def patient_conditioning_artifacts(
    case_id: str,
    run_id: str,
    evidence: dict[str, Any],
) -> list[EvidenceArtifact]:
    mapping = {
        "image_only_probability_path": ArtifactKind.PROBABILITY_MAP,
        "conditioned_probability_path": ArtifactKind.PROBABILITY_MAP,
        "delta_map_path": ArtifactKind.HEATMAP,
        "difference_mask_path": ArtifactKind.ROI_MASK,
        "spatial_effect_mask_path": ArtifactKind.ROI_MASK,
        "uncertainty_path": ArtifactKind.HEATMAP,
        "image_only_mask_path": ArtifactKind.ROI_MASK,
        "conditioned_mask_path": ArtifactKind.ROI_MASK,
        "evidence_manifest_path": ArtifactKind.REPORT_JSON,
    }
    paths: list[tuple[Any, ArtifactKind]] = []
    for key, kind in mapping.items():
        value = evidence.get(key)
        if value:
            paths.append((value, kind))
    return _verified_artifacts(case_id, run_id, tuple(paths))


def bone_activity_checkpoint_artifacts(
    case_id: str,
    run_id: str,
    evidence: dict[str, Any],
) -> list[EvidenceArtifact]:
    raw = _dict_payload(evidence.get("raw_engineering_outputs"))
    paths = (
        (evidence.get("evidence_manifest_path"), ArtifactKind.BONE_ACTIVITY_CHECKPOINT_EVIDENCE),
        (raw.get("path"), ArtifactKind.BONE_ACTIVITY_RAW_ENGINEERING_OUTPUTS),
    )
    return _verified_artifacts(case_id, run_id, paths)


def three_channel_quality_artifacts(case_id: str, run_id: str, quality: dict[str, Any]) -> list[EvidenceArtifact]:
    overlay_comparison = _dict_payload(quality.get("overlay_comparison"))
    paths = (
        (quality.get("report_path"), ArtifactKind.THREE_CHANNEL_QC_REPORT),
        (
            overlay_comparison.get("difference_heatmap_path"),
            ArtifactKind.THREE_CHANNEL_DIFFERENCE_HEATMAP,
        ),
    )
    return _verified_artifacts(case_id, run_id, paths)


def merge_roi_hints(case: CaseRecord, request_hints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hint in request_hints:
        roi_id = str(hint.get("roi_id") or f"request_roi_{len(merged) + 1}")
        merged.append({**hint, "roi_id": roi_id, "source": hint.get("source", "request")})
        seen.add(roi_id)
    for roi in case.rois:
        if roi.roi_id in seen:
            continue
        merged.append(
            {
                "roi_id": roi.roi_id,
                "source": roi.source.value,
                "geometry": roi.geometry,
                "label": roi.label,
                "review_state": roi.review_state.value,
                "candidate_id": roi.candidate_id,
            }
        )
        seen.add(roi.roi_id)
    return merged


def _keyframe_artifacts(case_id: str, run_id: str, keyframes: list[dict[str, Any]]) -> list[EvidenceArtifact]:
    artifacts: list[EvidenceArtifact] = []
    for frame in keyframes:
        path = frame.get("evidence_path") or frame.get("path")
        if not path:
            continue
        artifacts.append(
            EvidenceArtifact(
                artifact_id=f"artifact_{uuid4().hex[:10]}",
                case_id=case_id,
                run_id=run_id,
                kind=ArtifactKind.KEYFRAME,
                path=str(path),
                checksum=checksum_for_file(path),
            )
        )
    return artifacts
