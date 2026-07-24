from __future__ import annotations

from typing import Any

from backend.osteo_vision_api.domains.cases.schemas import CandidateRegion


def candidate_geometry(candidate: CandidateRegion) -> dict[str, Any]:
    geometry = candidate.metadata.get("bbox_normalized")
    if isinstance(geometry, dict) and geometry.get("type") == "rect":
        return {
            **geometry,
            "source": "candidate_region",
            "candidate_id": candidate.candidate_id,
        }
    return {"source": "candidate_region", "candidate_id": candidate.candidate_id}


def normalized_rect_geometry(geometry: dict[str, Any]) -> dict[str, Any]:
    if geometry.get("type") != "rect":
        return dict(geometry)
    x = _clamp_unit(geometry.get("x"))
    y = _clamp_unit(geometry.get("y"))
    width = min(_clamp_unit(geometry.get("width")), max(0.0, 1.0 - x))
    height = min(_clamp_unit(geometry.get("height")), max(0.0, 1.0 - y))
    return {
        **geometry,
        "type": "rect",
        "coordinate_space": "normalized",
        "x": round(x, 6),
        "y": round(y, 6),
        "width": round(width, 6),
        "height": round(height, 6),
    }


def bbox_xyxy_from_geometry(
    geometry: dict[str, Any],
    *,
    image_width: Any,
    image_height: Any,
) -> list[int] | None:
    """把前端归一化矩形复核框转换回像素坐标，供导出和回灌训练使用。"""

    if geometry.get("type") != "rect":
        return None
    width = _positive_int(image_width)
    height = _positive_int(image_height)
    if width is None or height is None:
        return None
    x = _clamp_unit(geometry.get("x"))
    y = _clamp_unit(geometry.get("y"))
    rect_width = _clamp_unit(geometry.get("width"))
    rect_height = _clamp_unit(geometry.get("height"))
    x0 = int(round(x * width))
    y0 = int(round(y * height))
    x1 = int(round(min(1.0, x + rect_width) * width))
    y1 = int(round(min(1.0, y + rect_height) * height))
    if x1 <= x0 or y1 <= y0:
        return None
    return [x0, y0, x1, y1]


def _clamp_unit(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, parsed))


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None
