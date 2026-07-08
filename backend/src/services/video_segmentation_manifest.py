from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.src.core.disclaimers import disclaimer_context
from backend.src.services.video_keyframe_metrics import video_temporal_summary
from backend.src.services.video_review_writer import review_video_fps, write_image_sequence_video


def write_video_frame_details_manifest(
    output_dir: Any,
    *,
    case_id: str,
    run_id: str,
    source_path: str,
    keyframe_report: dict[str, Any],
    frame_details: list[dict[str, Any]],
    three_d_evidence: dict[str, Any] | None = None,
) -> str:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = target_dir / "frame_details_manifest.json"
    payload = {
        "schema_version": "osteo-vision-frame-details-manifest-v1",
        "case_id": case_id,
        "run_id": run_id,
        "source_path": source_path,
        "frame_index_manifest_path": keyframe_report.get("frame_index_manifest_path"),
        "timeline_manifest_path": keyframe_report.get("timeline_manifest_path"),
        "keyframe_manifest_path": keyframe_report.get("keyframe_manifest_path"),
        "sampling_strategy": keyframe_report.get("sampling_strategy") or keyframe_report.get("sampling"),
        "video_frame_count": keyframe_report.get("frame_count"),
        "duration_sec": keyframe_report.get("duration_sec"),
        "selected_frame_count": len(frame_details),
        "temporal_stability_summary": video_temporal_summary(frame_details),
        "three_d_evidence": three_d_evidence or {},
        "frames": frame_details,
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(manifest_path)


def write_video_segmentation_outputs(
    output_dir: Any,
    *,
    case_id: str,
    run_id: str,
    source_path: str,
    keyframe_report: dict[str, Any],
    frame_details: list[dict[str, Any]],
    hotspot_outputs: list[dict[str, Any]],
    three_d_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    frames = _video_segmentation_frames(frame_details, hotspot_outputs)
    overlay_paths = [
        str(frame["fluorescence_overlay_result"]["overlay_path"])
        for frame in frames
        if frame.get("fluorescence_overlay_result", {}).get("overlay_path")
    ]
    mask_paths = [
        str(frame["segmentation_result"]["mask_path"])
        for frame in frames
        if frame.get("segmentation_result", {}).get("mask_path")
    ]
    risk_paths = [
        str(frame["video_signal_segmentation"]["risk_mask"]["path"])
        for frame in frames
        if frame.get("video_signal_segmentation", {}).get("risk_mask", {}).get("path")
    ]
    fps = review_video_fps(keyframe_report.get("fps"))
    overlay_video_path = write_image_sequence_video(
        overlay_paths,
        target_dir / "mp4_keyframe_segmentation_overlay_review.mp4",
        fps=fps,
    )
    mask_video_path = write_image_sequence_video(
        mask_paths,
        target_dir / "mp4_keyframe_segmentation_mask_review.mp4",
        fps=fps,
    )
    model_summary = _video_segmentation_model_summary(hotspot_outputs)
    summary = {
        "schema_version": "osteo-vision-video-segmentation-summary-v1",
        "selected_frame_count": len(frames),
        "mask_frame_count": len(mask_paths),
        "overlay_frame_count": len(overlay_paths),
        "risk_frame_count": len(risk_paths),
        "segmentation_review_video_available": bool(overlay_video_path),
        "mask_review_video_available": bool(mask_video_path),
        "model_id": model_summary["primary_model_id"],
        "model_ids": model_summary["model_ids"],
        "analysis_methods": model_summary["analysis_methods"],
        "analysis_scope": "selected_mp4_keyframes_video_signal_segmentation",
        "temporal_stability": video_temporal_summary(frame_details),
        "video_signal_outputs": ["bone_gate_mask", "fluorescence_signal_mask", "risk_mask", "uncertain_mask"],
        "three_d_evidence_available": bool((three_d_evidence or {}).get("model_path")),
        "three_d_registration_status": (three_d_evidence or {}).get("registration_status") or "not_recorded",
        "three_d_navigation_ready": bool((three_d_evidence or {}).get("navigation_ready")),
        "medical_boundary": (
            "Platform video signal segmentation workflow; fluorescence/perfusion risk prompts require "
            "physician review and are not a clinical diagnosis."
        ),
    }
    manifest_path = target_dir / "video_segmentation_manifest.json"
    payload = {
        "schema_version": "osteo-vision-video-segmentation-manifest-v1",
        "case_id": case_id,
        "run_id": run_id,
        "source_path": source_path,
        "source_video": {
            "width": keyframe_report.get("width"),
            "height": keyframe_report.get("height"),
            "fps": keyframe_report.get("fps"),
            "frame_count": keyframe_report.get("frame_count"),
            "duration_sec": keyframe_report.get("duration_sec"),
        },
        "keyframe_manifest_path": keyframe_report.get("keyframe_manifest_path"),
        "frame_index_manifest_path": keyframe_report.get("frame_index_manifest_path"),
        "timeline_manifest_path": keyframe_report.get("timeline_manifest_path"),
        "segmentation_review_video_path": overlay_video_path,
        "mask_review_video_path": mask_video_path,
        "summary": summary,
        "three_d_evidence": three_d_evidence or {},
        "frames": frames,
        "disclaimer": disclaimer_context(),
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "video_segmentation_manifest_path": str(manifest_path),
        "segmentation_review_video_path": overlay_video_path,
        "mask_review_video_path": mask_video_path,
        "summary": summary,
    }


def _video_segmentation_frames(
    frame_details: list[dict[str, Any]], hotspot_outputs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_order, by_index = _video_output_indexes(hotspot_outputs)
    return [
        _video_segmentation_frame(detail, _matching_video_output(detail, by_order, by_index))
        for detail in frame_details
    ]


def _video_output_indexes(outputs: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    return (
        {str(output.get("frame_order")): output for output in outputs if output.get("frame_order") is not None},
        {str(output.get("frame_index")): output for output in outputs if output.get("frame_index") is not None},
    )


def _matching_video_output(
    detail: dict[str, Any],
    by_order: dict[str, dict[str, Any]],
    by_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return by_order.get(str(detail.get("frame_order"))) or by_index.get(str(detail.get("frame_index"))) or {}


def _video_segmentation_frame(detail: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
    # frame_details 保存坐标与时序上下文，hotspot output 保存模型/启发式分割产物；这里只做字段对齐。
    segmentation_mask = _dict_field(output, "segmentation_mask")
    lesion_evidence = _dict_field(output, "lesion_evidence")
    quantification = _dict_field(output, "quantification")
    signal_masks = _dict_field(detail, "signal_masks") or _dict_field(output, "signal_masks")
    return {
        "frame_key": detail.get("frame_key"),
        "frame_order": detail.get("frame_order"),
        "frame_index": detail.get("frame_index"),
        "timestamp_sec": detail.get("timestamp_sec"),
        "evidence_path": detail.get("evidence_path") or detail.get("source_path"),
        "preview_path": detail.get("preview_path"),
        "segmentation_result": _frame_segmentation_result(
            output, detail, segmentation_mask, lesion_evidence, quantification
        ),
        "video_signal_segmentation": _frame_signal_result(detail, segmentation_mask, lesion_evidence, signal_masks),
        "fluorescence_overlay_result": _frame_overlay_result(detail, lesion_evidence),
        "candidate_result": _frame_candidate_result(detail),
        "review_routing": {
            "review_required": detail.get("review_required"),
            "review_priority": detail.get("review_priority"),
            "failure_reason": detail.get("failure_reason"),
            "target_domain_flag": detail.get("target_domain_flag"),
            "input_domain": detail.get("input_domain"),
            "data_boundary": detail.get("data_boundary"),
        },
        "spatial_mapping": detail.get("spatial_mapping"),
        "temporal_stability": detail.get("temporal_stability"),
        "medical_boundary": detail.get(
            "domain_boundary",
            "Heuristic keyframe hotspot analysis; requires physician review and is not a diagnosis.",
        ),
    }


def _frame_segmentation_result(
    output: dict[str, Any],
    detail: dict[str, Any],
    segmentation_mask: dict[str, Any],
    lesion_evidence: dict[str, Any],
    quantification: dict[str, Any],
) -> dict[str, Any]:
    return {
        "model_id": output.get("model_id") or "video_keyframe_hotspot_segmenter",
        "model_family": output.get("model_family"),
        "analysis_method": output.get("analysis_method"),
        "format": segmentation_mask.get("format", "png_binary_mask"),
        "mask_path": segmentation_mask.get("path") or detail.get("mask_path"),
        "probability_path": lesion_evidence.get("probability_path"),
        "uncertainty_path": segmentation_mask.get("uncertainty_path")
        or lesion_evidence.get("uncertainty_path")
        or detail.get("uncertainty_path"),
        "risk_mask_path": segmentation_mask.get("risk_mask_path")
        or lesion_evidence.get("risk_mask_path")
        or detail.get("risk_mask_path"),
        "uncertain_mask_path": segmentation_mask.get("uncertain_mask_path")
        or lesion_evidence.get("uncertain_mask_path")
        or detail.get("uncertain_mask_path"),
        "width": segmentation_mask.get("width"),
        "height": segmentation_mask.get("height"),
        "threshold": segmentation_mask.get("threshold"),
        "positive_area_px": segmentation_mask.get("positive_area_px"),
        "positive_area_fraction": quantification.get("positive_area_fraction"),
        "component_count": quantification.get("component_count"),
        "uncertainty": quantification.get("uncertainty"),
        "review_priority": quantification.get("review_priority") or detail.get("review_priority"),
        "target_domain_flag": quantification.get("target_domain_flag") or detail.get("target_domain_flag"),
        "failure_reason": lesion_evidence.get("failure_reason") or detail.get("failure_reason"),
    }


def _frame_signal_result(
    detail: dict[str, Any],
    segmentation_mask: dict[str, Any],
    lesion_evidence: dict[str, Any],
    signal_masks: dict[str, Any],
) -> dict[str, Any]:
    if signal_masks:
        return signal_masks
    mask_path = segmentation_mask.get("path") or detail.get("mask_path")
    risk_path = segmentation_mask.get("risk_mask_path") or lesion_evidence.get("risk_mask_path") or detail.get(
        "risk_mask_path"
    )
    uncertain_path = (
        segmentation_mask.get("uncertain_mask_path")
        or lesion_evidence.get("uncertain_mask_path")
        or detail.get("uncertain_mask_path")
    )
    return {
        "schema_version": "osteo-vision-video-signal-masks-v1",
        "bone_gate_mask": {
            "mask_type": "exposed_bone",
            "available": False,
            "status": "not_available_pending_review",
            "path": None,
        },
        "fluorescence_signal_mask": {
            "mask_type": "fluorescence_hotspot",
            "available": bool(mask_path),
            "path": mask_path,
            "probability_path": lesion_evidence.get("probability_path") or lesion_evidence.get("enhanced_path"),
        },
        "risk_mask": {"mask_type": "boundary_risk", "available": bool(risk_path), "path": risk_path},
        "uncertain_mask": {"mask_type": "uncertain", "available": bool(uncertain_path), "path": uncertain_path},
        "medical_boundary": detail.get(
            "video_signal_medical_boundary",
            "Video signal segmentation requires physician review and is not a diagnosis.",
        ),
    }


def _frame_overlay_result(detail: dict[str, Any], lesion_evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "format": "png_pseudocolor_overlay",
        "overlay_path": lesion_evidence.get("overlay_path") or detail.get("overlay_path"),
        "pseudo_color_path": lesion_evidence.get("pseudo_color_path") or detail.get("pseudo_color_path"),
        "enhanced_path": lesion_evidence.get("enhanced_path"),
    }


def _frame_candidate_result(detail: dict[str, Any]) -> dict[str, Any]:
    spatial_mapping = _dict_field(detail, "spatial_mapping")
    temporal_stability = _dict_field(detail, "temporal_stability")
    return {
        "top_component_bbox_xyxy": detail.get("top_component_bbox_xyxy"),
        "top_component_bbox_normalized": detail.get("top_component_bbox_normalized"),
        "top_component_bbox_source_xyxy": spatial_mapping.get("top_component_bbox_source_xyxy"),
        "top_component_bbox_source_normalized": spatial_mapping.get("top_component_bbox_source_normalized"),
        "bbox_temporal_smoothing_candidate_source_xyxy": temporal_stability.get("bbox_smoothing_candidate_source_xyxy"),
        "component_count": detail.get("component_count"),
        "review_required": detail.get("review_required"),
        "review_priority": detail.get("review_priority"),
    }


def _dict_field(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def _video_segmentation_model_summary(outputs: list[dict[str, Any]]) -> dict[str, Any]:
    model_ids = sorted(
        {
            str(output.get("model_id") or "video_keyframe_hotspot_segmenter")
            for output in outputs
            if isinstance(output, dict)
        }
    )
    methods = sorted(
        {str(output.get("analysis_method") or "unknown") for output in outputs if isinstance(output, dict)}
    )
    primary = model_ids[0] if len(model_ids) == 1 else "mixed_keyframe_segmentation"
    return {"primary_model_id": primary, "model_ids": model_ids, "analysis_methods": methods}
