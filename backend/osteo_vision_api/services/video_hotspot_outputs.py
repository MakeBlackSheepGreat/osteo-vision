from __future__ import annotations

from heapq import nlargest
from math import isfinite
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.osteo_vision_api.core.artifacts import checksum_for_file
from backend.osteo_vision_api.domains.cases.enums import ArtifactKind, ReviewState
from backend.osteo_vision_api.domains.cases.schemas import CandidateRegion, EvidenceArtifact
from backend.osteo_vision_api.services.video_keyframe_metrics import normalized_bbox, positive_float


def summarize_hotspot_outputs(hotspot_outputs: list[Any]) -> dict[str, Any]:
    fraction_sum = 0.0
    roi_fraction_sum = 0.0
    max_fraction = 0.0
    max_roi_fraction = 0.0
    candidate_count = 0
    frame_count = 0
    for output in hotspot_outputs:
        quantification = _mapping(_mapping(output).get("quantification"))
        fraction = _nonnegative_float(quantification.get("positive_area_fraction"))
        roi_fraction = _nonnegative_float(quantification.get("roi_positive_area_fraction"))
        frame_count += 1
        fraction_sum += fraction
        roi_fraction_sum += roi_fraction
        max_fraction = max(max_fraction, fraction)
        max_roi_fraction = max(max_roi_fraction, roi_fraction)
        candidate_count += _nonnegative_int(quantification.get("component_count"))
    return {
        "hotspot_frame_count": frame_count,
        "hotspot_candidate_count": candidate_count,
        "hotspot_max_positive_area_fraction": max_fraction,
        "hotspot_mean_positive_area_fraction": fraction_sum / frame_count if frame_count else 0.0,
        "hotspot_roi_max_positive_area_fraction": max_roi_fraction,
        "hotspot_roi_mean_positive_area_fraction": roi_fraction_sum / frame_count if frame_count else 0.0,
    }


def build_hotspot_candidate_regions(
    run_id: str, hotspot_outputs: list[Any], *, frame_details: list[Any]
) -> list[CandidateRegion]:
    details_by_order: dict[str, dict[str, Any]] = {}
    details_by_index: dict[str, dict[str, Any]] = {}
    for detail in frame_details:
        valid_detail = _mapping(detail)
        if not valid_detail:
            continue
        if valid_detail.get("frame_order") is not None:
            details_by_order[str(valid_detail["frame_order"])] = valid_detail
        if valid_detail.get("frame_index") is not None:
            details_by_index[str(valid_detail["frame_index"])] = valid_detail
    ranked = nlargest(
        3,
        (
            (fraction, _mapping(output))
            for output in hotspot_outputs
            if (fraction := _positive_area_fraction(output)) > 0.0
        ),
        key=lambda item: item[0],
    )
    candidates: list[CandidateRegion] = []
    for fraction, output in ranked:
        quantification = _mapping(output.get("quantification"))
        analysis_method = str(output.get("analysis_method") or "heuristic_hotspot_fallback")
        model_id = str(output.get("model_id") or "video_keyframe_hotspot_segmenter")
        metadata = _hotspot_candidate_metadata(output, quantification)
        detail = (
            details_by_order.get(str(output.get("frame_order")))
            or details_by_index.get(str(output.get("frame_index")))
            or {}
        )
        if detail:
            spatial_mapping = _dict_value(detail.get("spatial_mapping"))
            temporal_stability = _dict_value(detail.get("temporal_stability"))
            metadata.update(
                {
                    "frame_key": detail.get("frame_key"),
                    "source_bbox_xyxy": spatial_mapping.get("top_component_bbox_source_xyxy"),
                    "source_bbox_normalized": spatial_mapping.get("top_component_bbox_source_normalized"),
                    "source_video_width": spatial_mapping.get("source_video_width"),
                    "source_video_height": spatial_mapping.get("source_video_height"),
                    "spatial_mapping": spatial_mapping,
                    "temporal_stability": temporal_stability,
                    "review_priority": detail.get("review_priority"),
                    "target_domain_flag": detail.get("target_domain_flag"),
                    "input_domain": detail.get("input_domain"),
                    "data_boundary": detail.get("data_boundary"),
                    "failure_reason": detail.get("failure_reason"),
                }
            )
        candidates.append(
            CandidateRegion(
                candidate_id=f"cand_video_hotspot_{uuid4().hex[:10]}",
                run_id=run_id,
                score=fraction,
                risk_type=(
                    "video_keyframe_model_segmentation"
                    if analysis_method == "trainable_keyframe_segmenter"
                    else "video_keyframe_hotspot"
                ),
                confidence=_candidate_confidence(quantification),
                status=ReviewState.REVIEW_REQUIRED,
                explanation=(
                    (
                        f"Trainable proxy segmentation model {model_id} on MP4 keyframe "
                        if analysis_method == "trainable_keyframe_segmenter"
                        else "Heuristic fluorescence-like hotspot on MP4 keyframe "
                    )
                    + f"{output.get('frame_index')} at {output.get('timestamp_sec')} seconds; "
                    "physician review required."
                ),
                metadata=metadata,
            )
        )
    return candidates


