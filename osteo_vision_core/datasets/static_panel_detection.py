from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

import numpy as np
from PIL import Image

DETECTOR_VERSION = "white-gutter-recursive-v1"


@dataclass(frozen=True)
class PanelCropSuggestion:
    bbox: dict[str, int]
    score: float
    quality_status: str
    quality_warnings: tuple[str, ...]
    method: str = DETECTOR_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["quality_warnings"] = list(self.quality_warnings)
        return payload


def detect_panel_crop_suggestions(
    image: Image.Image,
    *,
    expected_panel_count: int | None = None,
    max_panels: int = 12,
) -> list[PanelCropSuggestion]:
    rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    height, width = rgb.shape[:2]
    boxes = _recursive_boxes(rgb, (0, 0, width, height), depth=0, max_depth=3)
    if len(boxes) == 1:
        boxes = _fallback_boxes(width, height, expected_panel_count=expected_panel_count)
    boxes = _deduplicate_boxes(boxes)[:max_panels]
    suggestions = [_suggestion_for_box(rgb, box) for box in boxes]
    return sorted(suggestions, key=lambda item: (item.bbox["y"], item.bbox["x"]))


def crop_quality_warnings(
    image: Image.Image,
    bbox: dict[str, int],
    *,
    sibling_boxes: Iterable[dict[str, int]] = (),
) -> list[str]:
    rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    height, width = rgb.shape[:2]
    x = int(bbox["x"])
    y = int(bbox["y"])
    box_width = int(bbox["width"])
    box_height = int(bbox["height"])
    warnings: list[str] = []
    if x < 0 or y < 0 or box_width <= 0 or box_height <= 0 or x + box_width > width or y + box_height > height:
        return ["crop_out_of_bounds"]
    area_fraction = (box_width * box_height) / float(width * height)
    aspect_ratio = max(box_width / box_height, box_height / box_width)
    if min(box_width, box_height) < 96:
        warnings.append("crop_dimension_below_96px")
    if area_fraction < 0.02:
        warnings.append("crop_area_below_2_percent")
    if area_fraction > 0.9:
        warnings.append("crop_near_full_source_image")
    if aspect_ratio > 5.0:
        warnings.append("crop_extreme_aspect_ratio")
    crop = rgb[y : y + box_height, x : x + box_width]
    near_white = np.all(crop > 240, axis=2)
    near_black = np.all(crop < 12, axis=2)
    if float(near_white.mean()) > 0.2:
        warnings.append("crop_high_white_background_fraction")
    if _border_fraction(near_white) > 0.3:
        warnings.append("crop_white_border_residue")
    if _border_fraction(near_black) > 0.3:
        warnings.append("crop_black_border_residue")
    for sibling in sibling_boxes:
        if _bbox_iou(bbox, sibling) > 0.85 and sibling != bbox:
            warnings.append("crop_duplicate_candidate")
            break
    return sorted(set(warnings))


def _recursive_boxes(
    rgb: np.ndarray,
    box: tuple[int, int, int, int],
    *,
    depth: int,
    max_depth: int,
) -> list[tuple[int, int, int, int]]:
    x0, y0, x1, y1 = box
    region = rgb[y0:y1, x0:x1]
    height, width = region.shape[:2]
    if depth >= max_depth or min(width, height) < 128:
        return [box]
    vertical = _white_gutter_centers(region, axis="vertical")
    horizontal = _white_gutter_centers(region, axis="horizontal")
    x_edges = _split_edges(width, vertical, minimum_size=max(64, int(width * 0.12)))
    y_edges = _split_edges(height, horizontal, minimum_size=max(64, int(height * 0.12)))
    if len(x_edges) == 2 and len(y_edges) == 2:
        return [box]
    cells: list[tuple[int, int, int, int]] = []
    for row in range(len(y_edges) - 1):
        for column in range(len(x_edges) - 1):
            cell = (
                x0 + x_edges[column],
                y0 + y_edges[row],
                x0 + x_edges[column + 1],
                y0 + y_edges[row + 1],
            )
            cells.extend(_recursive_boxes(rgb, cell, depth=depth + 1, max_depth=max_depth))
    return cells


