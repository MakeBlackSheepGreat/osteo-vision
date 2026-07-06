"""MP4 关键帧分割的空间映射与时序稳定性工具。

这些函数只负责几何坐标、bbox 缩放和关键帧元数据平滑；不直接修改二值 mask，
避免把复核辅助信息误当成模型真实逐帧推理结果。
"""

from __future__ import annotations

from typing import Any


def attach_video_temporal_context(frame_details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for index, detail in enumerate(frame_details):
        previous_detail = frame_details[index - 1] if index > 0 else None
        next_detail = frame_details[index + 1] if index + 1 < len(frame_details) else None
        window = [candidate for candidate in (previous_detail, detail, next_detail) if isinstance(candidate, dict)]
        fractions = [float(candidate.get("positive_area_fraction") or 0.0) for candidate in window]
        current_fraction = float(detail.get("positive_area_fraction") or 0.0)
        previous_fraction = (
            float(previous_detail.get("positive_area_fraction") or 0.0) if isinstance(previous_detail, dict) else None
        )
        next_fraction = (
            float(next_detail.get("positive_area_fraction") or 0.0) if isinstance(next_detail, dict) else None
        )
        bbox_source = _detail_source_bbox(detail)
        previous_bbox_source = _detail_source_bbox(previous_detail)
        smoothed_bbox = _median_bbox([_detail_source_bbox(candidate) for candidate in window])
        shift_px = _bbox_center_shift(bbox_source, previous_bbox_source)
        spatial_mapping = detail.get("spatial_mapping") if isinstance(detail.get("spatial_mapping"), dict) else {}
        source_width = positive_float(spatial_mapping.get("source_video_width") or spatial_mapping.get("mask_width"))
        source_height = positive_float(spatial_mapping.get("source_video_height") or spatial_mapping.get("mask_height"))
        source_diagonal = (source_width**2 + source_height**2) ** 0.5 if source_width and source_height else 0.0
        shift_fraction = float(shift_px / source_diagonal) if shift_px is not None and source_diagonal else None
        fraction_delta_previous = abs(current_fraction - previous_fraction) if previous_fraction is not None else None
        fraction_delta_next = abs(current_fraction - next_fraction) if next_fraction is not None else None
        instability_score = max(
            [
                value
                for value in (
                    fraction_delta_previous,
                    fraction_delta_next,
                    shift_fraction,
                )
                if value is not None
            ]
            or [0.0]
        )
        enriched_detail = {
            **detail,
            "temporal_stability": {
                "schema_version": "osteo-vision-keyframe-temporal-stability-v1",
                "smoothing_method": "three_frame_moving_average_metadata",
                "smoothing_applied_to_mask": False,
                "positive_area_fraction": current_fraction,
                "positive_area_fraction_smoothed": (
                    round(sum(fractions) / len(fractions), 8) if fractions else current_fraction
                ),
                "positive_area_fraction_delta_previous": (
                    round(fraction_delta_previous, 8) if fraction_delta_previous is not None else None
                ),
                "positive_area_fraction_delta_next": (
                    round(fraction_delta_next, 8) if fraction_delta_next is not None else None
                ),
                "bbox_center_shift_previous_px": round(shift_px, 4) if shift_px is not None else None,
                "bbox_center_shift_previous_fraction": (
                    round(shift_fraction, 8) if shift_fraction is not None else None
                ),
                "bbox_smoothing_candidate_source_xyxy": smoothed_bbox,
                "instability_score": round(float(instability_score), 8),
                "flicker_warning": bool(instability_score >= 0.05),
                "review_note": (
                    "Temporal values stabilize keyframe review metadata only; binary masks remain unchanged "
                    "and require physician review."
                ),
            },
        }
        enriched.append(enriched_detail)
    return enriched


def video_temporal_summary(frame_details: list[dict[str, Any]]) -> dict[str, Any]:
    stability_items = [
        detail.get("temporal_stability")
        for detail in frame_details
        if isinstance(detail.get("temporal_stability"), dict)
    ]
    instability_scores = [float(item.get("instability_score") or 0.0) for item in stability_items]
    previous_deltas = [
        float(item["positive_area_fraction_delta_previous"])
        for item in stability_items
        if item.get("positive_area_fraction_delta_previous") is not None
    ]
    shift_fractions = [
        float(item["bbox_center_shift_previous_fraction"])
        for item in stability_items
        if item.get("bbox_center_shift_previous_fraction") is not None
    ]
    return {
        "schema_version": "osteo-vision-video-temporal-stability-summary-v1",
        "frame_count": len(frame_details),
        "smoothing_method": "three_frame_moving_average_metadata",
        "smoothing_applied_to_mask": False,
        "instability_frame_count": sum(1 for item in stability_items if item.get("flicker_warning")),
        "max_instability_score": max(instability_scores) if instability_scores else 0.0,
        "mean_positive_area_fraction_delta_previous": (
            sum(previous_deltas) / len(previous_deltas) if previous_deltas else 0.0
        ),
        "max_bbox_center_shift_previous_fraction": max(shift_fractions) if shift_fractions else 0.0,
        "medical_boundary": "Temporal smoothing metadata is for review stability only and is not diagnostic.",
    }


def positive_float(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return parsed if parsed > 0 else 0.0


def safe_scale_ratio(numerator: float, denominator: float) -> float | None:
    if numerator <= 0 or denominator <= 0:
        return None
    return round(float(numerator) / float(denominator), 6)


def scaled_bbox(
    bbox: Any,
    *,
    from_width: float,
    from_height: float,
    to_width: float,
    to_height: float,
) -> list[int] | None:
    # 将 mask 坐标系的 bbox 映射回证据图或源视频坐标系，供前端叠加与医生复核使用。
    parsed = _int_bbox(bbox)
    if not parsed or from_width <= 0 or from_height <= 0 or to_width <= 0 or to_height <= 0:
        return None
    scale_x = float(to_width) / float(from_width)
    scale_y = float(to_height) / float(from_height)
    x0, y0, x1, y1 = parsed
    scaled = [
        int(round(x0 * scale_x)),
        int(round(y0 * scale_y)),
        int(round(x1 * scale_x)),
        int(round(y1 * scale_y)),
    ]
    scaled[0] = max(0, min(int(round(to_width)), scaled[0]))
    scaled[2] = max(0, min(int(round(to_width)), scaled[2]))
    scaled[1] = max(0, min(int(round(to_height)), scaled[1]))
    scaled[3] = max(0, min(int(round(to_height)), scaled[3]))
    if scaled[2] <= scaled[0] or scaled[3] <= scaled[1]:
        return None
    return scaled


def normalized_bbox(bbox: Any, *, width: float, height: float) -> dict[str, Any] | None:
    if not isinstance(bbox, list) or len(bbox) != 4 or width <= 0 or height <= 0:
        return None
    try:
        x0, y0, x1, y1 = [float(value) for value in bbox]
    except (TypeError, ValueError):
        return None
    x = max(0.0, min(1.0, x0 / width))
    y = max(0.0, min(1.0, y0 / height))
    rect_width = max(0.0, min(1.0 - x, (x1 - x0) / width))
    rect_height = max(0.0, min(1.0 - y, (y1 - y0) / height))
    if rect_width <= 0 or rect_height <= 0:
        return None
    return {
        "type": "rect",
        "coordinate_space": "normalized",
        "x": round(x, 6),
        "y": round(y, 6),
        "width": round(rect_width, 6),
        "height": round(rect_height, 6),
    }


def _detail_source_bbox(detail: Any) -> list[int] | None:
    if not isinstance(detail, dict):
        return None
    spatial_mapping = detail.get("spatial_mapping") if isinstance(detail.get("spatial_mapping"), dict) else {}
    bbox = spatial_mapping.get("top_component_bbox_source_xyxy") or detail.get("top_component_bbox_xyxy")
    return _int_bbox(bbox)


def _median_bbox(bboxes: list[list[int] | None]) -> list[int] | None:
    valid = [bbox for bbox in bboxes if bbox and len(bbox) == 4]
    if not valid:
        return None
    return [int(round(_median([bbox[index] for bbox in valid]))) for index in range(4)]


def _median(values: list[int]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return float(ordered[middle - 1] + ordered[middle]) / 2.0


def _bbox_center_shift(current: list[int] | None, previous: list[int] | None) -> float | None:
    if not current or not previous:
        return None
    current_x = (float(current[0]) + float(current[2])) / 2.0
    current_y = (float(current[1]) + float(current[3])) / 2.0
    previous_x = (float(previous[0]) + float(previous[2])) / 2.0
    previous_y = (float(previous[1]) + float(previous[3])) / 2.0
    return ((current_x - previous_x) ** 2 + (current_y - previous_y) ** 2) ** 0.5


def _int_bbox(bbox: Any) -> list[int] | None:
    if not isinstance(bbox, list) or len(bbox) != 4:
        return None
    try:
        parsed = [int(round(float(value))) for value in bbox]
    except (TypeError, ValueError):
        return None
    if parsed[2] <= parsed[0] or parsed[3] <= parsed[1]:
        return None
    return parsed
