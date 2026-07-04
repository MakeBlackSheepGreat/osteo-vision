from __future__ import annotations

import math
from typing import Any

import numpy as np


def normalized_rects_from_hints(roi_hints: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    rects: list[dict[str, Any]] = []
    for index, hint in enumerate(roi_hints or [], start=1):
        geometry = hint.get("geometry") if isinstance(hint.get("geometry"), dict) else hint
        if not isinstance(geometry, dict) or geometry.get("type") != "rect":
            continue
        x = _clamp_unit(_float_value(geometry.get("x")))
        y = _clamp_unit(_float_value(geometry.get("y")))
        width = _clamp_unit(_float_value(geometry.get("width")))
        height = _clamp_unit(_float_value(geometry.get("height")))
        if width <= 0.0 or height <= 0.0:
            continue
        rects.append(
            {
                "roi_id": str(hint.get("roi_id") or f"roi_hint_{index}"),
                "label": hint.get("label"),
                "x": x,
                "y": y,
                "width": min(width, 1.0 - x),
                "height": min(height, 1.0 - y),
            }
        )
    return rects


def roi_intensity_quantification(
    normalized: np.ndarray,
    roi_hints: list[dict[str, Any]] | None,
    *,
    threshold: float,
) -> dict[str, Any]:
    rects = normalized_rects_from_hints(roi_hints)
    per_roi: list[dict[str, Any]] = []
    positive_area = 0
    total_area = 0
    values: list[np.ndarray] = []
    for rect in rects:
        roi = _roi_array(normalized, rect)
        if roi is None or roi.size == 0:
            continue
        positive = roi >= float(threshold)
        roi_positive = int(np.count_nonzero(positive))
        roi_total = int(roi.size)
        positive_area += roi_positive
        total_area += roi_total
        values.append(roi.reshape(-1))
        per_roi.append(
            {
                "roi_id": rect["roi_id"],
                "label": rect.get("label"),
                "positive_area_px": roi_positive,
                "total_area_px": roi_total,
                "positive_area_fraction": round(float(roi_positive / roi_total), 6) if roi_total else 0.0,
                "mean_intensity": round(float(np.mean(roi)), 6),
                "max_intensity": round(float(np.max(roi)), 6),
                "p95_intensity": round(float(np.percentile(roi, 95)), 6),
            }
        )
    if values:
        merged = np.concatenate(values)
        mean_intensity = round(float(np.mean(merged)), 6)
        max_intensity = round(float(np.max(merged)), 6)
        p95_intensity = round(float(np.percentile(merged, 95)), 6)
    else:
        mean_intensity = 0.0
        max_intensity = 0.0
        p95_intensity = 0.0
    return {
        "roi_hint_count": len(roi_hints or []),
        "roi_quantification_count": len(per_roi),
        "roi_positive_area_px": positive_area,
        "roi_total_area_px": total_area,
        "roi_positive_area_fraction": round(float(positive_area / total_area), 6) if total_area else 0.0,
        "roi_mean_intensity": mean_intensity,
        "roi_max_intensity": max_intensity,
        "roi_p95_intensity": p95_intensity,
        "roi_quantifications": per_roi,
    }


def filter_candidates_by_roi(
    candidates: list[dict[str, Any]],
    roi_hints: list[dict[str, Any]] | None,
    *,
    width: int,
    height: int,
) -> list[dict[str, Any]]:
    rects = normalized_rects_from_hints(roi_hints)
    if not rects:
        return candidates
    filtered: list[dict[str, Any]] = []
    for candidate in candidates:
        bbox = candidate.get("bbox_xyxy")
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue
        overlap = _max_bbox_roi_overlap([float(value) for value in bbox], rects, width=width, height=height)
        if overlap <= 0.0:
            continue
        filtered.append({**candidate, "roi_overlap_fraction": round(overlap, 6)})
    return filtered


def _roi_array(array: np.ndarray, rect: dict[str, Any]) -> np.ndarray | None:
    height, width = array.shape[:2]
    x0 = max(0, min(width, math.floor(float(rect["x"]) * width)))
    y0 = max(0, min(height, math.floor(float(rect["y"]) * height)))
    x1 = max(0, min(width, math.ceil((float(rect["x"]) + float(rect["width"])) * width)))
    y1 = max(0, min(height, math.ceil((float(rect["y"]) + float(rect["height"])) * height)))
    if x1 <= x0 or y1 <= y0:
        return None
    return np.asarray(array[y0:y1, x0:x1], dtype=np.float32)


def _max_bbox_roi_overlap(bbox: list[float], rects: list[dict[str, Any]], *, width: int, height: int) -> float:
    bx0, by0, bx1, by1 = bbox
    bbox_area = max(0.0, bx1 - bx0) * max(0.0, by1 - by0)
    if bbox_area <= 0.0:
        return 0.0
    best = 0.0
    for rect in rects:
        rx0 = float(rect["x"]) * width
        ry0 = float(rect["y"]) * height
        rx1 = (float(rect["x"]) + float(rect["width"])) * width
        ry1 = (float(rect["y"]) + float(rect["height"])) * height
        ix0 = max(bx0, rx0)
        iy0 = max(by0, ry0)
        ix1 = min(bx1, rx1)
        iy1 = min(by1, ry1)
        overlap_area = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
        best = max(best, overlap_area / bbox_area)
    return best


def _float_value(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, value))
