from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from src.core.paths import ensure_dir
from src.preprocess.fluorescence import blend_pseudocolor_on_reference, enhance_fluorescence_signal
from src.preprocess.roi import filter_candidates_by_roi, roi_intensity_quantification


def segment_2d_fluorescence_hotspots(
    input_path: str | Path,
    *,
    output_dir: str | Path,
    case_id: str,
    threshold: float = 0.6,
    min_component_area: int = 25,
    colormap: str = "green",
    alpha: float = 0.45,
    model_id: str = "fluorescence_hotspot_2d_segmenter",
    roi_hints: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Segment bright fluorescence-like hotspots in a 2D image for platform validation evidence."""

    source = Path(input_path)
    out_dir = ensure_dir(output_dir)
    safe_case_id = _safe_name(case_id)
    with Image.open(source) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    enhanced = enhance_fluorescence_signal(rgb, threshold=threshold, colormap=colormap)
    enhanced_float = np.asarray(enhanced["enhanced"], dtype=np.float32)
    mask = (enhanced_float >= float(threshold)).astype(np.uint8)
    candidates = connected_hotspot_candidates(
        mask,
        enhanced_float,
        min_component_area=int(min_component_area),
        model_id=model_id,
    )
    candidates_before_roi = len(candidates)
    candidates = filter_candidates_by_roi(
        candidates,
        roi_hints,
        width=int(mask.shape[1]),
        height=int(mask.shape[0]),
    )
    mask_path = out_dir / f"{safe_case_id}_{model_id}_mask.png"
    enhanced_path = out_dir / f"{safe_case_id}_{model_id}_enhanced.png"
    pseudo_path = out_dir / f"{safe_case_id}_{model_id}_pseudo_color.png"
    overlay_path = out_dir / f"{safe_case_id}_{model_id}_overlay.png"
    overlay = blend_pseudocolor_on_reference(rgb, enhanced["pseudo_color"], alpha=alpha)
    Image.fromarray((mask * 255).astype(np.uint8)).save(mask_path)
    Image.fromarray(enhanced["enhanced_uint8"]).save(enhanced_path)
    Image.fromarray(enhanced["pseudo_color"]).save(pseudo_path)
    Image.fromarray(overlay).save(overlay_path)
    positive_area = int(mask.sum())
    total_area = int(mask.size)
    quantification = {
        **enhanced["quantification"],
        **roi_intensity_quantification(enhanced_float, roi_hints, threshold=threshold),
        "available": True,
        "source": model_id,
        "positive_area_px": positive_area,
        "total_area_px": total_area,
        "positive_area_fraction": float(positive_area / total_area) if total_area else 0.0,
        "component_count": len(candidates),
        "component_count_before_roi_filter": candidates_before_roi,
        "roi_filter_applied": bool(roi_hints),
        "min_component_area": int(min_component_area),
    }
    segmentation_mask = {
        "case_id": case_id,
        "source": model_id,
        "format": "png_binary_mask",
        "path": str(mask_path),
        "width": int(mask.shape[1]),
        "height": int(mask.shape[0]),
        "positive_area_px": positive_area,
        "threshold": float(threshold),
    }
    return {
        "prediction": {
            "segmentation_available": True,
            "mask_path": str(mask_path),
            "candidate_count": len(candidates),
            "positive_area_fraction": quantification["positive_area_fraction"],
        },
        "score": quantification["positive_area_fraction"],
        "segmentation_mask": segmentation_mask,
        "lesion_evidence": {
            "type": "2d_hotspot_mask",
            "source": model_id,
            "mask_path": str(mask_path),
            "enhanced_path": str(enhanced_path),
            "pseudo_color_path": str(pseudo_path),
            "overlay_path": str(overlay_path),
            "candidates": candidates,
            "input_domain": "2D fluorescence-like image proxy",
        },
        "quantification": quantification,
    }


def connected_hotspot_candidates(
    mask: np.ndarray,
    intensity: np.ndarray,
    *,
    min_component_area: int,
    model_id: str,
) -> list[dict[str, Any]]:
    try:
        import cv2

        component_count, labels, stats, _centroids = cv2.connectedComponentsWithStats(
            mask.astype(np.uint8), connectivity=8
        )
    except Exception:
        return _single_candidate(mask, intensity, min_component_area=min_component_area, model_id=model_id)
    candidates: list[dict[str, Any]] = []
    for label in range(1, component_count):
        x, y, width, height, area = [int(value) for value in stats[label]]
        if area < min_component_area:
            continue
        component = labels == label
        component_values = intensity[component]
        score = float(component_values.mean()) if component_values.size else 0.0
        candidates.append(
            {
                "candidate_id": f"{model_id}_component_{label}",
                "bbox_xyxy": [x, y, x + width, y + height],
                "area_px": area,
                "score": score,
                "confidence": float(component_values.max()) if component_values.size else 0.0,
                "source": model_id,
            }
        )
    candidates.sort(key=lambda item: (float(item["score"]), int(item["area_px"])), reverse=True)
    return candidates


def _single_candidate(
    mask: np.ndarray,
    intensity: np.ndarray,
    *,
    min_component_area: int,
    model_id: str,
) -> list[dict[str, Any]]:
    ys, xs = np.where(mask > 0)
    area = int(xs.size)
    if area < min_component_area:
        return []
    values = intensity[mask > 0]
    return [
        {
            "candidate_id": f"{model_id}_component_1",
            "bbox_xyxy": [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1],
            "area_px": area,
            "score": float(values.mean()) if values.size else 0.0,
            "confidence": float(values.max()) if values.size else 0.0,
            "source": model_id,
        }
    ]


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value) or "case"
