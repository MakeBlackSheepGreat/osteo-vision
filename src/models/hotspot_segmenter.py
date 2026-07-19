from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from src.core.paths import ensure_dir
from src.models.video_signal_masks import save_video_signal_maps, video_signal_mask_contract
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
    rgb: np.ndarray | None = None,
) -> dict[str, Any]:
    """Segment bright fluorescence-like hotspots in a 2D image for platform validation evidence."""

    source = Path(input_path)
    out_dir = ensure_dir(output_dir)
    safe_case_id = _safe_name(case_id)
    if rgb is None:
        with Image.open(source) as image:
            rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    else:
        rgb = np.asarray(rgb, dtype=np.uint8)
        if rgb.ndim != 3 or rgb.shape[2] < 3:
            raise ValueError(f"Predecoded hotspot frame must be RGB, got shape {rgb.shape}.")
        rgb = rgb[..., :3]
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
    signal_paths = save_video_signal_maps(
        probability=enhanced_float,
        mask=mask,
        uncertainty=None,
        output_dir=out_dir,
        safe_case=safe_case_id,
        model_id=model_id,
        threshold=float(threshold),
        activity_score_path=enhanced_path,
    )
    overlay = blend_pseudocolor_on_reference(rgb, enhanced["pseudo_color"], alpha=alpha)
    Image.fromarray((mask * 255).astype(np.uint8)).save(mask_path)
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
        "risk_mask_path": signal_paths["risk_mask_path"],
        "uncertain_mask_path": signal_paths["uncertain_mask_path"],
    }
    signal_masks = video_signal_mask_contract(
        mask_path=str(mask_path),
        risk_mask_path=str(signal_paths["risk_mask_path"]),
        uncertain_mask_path=str(signal_paths["uncertain_mask_path"]),
        width=int(mask.shape[1]),
        height=int(mask.shape[0]),
        positive_area_px=positive_area,
        threshold=float(threshold),
        source=model_id,
        probability_path=str(enhanced_path),
        overlay_path=str(overlay_path),
        risk_summary=signal_paths.get("risk_summary", {}),
        activity_score_path=signal_paths.get("activity_score_path"),
    )
    return {
        "prediction": {
            "segmentation_available": True,
            "mask_path": str(mask_path),
            "risk_mask_path": signal_paths["risk_mask_path"],
            "uncertain_mask_path": signal_paths["uncertain_mask_path"],
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
            "risk_mask_path": signal_paths["risk_mask_path"],
            "uncertain_mask_path": signal_paths["uncertain_mask_path"],
            "pseudo_color_path": str(pseudo_path),
            "overlay_path": str(overlay_path),
            "candidates": candidates,
            "signal_masks": signal_masks,
            "video_signal_segmentation": signal_masks,
            "input_domain": "2D fluorescence-like image proxy",
        },
        "quantification": quantification,
        "signal_masks": signal_masks,
        "video_signal_segmentation": signal_masks,
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
    flat_labels = np.asarray(labels, dtype=np.int32).ravel()
    flat_intensity = intensity.astype(np.float32, copy=False).ravel()
    component_count = int(component_count)
    component_sums = np.bincount(flat_labels, weights=flat_intensity, minlength=component_count)
    component_max = np.full(component_count, -np.inf, dtype=np.float32)
    np.maximum.at(component_max, flat_labels, flat_intensity)
    candidates: list[dict[str, Any]] = []
    for label in range(1, component_count):
        x, y, width, height, area = [int(value) for value in stats[label]]
        if area < min_component_area:
            continue
        candidates.append(
            {
                "candidate_id": f"{model_id}_component_{label}",
                "bbox_xyxy": [x, y, x + width, y + height],
                "area_px": area,
                "score": float(component_sums[label] / area) if area else 0.0,
                "confidence": float(component_max[label]) if area else 0.0,
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
