from __future__ import annotations

from typing import Any

from backend.src.services.video_keyframe_metrics import (
    attach_video_temporal_context,
    normalized_bbox,
    positive_float,
    safe_scale_ratio,
    scaled_bbox,
)


def build_video_frame_details(
    keyframes: list[dict[str, Any]],
    hotspot_outputs: list[dict[str, Any]],
    *,
    keyframe_report: dict[str, Any],
) -> list[dict[str, Any]]:
    by_order = {
        str(output.get("frame_order")): output for output in hotspot_outputs if output.get("frame_order") is not None
    }
    by_index = {
        str(output.get("frame_index")): output for output in hotspot_outputs if output.get("frame_index") is not None
    }
    details: list[dict[str, Any]] = []
    source_width = positive_float(keyframe_report.get("width"))
    source_height = positive_float(keyframe_report.get("height"))
    for detail_index, frame in enumerate(keyframes):
        hotspot_candidate = by_order.get(str(frame.get("order"))) or by_index.get(str(frame.get("frame_index"))) or {}
        hotspot: dict[str, Any] = hotspot_candidate if isinstance(hotspot_candidate, dict) else {}
        quantification_candidate = hotspot.get("quantification")
        quantification: dict[str, Any] = quantification_candidate if isinstance(quantification_candidate, dict) else {}
        lesion_evidence_candidate = hotspot.get("lesion_evidence")
        lesion_evidence: dict[str, Any] = (
            lesion_evidence_candidate if isinstance(lesion_evidence_candidate, dict) else {}
        )
        signal_masks_candidate = hotspot.get("signal_masks") or hotspot.get("video_signal_segmentation")
        signal_masks: dict[str, Any] = signal_masks_candidate if isinstance(signal_masks_candidate, dict) else {}
        segmentation_mask_candidate = hotspot.get("segmentation_mask")
        segmentation_mask: dict[str, Any] = (
            segmentation_mask_candidate if isinstance(segmentation_mask_candidate, dict) else {}
        )
        inference_candidate = (
            quantification.get("inference") or segmentation_mask.get("inference") or lesion_evidence.get("inference")
        )
        inference: dict[str, Any] = inference_candidate if isinstance(inference_candidate, dict) else {}
        candidates = lesion_evidence.get("candidates")
        top_component = candidates[0] if isinstance(candidates, list) and candidates else {}
        top_component = top_component if isinstance(top_component, dict) else {}
        bbox = top_component.get("bbox_xyxy")
        width = positive_float(segmentation_mask.get("width"))
        height = positive_float(segmentation_mask.get("height"))
        evidence_width = positive_float(frame.get("evidence_width")) or width
        evidence_height = positive_float(frame.get("evidence_height")) or height
        target_width = source_width or evidence_width or width
        target_height = source_height or evidence_height or height
        frame_index = frame.get("frame_index")
        component_count = int(positive_float(quantification.get("component_count")))
        positive_fraction = float(quantification.get("positive_area_fraction", 0.0) or 0.0)
        top_component_bbox_normalized = normalized_bbox(bbox, width=width, height=height)
        bbox_source = scaled_bbox(
            bbox,
            from_width=width,
            from_height=height,
            to_width=target_width,
            to_height=target_height,
        )
        bbox_evidence = scaled_bbox(
            bbox,
            from_width=width,
            from_height=height,
            to_width=evidence_width,
            to_height=evidence_height,
        )
        bbox_source_normalized = normalized_bbox(bbox_source, width=target_width, height=target_height)
        details.append(
            {
                "frame_key": f"{frame_index}-{detail_index}",
                "frame_order": frame.get("order"),
                "frame_index": frame_index,
                "timestamp_sec": frame.get("timestamp_sec"),
                "preview_path": frame.get("preview_path") or frame.get("path"),
                "evidence_path": frame.get("evidence_path"),
                "source_path": hotspot.get("source_path") or frame.get("evidence_path") or frame.get("path"),
                "overlay_path": lesion_evidence.get("overlay_path"),
                "mask_path": segmentation_mask.get("path"),
                "probability_path": lesion_evidence.get("probability_path"),
                "uncertainty_path": segmentation_mask.get("uncertainty_path")
                or lesion_evidence.get("uncertainty_path"),
                "risk_mask_path": segmentation_mask.get("risk_mask_path") or lesion_evidence.get("risk_mask_path"),
                "uncertain_mask_path": segmentation_mask.get("uncertain_mask_path")
                or lesion_evidence.get("uncertain_mask_path"),
                "pseudo_color_path": lesion_evidence.get("pseudo_color_path"),
                "signal_masks": signal_masks,
                "video_signal_segmentation": signal_masks,
                "positive_area_fraction": positive_fraction,
                "roi_positive_area_fraction": float(quantification.get("roi_positive_area_fraction", 0.0) or 0.0),
                "component_count": component_count,
                "p95_intensity": quantification.get("p95_intensity"),
                "background_intensity": quantification.get("background_intensity", 0.0),
                "intensity_source": quantification.get("intensity_source"),
                "intensity_domain": quantification.get("intensity_domain"),
                "decoded_frame_intensity": quantification.get("decoded_frame_intensity", {}),
                "inference": inference,
                "top_component": top_component,
                "top_component_bbox_xyxy": bbox if isinstance(bbox, list) and len(bbox) == 4 else None,
                "top_component_bbox_normalized": top_component_bbox_normalized,
                "spatial_mapping": {
                    "schema_version": "osteo-vision-keyframe-spatial-mapping-v1",
                    "mask_coordinate_space": "keyframe_mask_pixels",
                    "evidence_coordinate_space": "keyframe_evidence_pixels",
                    "source_coordinate_space": "source_video_pixels",
                    "mask_width": int(width) if width else None,
                    "mask_height": int(height) if height else None,
                    "evidence_width": int(evidence_width) if evidence_width else None,
                    "evidence_height": int(evidence_height) if evidence_height else None,
                    "source_video_width": int(source_width) if source_width else None,
                    "source_video_height": int(source_height) if source_height else None,
                    "scale_x_mask_to_source": safe_scale_ratio(target_width, width),
                    "scale_y_mask_to_source": safe_scale_ratio(target_height, height),
                    "top_component_bbox_evidence_xyxy": bbox_evidence,
                    "top_component_bbox_source_xyxy": bbox_source,
                    "top_component_bbox_source_normalized": bbox_source_normalized,
                    "mapping_status": (
                        "source_video_coordinates_available"
                        if bbox_source and target_width and target_height
                        else "bbox_or_source_geometry_missing"
                    ),
                    "patch_based_inference": {
                        "applied": False,
                        "ready_coordinate_contract": "source_video_pixels_xyxy",
                    },
                },
                "selection_score": frame.get("selection_score"),
                "selection_rank": frame.get("selection_rank"),
                "quality": frame.get("quality", {}),
                "review_required": component_count > 0 or positive_fraction > 0,
                "review_priority": (
                    lesion_evidence.get("review_priority")
                    or segmentation_mask.get("review_priority")
                    or _review_priority_from_frame(component_count=component_count, positive_fraction=positive_fraction)
                ),
                "failure_reason": lesion_evidence.get("failure_reason") or None,
                "target_domain_flag": bool(
                    lesion_evidence.get("target_domain_flag") or segmentation_mask.get("target_domain_flag")
                ),
                "input_domain": lesion_evidence.get("input_domain"),
                "data_boundary": lesion_evidence.get("data_boundary"),
                "domain_boundary": hotspot.get(
                    "domain_boundary",
                    "Heuristic keyframe hotspot analysis; requires physician review and is not a diagnosis.",
                ),
                "video_signal_medical_boundary": signal_masks.get(
                    "medical_boundary",
                    "Video signal segmentation requires physician review and is not a diagnosis.",
                ),
            }
        )
    return attach_video_temporal_context(details)


