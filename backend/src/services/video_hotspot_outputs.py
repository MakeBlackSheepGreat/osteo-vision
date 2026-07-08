from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.src.core.artifacts import checksum_for_file
from backend.src.domains.cases.enums import ArtifactKind, ReviewState
from backend.src.domains.cases.schemas import CandidateRegion, EvidenceArtifact
from backend.src.services.video_keyframe_metrics import normalized_bbox, positive_float


def summarize_hotspot_outputs(hotspot_outputs: list[dict[str, Any]]) -> dict[str, Any]:
    fractions = [
        float(output.get("quantification", {}).get("positive_area_fraction", 0.0)) for output in hotspot_outputs
    ]
    component_counts = [int(output.get("quantification", {}).get("component_count", 0)) for output in hotspot_outputs]
    roi_fractions = [
        float(output.get("quantification", {}).get("roi_positive_area_fraction", 0.0)) for output in hotspot_outputs
    ]
    return {
        "hotspot_frame_count": len(hotspot_outputs),
        "hotspot_candidate_count": sum(component_counts),
        "hotspot_max_positive_area_fraction": max(fractions) if fractions else 0.0,
        "hotspot_mean_positive_area_fraction": sum(fractions) / len(fractions) if fractions else 0.0,
        "hotspot_roi_max_positive_area_fraction": max(roi_fractions) if roi_fractions else 0.0,
        "hotspot_roi_mean_positive_area_fraction": sum(roi_fractions) / len(roi_fractions) if roi_fractions else 0.0,
    }


def build_hotspot_candidate_regions(
    run_id: str, hotspot_outputs: list[dict[str, Any]], *, frame_details: list[dict[str, Any]]
) -> list[CandidateRegion]:
    details_by_order = {
        str(detail.get("frame_order")): detail for detail in frame_details if detail.get("frame_order") is not None
    }
    details_by_index = {
        str(detail.get("frame_index")): detail for detail in frame_details if detail.get("frame_index") is not None
    }
    ranked = sorted(
        hotspot_outputs,
        key=lambda item: float(item.get("quantification", {}).get("positive_area_fraction", 0.0)),
        reverse=True,
    )
    candidates: list[CandidateRegion] = []
    for output in ranked[:3]:
        quantification = output.get("quantification", {})
        fraction = float(quantification.get("positive_area_fraction", 0.0))
        if fraction <= 0:
            continue
        analysis_method = str(output.get("analysis_method") or "heuristic_hotspot_fallback")
        model_id = str(output.get("model_id") or "video_keyframe_hotspot_segmenter")
        metadata = _hotspot_candidate_metadata(output, quantification)
        detail = (
            details_by_order.get(str(output.get("frame_order")))
            or details_by_index.get(str(output.get("frame_index")))
            or {}
        )
        if detail:
            spatial_mapping = detail.get("spatial_mapping") if isinstance(detail.get("spatial_mapping"), dict) else {}
            temporal_stability = (
                detail.get("temporal_stability") if isinstance(detail.get("temporal_stability"), dict) else {}
            )
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


def hotspot_artifacts(case_id: str, run_id: str, hotspot_outputs: list[dict[str, Any]]) -> list[EvidenceArtifact]:
    artifacts: list[EvidenceArtifact] = []
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
            parent = output.get(parent_key)
            path = parent.get(path_key) if isinstance(parent, dict) else None
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


def video_manifest_artifacts(case_id: str, run_id: str, paths: list[Any]) -> list[EvidenceArtifact]:
    artifacts: list[EvidenceArtifact] = []
    seen: set[str] = set()
    for path in paths:
        if not path:
            continue
        normalized = str(path)
        if normalized in seen or not Path(normalized).exists():
            continue
        seen.add(normalized)
        artifacts.append(
            EvidenceArtifact(
                artifact_id=f"artifact_{uuid4().hex[:10]}",
                case_id=case_id,
                run_id=run_id,
                kind=ArtifactKind.REPORT_JSON,
                path=normalized,
                checksum=checksum_for_file(normalized),
            )
        )
    return artifacts


def video_segmentation_artifacts(case_id: str, run_id: str, outputs: dict[str, Any]) -> list[EvidenceArtifact]:
    mapping = [
        ("video_segmentation_manifest_path", ArtifactKind.VIDEO_SEGMENTATION_MANIFEST),
        ("segmentation_review_video_path", ArtifactKind.VIDEO_OVERLAY),
        ("mask_review_video_path", ArtifactKind.VIDEO_MASK),
    ]
    artifacts: list[EvidenceArtifact] = []
    for path_key, kind in mapping:
        path = outputs.get(path_key)
        if not path or not Path(str(path)).exists():
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


def _candidate_confidence(quantification: Any) -> float:
    quant = quantification if isinstance(quantification, dict) else {}
    for key in ("max_probability", "mean_probability", "p95_intensity", "max_intensity"):
        value = quant.get(key)
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _hotspot_candidate_metadata(output: dict[str, Any], quantification: Any) -> dict[str, Any]:
    quant = quantification if isinstance(quantification, dict) else {}
    lesion_evidence = output.get("lesion_evidence") if isinstance(output.get("lesion_evidence"), dict) else {}
    signal_masks = output.get("signal_masks") or output.get("video_signal_segmentation")
    signal_masks = signal_masks if isinstance(signal_masks, dict) else {}
    hotspot_candidates = lesion_evidence.get("candidates") if isinstance(lesion_evidence, dict) else []
    top_candidate = hotspot_candidates[0] if isinstance(hotspot_candidates, list) and hotspot_candidates else {}
    top_candidate = top_candidate if isinstance(top_candidate, dict) else {}
    segmentation_mask = output.get("segmentation_mask") if isinstance(output.get("segmentation_mask"), dict) else {}
    width = positive_float(segmentation_mask.get("width")) if isinstance(segmentation_mask, dict) else 0.0
    height = positive_float(segmentation_mask.get("height")) if isinstance(segmentation_mask, dict) else 0.0
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
        "overlay_path": lesion_evidence.get("overlay_path") if isinstance(lesion_evidence, dict) else None,
        "risk_mask_path": lesion_evidence.get("risk_mask_path") if isinstance(lesion_evidence, dict) else None,
        "uncertain_mask_path": lesion_evidence.get("uncertain_mask_path") if isinstance(lesion_evidence, dict) else None,
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