def hotspot_artifacts(case_id: str, run_id: str, hotspot_outputs: list[Any]) -> list[EvidenceArtifact]:
    artifacts: list[EvidenceArtifact] = []
    seen: set[tuple[ArtifactKind, str]] = set()
    checksums: dict[str, str] = {}
    mapping = [
        ("segmentation_mask", "path", ArtifactKind.ROI_MASK),
        ("lesion_evidence", "probability_path", ArtifactKind.PROBABILITY_MAP),
        ("lesion_evidence", "risk_mask_path", ArtifactKind.HEATMAP),
        ("lesion_evidence", "uncertain_mask_path", ArtifactKind.ROI_MASK),
        ("lesion_evidence", "pseudo_color_path", ArtifactKind.HEATMAP),
        ("lesion_evidence", "overlay_path", ArtifactKind.OVERLAY),
    ]
    for output in hotspot_outputs:
        for parent_key, path_key, kind in mapping:
            parent = _mapping(output).get(parent_key)
            path = parent.get(path_key) if isinstance(parent, dict) else None
            _append_artifact(
                artifacts,
                seen,
                checksums,
                case_id=case_id,
                run_id=run_id,
                kind=kind,
                path=path,
            )
    return artifacts


def video_manifest_artifacts(case_id: str, run_id: str, paths: list[Any]) -> list[EvidenceArtifact]:
    artifacts: list[EvidenceArtifact] = []
    seen: set[tuple[ArtifactKind, str]] = set()
    checksums: dict[str, str] = {}
    for path in paths:
        _append_artifact(
            artifacts,
            seen,
            checksums,
            case_id=case_id,
            run_id=run_id,
            kind=ArtifactKind.REPORT_JSON,
            path=path,
        )
    return artifacts


def video_segmentation_artifacts(case_id: str, run_id: str, outputs: dict[str, Any]) -> list[EvidenceArtifact]:
    mapping = [
        ("video_segmentation_manifest_path", ArtifactKind.VIDEO_SEGMENTATION_MANIFEST),
        ("segmentation_review_video_path", ArtifactKind.VIDEO_OVERLAY),
        ("mask_review_video_path", ArtifactKind.VIDEO_MASK),
    ]
    artifacts: list[EvidenceArtifact] = []
    seen: set[tuple[ArtifactKind, str]] = set()
    checksums: dict[str, str] = {}
    for path_key, kind in mapping:
        _append_artifact(
            artifacts,
            seen,
            checksums,
            case_id=case_id,
            run_id=run_id,
            kind=kind,
            path=_mapping(outputs).get(path_key),
        )
    return artifacts


def _candidate_confidence(quantification: Any) -> float:
    quant = _mapping(quantification)
    for key in ("max_probability", "mean_probability", "p95_intensity", "max_intensity"):
        value = _finite_nonnegative_float_or_none(quant.get(key))
        if value is not None:
            return value
    return 0.0


def _dict_value(value: Any) -> dict[str, Any]:
    return _mapping(value)