def _white_gutter_centers(rgb: np.ndarray, *, axis: str) -> list[int]:
    near_white = np.all(rgb > 240, axis=2)
    projection = near_white.mean(axis=0 if axis == "vertical" else 1)
    minimum_fraction = 0.7
    indices = np.flatnonzero(projection >= minimum_fraction)
    if indices.size == 0:
        return []
    length = rgb.shape[1] if axis == "vertical" else rgb.shape[0]
    orthogonal = rgb.shape[0] if axis == "vertical" else rgb.shape[1]
    centers: list[int] = []
    start = previous = int(indices[0])
    for raw_value in indices[1:]:
        value = int(raw_value)
        if value == previous + 1:
            previous = value
            continue
        _append_gutter_center(centers, start, previous, length=length, orthogonal=orthogonal)
        start = previous = value
    _append_gutter_center(centers, start, previous, length=length, orthogonal=orthogonal)
    return centers


def _append_gutter_center(
    centers: list[int],
    start: int,
    end: int,
    *,
    length: int,
    orthogonal: int,
) -> None:
    band_width = end - start + 1
    center = (start + end) // 2
    if center <= max(2, int(length * 0.02)) or center >= length - max(2, int(length * 0.02)):
        return
    if band_width > max(40, int(length * 0.08)):
        return
    if orthogonal < 1:
        return
    centers.append(center)


def _split_edges(length: int, centers: list[int], *, minimum_size: int) -> list[int]:
    edges = [0]
    for center in sorted(set(centers)):
        if center - edges[-1] < minimum_size:
            continue
        if length - center < minimum_size:
            continue
        edges.append(center)
    edges.append(length)
    return edges


def _fallback_boxes(width: int, height: int, *, expected_panel_count: int | None) -> list[tuple[int, int, int, int]]:
    if expected_panel_count == 2 and width / max(height, 1) >= 1.35:
        midpoint = width // 2
        return [(0, 0, midpoint, height), (midpoint, 0, width, height)]
    if width / max(height, 1) >= 2.4:
        midpoint = width // 2
        return [(0, 0, midpoint, height), (midpoint, 0, width, height)]
    if height / max(width, 1) >= 2.4:
        midpoint = height // 2
        return [(0, 0, width, midpoint), (0, midpoint, width, height)]
    return [(0, 0, width, height)]


def _suggestion_for_box(rgb: np.ndarray, box: tuple[int, int, int, int]) -> PanelCropSuggestion:
    x0, y0, x1, y1 = box
    bbox = {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0}
    image = Image.fromarray(rgb)
    warnings = crop_quality_warnings(image, bbox)
    blocking = {"crop_out_of_bounds", "crop_area_below_2_percent"}
    status = "blocked" if blocking.intersection(warnings) else ("warning" if warnings else "pass")
    score = 0.98 if status == "pass" else (0.78 if status == "warning" else 0.3)
    return PanelCropSuggestion(
        bbox=bbox,
        score=score,
        quality_status=status,
        quality_warnings=tuple(warnings),
    )


def _deduplicate_boxes(boxes: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    result: list[tuple[int, int, int, int]] = []
    for box in sorted(boxes, key=lambda value: (value[1], value[0], value[3], value[2])):
        candidate = {"x": box[0], "y": box[1], "width": box[2] - box[0], "height": box[3] - box[1]}
        if any(
            _bbox_iou(
                candidate,
                {
                    "x": existing[0],
                    "y": existing[1],
                    "width": existing[2] - existing[0],
                    "height": existing[3] - existing[1],
                },
            )
            > 0.85
            for existing in result
        ):
            continue
        result.append(box)
    return result


def _bbox_iou(first: dict[str, int], second: dict[str, int]) -> float:
    left = max(first["x"], second["x"])
    top = max(first["y"], second["y"])
    right = min(first["x"] + first["width"], second["x"] + second["width"])
    bottom = min(first["y"] + first["height"], second["y"] + second["height"])
    intersection = max(0, right - left) * max(0, bottom - top)
    if intersection <= 0:
        return 0.0
    union = first["width"] * first["height"] + second["width"] * second["height"] - intersection
    return intersection / float(max(union, 1))


def _border_fraction(mask: np.ndarray) -> float:
    if mask.size == 0:
        return 0.0
    border_width = max(1, min(mask.shape) // 40)
    border = np.concatenate(
        [
            mask[:border_width, :].ravel(),
            mask[-border_width:, :].ravel(),
            mask[:, :border_width].ravel(),
            mask[:, -border_width:].ravel(),
        ]
    )
    return float(border.mean())
