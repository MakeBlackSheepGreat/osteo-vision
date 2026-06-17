from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np
from scipy import ndimage as ndi


def dice_score(intersection: float, pred_area: float, true_area: float) -> float:
    denominator = pred_area + true_area
    return 0.0 if denominator <= 0 else 2 * intersection / denominator


def iou_score(intersection: float, union: float) -> float:
    return 0.0 if union <= 0 else intersection / union


def binary_segmentation_metrics(
    pred_mask: np.ndarray,
    true_mask: np.ndarray,
    *,
    spacing: Iterable[float] | None = None,
    nsd_tolerance_mm: float = 1.0,
    include_cldice: bool = False,
) -> dict[str, Any]:
    pred = np.asarray(pred_mask).astype(bool)
    true = np.asarray(true_mask).astype(bool)
    if pred.shape != true.shape:
        raise ValueError("pred_mask and true_mask must have the same shape")
    spacing_tuple = tuple(float(item) for item in (spacing or (1.0,) * pred.ndim))
    if len(spacing_tuple) != pred.ndim:
        raise ValueError("spacing length must match mask dimensions")

    pred_area = float(pred.sum())
    true_area = float(true.sum())
    intersection = float(np.logical_and(pred, true).sum())
    union = float(np.logical_or(pred, true).sum())
    metrics: dict[str, Any] = {
        "present_in_prediction": bool(pred_area > 0),
        "present_in_target": bool(true_area > 0),
        "dice": 1.0 if pred_area == 0 and true_area == 0 else dice_score(intersection, pred_area, true_area),
        "iou": 1.0 if union == 0 else iou_score(intersection, union),
        "hd95": hd95(pred, true, spacing=spacing_tuple),
        "nsd": normalized_surface_dice(pred, true, spacing=spacing_tuple, tolerance_mm=nsd_tolerance_mm),
    }
    if include_cldice:
        metrics["cldice"] = cldice_score(pred, true)
    return metrics


def per_label_segmentation_metrics(
    prediction: np.ndarray,
    target: np.ndarray,
    labels: Iterable[int],
    *,
    spacing: Iterable[float] | None = None,
    nsd_tolerance_mm: float = 1.0,
    tubular_labels: Iterable[int] | None = None,
) -> dict[str, dict[str, Any]]:
    pred = np.asarray(prediction)
    true = np.asarray(target)
    if pred.shape != true.shape:
        raise ValueError("prediction and target must have the same shape")
    tubular = {int(item) for item in (tubular_labels or [])}
    return {
        str(int(label)): binary_segmentation_metrics(
            pred == int(label),
            true == int(label),
            spacing=spacing,
            nsd_tolerance_mm=nsd_tolerance_mm,
            include_cldice=int(label) in tubular,
        )
        for label in labels
    }


def hd95(pred_mask: np.ndarray, true_mask: np.ndarray, *, spacing: Iterable[float] | None = None) -> float | None:
    pred = np.asarray(pred_mask).astype(bool)
    true = np.asarray(true_mask).astype(bool)
    if not pred.any() and not true.any():
        return 0.0
    distances = _surface_distances(pred, true, spacing=spacing)
    if distances is None or distances.size == 0:
        return None
    return float(np.percentile(distances, 95))


def normalized_surface_dice(
    pred_mask: np.ndarray,
    true_mask: np.ndarray,
    *,
    spacing: Iterable[float] | None = None,
    tolerance_mm: float = 1.0,
) -> float | None:
    pred = np.asarray(pred_mask).astype(bool)
    true = np.asarray(true_mask).astype(bool)
    if not pred.any() and not true.any():
        return 1.0
    pred_to_true = _directed_surface_distances(pred, true, spacing=spacing)
    true_to_pred = _directed_surface_distances(true, pred, spacing=spacing)
    if pred_to_true is None or true_to_pred is None:
        return None
    total = pred_to_true.size + true_to_pred.size
    if total == 0:
        return None
    within = float((pred_to_true <= tolerance_mm).sum() + (true_to_pred <= tolerance_mm).sum())
    return within / total


def cldice_score(pred_mask: np.ndarray, true_mask: np.ndarray) -> float:
    pred = np.asarray(pred_mask).astype(bool)
    true = np.asarray(true_mask).astype(bool)
    if not pred.any() and not true.any():
        return 1.0
    if not pred.any() or not true.any():
        return 0.0
    pred_skeleton = morphological_skeleton(pred)
    true_skeleton = morphological_skeleton(true)
    tprec_denominator = float(pred_skeleton.sum())
    tsens_denominator = float(true_skeleton.sum())
    if tprec_denominator == 0 or tsens_denominator == 0:
        return 0.0
    tprec = float(np.logical_and(pred_skeleton, true).sum()) / tprec_denominator
    tsens = float(np.logical_and(true_skeleton, pred).sum()) / tsens_denominator
    denominator = tprec + tsens
    return 0.0 if denominator == 0 else 2.0 * tprec * tsens / denominator


def morphological_skeleton(mask: np.ndarray, *, max_iterations: int | None = None) -> np.ndarray:
    data = np.asarray(mask).astype(bool)
    if not data.any():
        return np.zeros(data.shape, dtype=bool)
    structure = ndi.generate_binary_structure(data.ndim, 1)
    skeleton = np.zeros(data.shape, dtype=bool)
    eroded = data.copy()
    iterations = 0
    limit = max_iterations or max(data.shape) * 2
    while eroded.any() and iterations < limit:
        opened = ndi.binary_opening(eroded, structure=structure)
        skeleton |= np.logical_and(eroded, np.logical_not(opened))
        eroded = ndi.binary_erosion(eroded, structure=structure)
        iterations += 1
    return skeleton


def _surface_distances(
    pred_mask: np.ndarray,
    true_mask: np.ndarray,
    *,
    spacing: Iterable[float] | None = None,
) -> np.ndarray | None:
    pred_to_true = _directed_surface_distances(pred_mask, true_mask, spacing=spacing)
    true_to_pred = _directed_surface_distances(true_mask, pred_mask, spacing=spacing)
    if pred_to_true is None or true_to_pred is None:
        return None
    return np.concatenate([pred_to_true, true_to_pred])


def _directed_surface_distances(
    source_mask: np.ndarray,
    target_mask: np.ndarray,
    *,
    spacing: Iterable[float] | None = None,
) -> np.ndarray | None:
    source = np.asarray(source_mask).astype(bool)
    target = np.asarray(target_mask).astype(bool)
    if not source.any() or not target.any():
        return None
    source_surface = _surface(source)
    target_surface = _surface(target)
    if not source_surface.any() or not target_surface.any():
        return None
    spacing_tuple = tuple(float(item) for item in (spacing or (1.0,) * source.ndim))
    distance_map = ndi.distance_transform_edt(~target_surface, sampling=spacing_tuple)
    return distance_map[source_surface]


def _surface(mask: np.ndarray) -> np.ndarray:
    structure = ndi.generate_binary_structure(mask.ndim, 1)
    eroded = ndi.binary_erosion(mask, structure=structure, border_value=0)
    return np.logical_and(mask, np.logical_not(eroded))

