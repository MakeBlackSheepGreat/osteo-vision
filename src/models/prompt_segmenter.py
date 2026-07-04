from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from src.core.paths import ensure_dir
from src.preprocess.roi import normalized_rects_from_hints


def segment_2d_prompt_mask(
    input_path: str | Path,
    *,
    output_dir: str | Path,
    case_id: str,
    model_id: str,
    prompts: list[dict[str, Any]] | None = None,
    roi_hints: list[dict[str, Any]] | None = None,
    point_radius_px: int = 12,
) -> dict[str, Any]:
    """Create a prompt-defined 2D mask for MedSAM/SAM2 adapter contract testing.

    This is a deterministic prompt fallback. It preserves the intended bbox/point
    contract while real MedSAM/SAM2 weights are unavailable.
    """

    source = Path(input_path)
    out_dir = ensure_dir(output_dir)
    safe_case_id = _safe_name(case_id)
    with Image.open(source) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    height, width = rgb.shape[:2]
    parsed_prompts = _prompt_shapes(prompts, roi_hints, width=width, height=height, point_radius_px=point_radius_px)
    mask = np.zeros((height, width), dtype=np.uint8)
    for prompt in parsed_prompts:
        if prompt["type"] == "rect":
            x0, y0, x1, y1 = prompt["bbox_xyxy"]
            mask[y0:y1, x0:x1] = 1
        elif prompt["type"] == "point":
            cx, cy, radius = prompt["center_x"], prompt["center_y"], prompt["radius_px"]
            yy, xx = np.ogrid[:height, :width]
            mask[((xx - cx) ** 2 + (yy - cy) ** 2) <= radius**2] = 1
    overlay = _prompt_overlay(rgb, mask)
    mask_path = out_dir / f"{safe_case_id}_{model_id}_prompt_mask.png"
    overlay_path = out_dir / f"{safe_case_id}_{model_id}_prompt_overlay.png"
    Image.fromarray((mask * 255).astype(np.uint8)).save(mask_path)
    Image.fromarray(overlay).save(overlay_path)
    positive_area = int(mask.sum())
    total_area = int(mask.size)
    candidates = [
        {
            "candidate_id": f"{model_id}_prompt_{index:02d}",
            "source": model_id,
            "prompt_type": prompt["type"],
            "bbox_xyxy": prompt.get("bbox_xyxy"),
            "score": 1.0,
            "confidence": 1.0,
        }
        for index, prompt in enumerate(parsed_prompts, start=1)
    ]
    return {
        "prediction": {
            "segmentation_available": bool(parsed_prompts),
            "prompt_count": len(parsed_prompts),
            "mask_path": str(mask_path),
            "positive_area_fraction": float(positive_area / total_area) if total_area else 0.0,
            "adapter_mode": "prompt_contract_fallback",
        },
        "score": float(positive_area / total_area) if total_area else 0.0,
        "segmentation_mask": {
            "case_id": case_id,
            "source": model_id,
            "format": "png_binary_mask",
            "path": str(mask_path),
            "width": int(width),
            "height": int(height),
            "positive_area_px": positive_area,
            "prompt_defined": True,
        },
        "lesion_evidence": {
            "type": "medsam_like_prompt_mask",
            "source": model_id,
            "mask_path": str(mask_path),
            "overlay_path": str(overlay_path),
            "candidates": candidates,
            "prompt_contract": {
                "accepted_prompt_types": ["bbox_xyxy", "bbox_normalized", "roi_hints", "point"],
                "fallback_mode": True,
            },
            "input_domain": "2D image prompt fallback; not target-domain MedSAM2 inference",
        },
        "quantification": {
            "available": True,
            "source": model_id,
            "prompt_count": len(parsed_prompts),
            "positive_area_px": positive_area,
            "total_area_px": total_area,
            "positive_area_fraction": float(positive_area / total_area) if total_area else 0.0,
        },
    }