def _hotspot_candidate_metadata(output: dict[str, Any], quantification: Any) -> dict[str, Any]:
    quant = _mapping(quantification)
    lesion_evidence = _mapping(output.get("lesion_evidence"))
    signal_masks = output.get("signal_masks") or output.get("video_signal_segmentation")
    signal_masks = signal_masks if isinstance(signal_masks, dict) else {}
    hotspot_candidates = lesion_evidence.get("candidates") if isinstance(lesion_evidence, dict) else []
    top_candidate = hotspot_candidates[0] if isinstance(hotspot_candidates, list) and hotspot_candidates else {}
    top_candidate = top_candidate if isinstance(top_candidate, dict) else {}
    segmentation_mask = _mapping(output.get("segmentation_mask"))
    width = positive_float(segmentation_mask.get("width"))
    height = positive_float(segmentation_mask.get("height"))
    bbox = top_candidate.get("bbox_xyxy")
    normalized = normalized_bbox(bbox, width=width, height=height)
    return {
        "model_id": output.get("model_id"),
        "model_family": output.get("model_family"),
        "analysis_method": output.get("analysis_method"),
        "frame_order": output.get("frame_order"),
        "frame_index": output.get("frame_index"),
        "timestamp_sec": output.get("timestamp_sec"),
        "source_path": output.get("source_path"),
        "overlay_path": lesion_evidence.get("overlay_path"),
        "risk_mask_path": lesion_evidence.get("risk_mask_path"),
        "uncertain_mask_path": lesion_evidence.get("uncertain_mask_path"),
        "mask_path": segmentation_mask.get("path") if isinstance(segmentation_mask, dict) else None,
        "mask_type": "boundary_risk",
        "signal_masks": signal_masks,
        "video_signal_segmentation": signal_masks,
        "bone_gate_status": _bone_gate_status(signal_masks),
        "sample_weight": _sample_weight_for_review_state(str(output.get("review_state") or "review_required")),
        "positive_area_fraction": quant.get("positive_area_fraction"),
        "component_count": quant.get("component_count"),
        "uncertainty": quant.get("uncertainty"),
        "review_priority": output.get("review_priority") or quant.get("review_priority"),
        "target_domain_flag": output.get("target_domain_flag") or quant.get("target_domain_flag"),
        "failure_reason": output.get("failure_reason"),
        "top_component": top_candidate,
        "bbox_xyxy": bbox if isinstance(bbox, list) and len(bbox) == 4 else None,
        "bbox_normalized": normalized,
        "image_width": int(width) if width else None,
        "image_height": int(height) if height else None,
    }


def _bone_gate_status(signal_masks: dict[str, Any]) -> str:
    bone_gate = signal_masks.get("bone_gate_mask") if isinstance(signal_masks, dict) else {}
    if isinstance(bone_gate, dict):
        return str(bone_gate.get("status") or "not_available_pending_review")
    return "not_available_pending_review"


def _sample_weight_for_review_state(state: str) -> float:
    normalized = state.lower()
    if normalized in {"accepted", "modified"}:
        return 4.0
    if normalized == "rejected":
        return 0.5
    return 1.0


def _positive_area_fraction(output: Any) -> float:
    return _nonnegative_float(_mapping(_mapping(output).get("quantification")).get("positive_area_fraction"))


def _nonnegative_float(value: Any) -> float:
    parsed = _finite_nonnegative_float_or_none(value)
    return parsed if parsed is not None else 0.0


def _finite_nonnegative_float_or_none(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if isfinite(parsed) and parsed >= 0.0 else None


def _nonnegative_int(value: Any) -> int:
    parsed = _nonnegative_float(value)
    return int(parsed)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _append_artifact(
    artifacts: list[EvidenceArtifact],
    seen: set[tuple[ArtifactKind, str]],
    checksums: dict[str, str],
    *,
    case_id: str,
    run_id: str,
    kind: ArtifactKind,
    path: Any,
) -> None:
    if not path:
        return
    normalized = str(path)
    candidate = Path(normalized)
    key = (kind, normalized)
    if key in seen or not candidate.is_file():
        return
    seen.add(key)
    checksum = checksums.get(normalized)
    if checksum is None:
        checksum = checksum_for_file(candidate)
        checksums[normalized] = checksum
    artifacts.append(
        EvidenceArtifact(
            artifact_id=f"artifact_{uuid4().hex[:10]}",
            case_id=case_id,
            run_id=run_id,
            kind=kind,
            path=normalized,
            checksum=checksum,
        )
    )