def build_video_timeline_summary(keyframe_report: dict[str, Any]) -> dict[str, Any]:
    selection_trace = (
        keyframe_report.get("selection_trace") if isinstance(keyframe_report.get("selection_trace"), dict) else {}
    )
    candidates = selection_trace.get("candidates") if isinstance(selection_trace, dict) else []
    candidate_items = (
        [candidate for candidate in candidates if isinstance(candidate, dict)] if isinstance(candidates, list) else []
    )
    deduplication = selection_trace.get("deduplication") if isinstance(selection_trace, dict) else {}
    deduplication = deduplication if isinstance(deduplication, dict) else {}
    frame_count = _positive_int(keyframe_report.get("frame_count"))
    max_entries = _positive_int(keyframe_report.get("max_timeline_entries")) or 5000
    stride = max(1, int(_ceil_div(frame_count, max_entries))) if frame_count else 1
    duplicate_items = [item for item in candidate_items if item.get("skipped_as_duplicate")]
    selected_items = [item for item in candidate_items if item.get("selected")]
    return {
        "schema_version": "osteo-vision-timeline-summary-v1",
        "timeline_manifest_path": keyframe_report.get("timeline_manifest_path"),
        "frame_index_manifest_path": keyframe_report.get("frame_index_manifest_path"),
        "timeline_scope": "full_duration_index_with_scored_candidates",
        "sampling_strategy": keyframe_report.get("sampling_strategy") or keyframe_report.get("sampling"),
        "frame_count": frame_count,
        "fps": keyframe_report.get("fps"),
        "duration_sec": keyframe_report.get("duration_sec"),
        "timeline_stride": stride,
        "max_timeline_entries": max_entries,
        "selected_frame_count": len(keyframe_report.get("keyframes") or []),
        "candidate_frame_count": len(candidate_items),
        "duplicate_candidate_count": int(deduplication.get("duplicate_candidate_count") or 0),
        "skipped_duplicate_count": int(deduplication.get("skipped_duplicate_count") or 0),
        "backfilled_duplicate_count": int(deduplication.get("backfilled_duplicate_count") or 0),
        "deduplication": deduplication,
        "selected_trace": _timeline_trace_items(selected_items, limit=8),
        "duplicate_trace": _timeline_trace_items(duplicate_items, limit=8),
        "candidate_trace": _timeline_trace_items(candidate_items, limit=12),
    }


def _timeline_trace_items(items: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    trace_items: list[dict[str, Any]] = []
    for item in items[:limit]:
        trace_items.append(
            {
                "frame_index": item.get("frame_index"),
                "selection_rank": item.get("selection_rank"),
                "selection_score": item.get("selection_score"),
                "selected": bool(item.get("selected")),
                "skipped_as_duplicate": bool(item.get("skipped_as_duplicate")),
                "selected_after_duplicate_backfill": bool(item.get("selected_after_duplicate_backfill")),
                "duplicate_of_frame_index": item.get("duplicate_of_frame_index"),
                "duplicate_similarity": item.get("duplicate_similarity"),
                "duplicate_group": item.get("duplicate_group"),
            }
        )
    return trace_items


def _positive_int(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return parsed if parsed > 0 else 0


def _ceil_div(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return numerator
    return (numerator + denominator - 1) // denominator


def _review_priority_from_frame(*, component_count: int, positive_fraction: float) -> str:
    if component_count <= 0 or positive_fraction <= 0:
        return "low"
    if positive_fraction > 0.45:
        return "high"
    if positive_fraction >= 0.005:
        return "medium"
    return "low"