def _prompt_shapes(
    prompts: list[dict[str, Any]] | None,
    roi_hints: list[dict[str, Any]] | None,
    *,
    width: int,
    height: int,
    point_radius_px: int,
) -> list[dict[str, Any]]:
    shapes: list[dict[str, Any]] = []
    for rect in normalized_rects_from_hints(roi_hints):
        bbox = _bbox_from_normalized_rect(rect, width=width, height=height)
        if bbox:
            shapes.append({"type": "rect", "bbox_xyxy": bbox, "source": "roi_hint", "label": rect.get("label")})
    for prompt in prompts or []:
        bbox = _bbox_from_prompt(prompt, width=width, height=height)
        if bbox:
            shapes.append({"type": "rect", "bbox_xyxy": bbox, "source": prompt.get("source", "prompt")})
            continue
        point = _point_from_prompt(prompt, width=width, height=height)
        if point:
            shapes.append(
                {
                    "type": "point",
                    "center_x": point[0],
                    "center_y": point[1],
                    "radius_px": max(1, int(point_radius_px)),
                    "source": prompt.get("source", "prompt"),
                }
            )
    return shapes


def _bbox_from_prompt(prompt: dict[str, Any], *, width: int, height: int) -> list[int] | None:
    bbox = prompt.get("bbox_xyxy")
    if isinstance(bbox, list) and len(bbox) == 4:
        return _clipped_bbox(bbox, width=width, height=height)
    normalized = prompt.get("bbox_normalized") if isinstance(prompt.get("bbox_normalized"), dict) else None
    if normalized:
        return _bbox_from_normalized_rect(normalized, width=width, height=height)
    geometry = prompt.get("geometry") if isinstance(prompt.get("geometry"), dict) else None
    if geometry and geometry.get("type") == "rect":
        return _bbox_from_normalized_rect(geometry, width=width, height=height)
    return None


def _bbox_from_normalized_rect(rect: dict[str, Any], *, width: int, height: int) -> list[int] | None:
    x = _float_value(rect.get("x"))
    y = _float_value(rect.get("y"))
    rect_width = _float_value(rect.get("width"))
    rect_height = _float_value(rect.get("height"))
    if x is None or y is None or rect_width is None or rect_height is None:
        return None
    bbox = [x * width, y * height, (x + rect_width) * width, (y + rect_height) * height]
    return _clipped_bbox(bbox, width=width, height=height)


def _point_from_prompt(prompt: dict[str, Any], *, width: int, height: int) -> tuple[int, int] | None:
    point = prompt.get("point")
    if isinstance(point, dict):
        x = _float_value(point.get("x"))
        y = _float_value(point.get("y"))
        if x is None or y is None:
            return None
        if str(point.get("coordinate_space", "normalized")) == "pixel":
            return max(0, min(width - 1, round(x))), max(0, min(height - 1, round(y)))
        return max(0, min(width - 1, round(x * width))), max(0, min(height - 1, round(y * height)))
    return None


def _float_value(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clipped_bbox(values: list[Any], *, width: int, height: int) -> list[int] | None:
    try:
        x0, y0, x1, y1 = [round(float(value)) for value in values]
    except (TypeError, ValueError):
        return None
    clipped = [
        max(0, min(width, int(x0))),
        max(0, min(height, int(y0))),
        max(0, min(width, int(x1))),
        max(0, min(height, int(y1))),
    ]
    if clipped[2] <= clipped[0] or clipped[3] <= clipped[1]:
        return None
    return clipped


def _prompt_overlay(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    overlay = rgb.copy()
    color = np.zeros_like(rgb)
    color[..., 0] = 255
    color[..., 1] = 60
    color[..., 2] = 90
    alpha = 0.45
    active = mask.astype(bool)
    overlay[active] = ((1.0 - alpha) * overlay[active] + alpha * color[active]).astype(np.uint8)
    return overlay


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value) or "case"
