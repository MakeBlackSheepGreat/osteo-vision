from __future__ import annotations

import json
from collections import Counter
from math import hypot, isfinite, log1p
from pathlib import Path
from typing import Any, Mapping

import cv2
import numpy as np
from PIL import Image

from osteo_vision_core.core.paths import ensure_dir

BOUNDARY_ASSESSMENT_SCHEMA = "osteo-vision-lesion-boundary-assessment-v2"


def assess_candidate_boundaries(
    lesion_evidence: Mapping[str, Any],
    *,
    output_dir: str | Path,
    case_id: str,
    spatial_interpretation_allowed: bool = False,
    max_candidates_per_type: int = 64,
    max_total_candidates: int = 32,
    spatial_iou_threshold: float = 0.35,
    spatial_distance_fraction: float = 0.015,
    activity_spectrum: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Quantify candidate boundary risk and uncertainty for physician review routing."""

    candidates = [dict(item) for item in lesion_evidence.get("candidates", []) if isinstance(item, Mapping)]
    mask = _read_gray(lesion_evidence.get("mask_path"), binary=True)
    risk = _read_gray(lesion_evidence.get("risk_mask_path"), binary=False)
    uncertain = _read_gray(lesion_evidence.get("uncertain_mask_path"), binary=False)
    if mask is None or risk is None or uncertain is None or risk.shape != mask.shape or uncertain.shape != mask.shape:
        return {
            "schema_version": BOUNDARY_ASSESSMENT_SCHEMA,
            "available": False,
            "reason": "boundary_evidence_unavailable_or_mismatched",
            "candidates": [],
            "physician_review_required": True,
        }

    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    activity_map, activity_context = _load_activity_context(activity_spectrum, mask.shape)
    kernel = np.ones((3, 3), dtype=np.uint8)
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        label = _candidate_label(candidate.get("candidate_id"), component_count)
        component, risk_crop, uncertain_crop = _candidate_component_crop(
            mask,
            risk,
            uncertain,
            labels,
            stats,
            label,
            candidate,
        )
        if not bool(component.any()):
            continue
        boundary = cv2.subtract(
            cv2.dilate(component, kernel, iterations=1),
            cv2.erode(component, kernel, iterations=1),
        )
        boundary_pixels = boundary > 0
        risk_fraction = float(risk_crop[boundary_pixels].mean()) if boundary_pixels.any() else 0.0
        uncertainty_fraction = float(uncertain_crop[boundary_pixels].mean()) if boundary_pixels.any() else 1.0
        signal_confidence = _clamped_unit(candidate.get("score") or candidate.get("confidence") or 0.0)
        activity_class, activity_overlap = _candidate_activity_summary(
            candidate,
            label=label,
            stats=stats,
            labels=labels,
            activity_map=activity_map,
        )
        review_confidence = float(
            np.clip(
                signal_confidence * (1.0 - 0.6 * uncertainty_fraction - 0.25 * risk_fraction),
                0.0,
                1.0,
            )
        )
        if uncertainty_fraction >= 0.35:
            boundary_type = "uncertain_boundary"
        elif risk_fraction >= 0.45:
            boundary_type = "high_risk_transition_boundary"
        else:
            boundary_type = "signal_candidate_boundary"
        rows.append(
            {
                **candidate,
                "boundary_type": boundary_type,
                "boundary_pixel_count": int(boundary_pixels.sum()),
                "boundary_risk_fraction": round(risk_fraction, 6),
                "boundary_uncertainty_fraction": round(uncertainty_fraction, 6),
                "review_confidence": round(review_confidence, 6),
                "review_ranking_score": round(
                    _review_ranking_score(
                        candidate,
                        review_confidence,
                        risk_fraction,
                        uncertainty_fraction,
                    ),
                    6,
                ),
                "activity_class": activity_class,
                "activity_overlap_fraction": activity_overlap,
                "activity_evidence_available": activity_context["available"],
                "semantic_scope": "engineering_signal_boundary_for_physician_review",
            }
        )

    evaluated_type_counts = _type_counts(rows)
    evaluated_activity_counts = _activity_counts(rows)
    effective_max_per_type = _positive_int(max_candidates_per_type, default=64)
    effective_max_total = _positive_int(max_total_candidates, default=32)
    effective_iou_threshold = _clamped_unit(spatial_iou_threshold, default=0.35)
    effective_distance_fraction = max(0.0, _safe_float(spatial_distance_fraction, default=0.015))
    min_center_distance_px = max(4.0, float(min(mask.shape)) * effective_distance_fraction)
    retained, retention_audit = _retain_review_candidates(
        rows,
        max_per_type=effective_max_per_type,
        max_total_candidates=effective_max_total,
        spatial_iou_threshold=effective_iou_threshold,
        min_center_distance_px=min_center_distance_px,
    )
    retained_type_counts = _type_counts(retained)
    retained_activity_counts = _activity_counts(retained)
    suppressed_type_counts = {
        boundary_type: evaluated_type_counts[boundary_type] - retained_type_counts[boundary_type]
        for boundary_type in evaluated_type_counts
    }
    summary = {
        "schema_version": BOUNDARY_ASSESSMENT_SCHEMA,
        "available": True,
        "candidate_count": len(retained),
        "evaluated_candidate_count": len(rows),
        "suppressed_candidate_count": max(0, len(rows) - len(retained)),
        "boundary_type_counts": retained_type_counts,
        "evaluated_boundary_type_counts": evaluated_type_counts,
        "suppressed_boundary_type_counts": suppressed_type_counts,
        "activity_class_counts": retained_activity_counts,
        "evaluated_activity_class_counts": evaluated_activity_counts,
        "candidate_retention": {
            "method": "review_priority_spatial_diversity_nms_v3",
            "max_candidates_per_type": effective_max_per_type,
            "max_total_candidates": effective_max_total,
            "spatial_iou_threshold": round(effective_iou_threshold, 4),
            "min_center_distance_px": round(min_center_distance_px, 3),
            "input_candidate_count": len(candidates),
            "evaluated_candidate_count": len(rows),
            "retained_candidate_count": len(retained),
            **retention_audit,
        },
        "activity_evidence": activity_context,
        "candidates": retained,
        "spatial_interpretation_allowed": bool(spatial_interpretation_allowed),
        "review_priority": "standard" if spatial_interpretation_allowed else "high",
        "spatial_limitation": None if spatial_interpretation_allowed else "task2_registration_evidence_unavailable",
        "physician_review_required": True,
        "clinical_claim_allowed": False,
        "medical_boundary": (
            "Boundary types describe model signal, risk, and uncertainty layers for review routing. "
            "Pathological necrosis and surgical margins require physician and target-domain evidence."
        ),
    }
    root = ensure_dir(output_dir)
    summary_path = root / f"{_safe_name(case_id)}_boundary_assessment.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    return summary


def _read_gray(value: Any, *, binary: bool) -> np.ndarray | None:
    path = Path(str(value or "")).expanduser().resolve()
    if not path.is_file():
        return None
    try:
        with Image.open(path) as image:
            array = np.asarray(image.convert("L"), dtype=np.uint8).copy()
    except OSError:
        return None
    if binary:
        return (array > 127).astype(np.uint8)
    return array.astype(np.float32) / 255.0


def _load_activity_context(
    spectrum: Mapping[str, Any] | None,
    shape: tuple[int, int],
) -> tuple[np.ndarray | None, dict[str, Any]]:
    """Load an optional reviewed bone-activity class map without opening a clinical claim path."""

    value = dict(spectrum) if isinstance(spectrum, Mapping) else {}
    class_map_path = Path(str(value.get("activity_class_map_path") or "")).expanduser().resolve()
    class_map: np.ndarray | None = None
    if class_map_path.is_file():
        try:
            with Image.open(class_map_path) as image:
                class_map = np.asarray(image.convert("L"), dtype=np.uint8).copy()
        except OSError:
            class_map = None
    if class_map is None and value.get("available") is True:
        class_map = np.zeros(shape, dtype=np.uint8)
        found = False
        for class_value, key in (
            (1, "low_activity_candidate"),
            (2, "transition_candidate"),
            (3, "high_activity_candidate"),
            (4, "ignore_region"),
        ):
            path = Path(str(_mapping(value.get(key)).get("path") or "")).expanduser().resolve()
            if not path.is_file():
                continue
            try:
                with Image.open(path) as image:
                    layer = np.asarray(image.convert("L"), dtype=np.uint8) > 127
            except OSError:
                continue
            if layer.shape != shape:
                layer = (
                    cv2.resize(
                        layer.astype(np.uint8),
                        (shape[1], shape[0]),
                        interpolation=cv2.INTER_NEAREST,
                    )
                    > 0
                )
            class_map[layer] = class_value
            found = True
        if not found:
            class_map = None
    if class_map is not None and class_map.shape != shape:
        class_map = cv2.resize(class_map, (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST)
    available = class_map is not None and bool(value.get("available") is True)
    if not available:
        class_map = None
    return class_map, {
        "available": available,
        "status": value.get("status") or "pending_reviewed_bone_gate",
        "activity_class_map_path": str(class_map_path) if available else None,
        "calibration_status": value.get("calibration_status") or "pending_target_domain_validation",
        "medical_boundary": (
            "Activity class is a reviewed-bone-gate engineering reference and requires physician confirmation."
        ),
    }


def _candidate_activity_summary(
    candidate: Mapping[str, Any],
    *,
    label: int | None,
    stats: np.ndarray,
    labels: np.ndarray,
    activity_map: np.ndarray | None,
) -> tuple[str, float | None]:
    if activity_map is None:
        return "unavailable_pending_reviewed_bone_gate", None
    if label is not None:
        x, y, width, height, _area = [int(value) for value in stats[label]]
        component = labels[y : y + height, x : x + width] == label
        classes = activity_map[y : y + height, x : x + width][component]
    else:
        clamped_bbox = _clamped_candidate_bbox(candidate, activity_map.shape)
        if clamped_bbox is None:
            return "unavailable_pending_reviewed_bone_gate", None
        x0, y0, x1, y1 = clamped_bbox
        classes = activity_map[y0:y1, x0:x1].ravel()
    classes = np.asarray(classes, dtype=np.uint8)
    classes = classes[classes > 0]
    if classes.size == 0:
        return "outside_reviewed_bone_gate", 0.0
    counts = np.bincount(classes, minlength=5)
    dominant = int(np.argmax(counts[1:]) + 1)
    labels_by_value = {
        1: "low_activity_candidate",
        2: "transition_candidate",
        3: "high_activity_candidate",
        4: "ignore_region",
    }
    return labels_by_value.get(dominant, "outside_reviewed_bone_gate"), round(
        float(counts[dominant] / max(1, classes.size)),
        6,
    )


def _candidate_label(value: Any, component_count: int) -> int | None:
    suffix = str(value or "").rsplit("_component_", maxsplit=1)
    if len(suffix) != 2:
        return None
    try:
        label = int(suffix[1])
    except ValueError:
        return None
    return label if 0 < label < component_count else None


def _candidate_component_crop(
    mask: np.ndarray,
    risk: np.ndarray,
    uncertain: np.ndarray,
    labels: np.ndarray,
    stats: np.ndarray,
    label: int | None,
    candidate: Mapping[str, Any],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    height, width = mask.shape
    if label is not None:
        x, y, component_width, component_height, _area = [int(value) for value in stats[label]]
        x0, y0 = max(0, x - 1), max(0, y - 1)
        x1, y1 = (
            min(width, x + component_width + 1),
            min(height, y + component_height + 1),
        )
        component = (labels[y0:y1, x0:x1] == label).astype(np.uint8)
    else:
        clamped_bbox = _clamped_candidate_bbox(candidate, mask.shape)
        if clamped_bbox is None:
            empty = np.zeros((0, 0), dtype=np.uint8)
            return empty, empty.astype(np.float32), empty.astype(np.float32)
        raw_x0, raw_y0, raw_x1, raw_y1 = clamped_bbox
        x0, y0 = max(0, raw_x0 - 1), max(0, raw_y0 - 1)
        x1, y1 = min(width, raw_x1 + 1), min(height, raw_y1 + 1)
        component = mask[y0:y1, x0:x1].astype(np.uint8, copy=False)
    return component, risk[y0:y1, x0:x1], uncertain[y0:y1, x0:x1]


def _type_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    values = (
        "signal_candidate_boundary",
        "high_risk_transition_boundary",
        "uncertain_boundary",
    )
    counts = Counter(str(item.get("boundary_type") or "") for item in rows)
    return {value: counts[value] for value in values}


def _activity_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    values = (
        "low_activity_candidate",
        "transition_candidate",
        "high_activity_candidate",
        "ignore_region",
        "outside_reviewed_bone_gate",
        "unavailable_pending_reviewed_bone_gate",
    )
    counts = Counter(str(item.get("activity_class") or "") for item in rows)
    return {value: counts[value] for value in values}


def _retain_review_candidates(
    rows: list[dict[str, Any]],
    *,
    max_per_type: int,
    max_total_candidates: int,
    spatial_iou_threshold: float,
    min_center_distance_px: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    safe_limit = _positive_int(max_per_type, default=1)
    total_limit = _positive_int(max_total_candidates, default=1)
    threshold = _clamped_unit(spatial_iou_threshold, default=0.35)
    center_distance = max(0.0, _safe_float(min_center_distance_px))
    retained: list[dict[str, Any]] = []
    overlap_suppressed = 0
    spatial_comparison_count = 0
    type_order = (
        "signal_candidate_boundary",
        "high_risk_transition_boundary",
        "uncertain_boundary",
    )
    by_type: dict[str, list[dict[str, Any]]] = {}
    for boundary_type in type_order:
        by_type[boundary_type] = []
    for item in rows:
        by_type.setdefault(str(item.get("boundary_type") or ""), []).append(item)
    for matching in by_type.values():
        matching.sort(key=_candidate_ranking_key, reverse=True)

    # Reserve one high-quality candidate per available boundary type before
    # filling the remaining budget. This keeps rare risk states visible while
    # the second pass removes nearby fragments from the same type.
    selected_by_type: dict[str, list[dict[str, Any]]] = {key: [] for key in by_type}
    for boundary_type in type_order:
        matching = by_type.get(boundary_type, [])
        if len(retained) >= total_limit:
            break
        if not matching:
            continue
        selected_by_type[boundary_type].append(matching[0])
        retained.append(matching[0])

    for boundary_type in type_order:
        if len(retained) >= total_limit:
            break
        matching = by_type.get(boundary_type, [])
        selected = selected_by_type.setdefault(boundary_type, [])
        remaining = matching[1:] if selected else matching
        for item in remaining:
            if len(selected) >= safe_limit or len(retained) >= total_limit:
                break
            duplicate = False
            for previous in selected:
                spatial_comparison_count += 1
                if _candidate_is_spatial_duplicate(
                    item,
                    previous,
                    iou_threshold=threshold,
                    min_center_distance_px=center_distance,
                ):
                    duplicate = True
                    break
            if duplicate:
                overlap_suppressed += 1
                continue
            selected.append(item)
            retained.append(item)
    retained.sort(
        key=lambda item: (
            _safe_float(item.get("review_ranking_score")),
            _safe_float(item.get("review_confidence")),
        ),
        reverse=True,
    )
    return retained, {
        "spatial_overlap_suppressed_count": overlap_suppressed,
        "spatial_comparison_count": spatial_comparison_count,
        "spatially_diverse_retained_count": len(retained),
    }


def _candidate_is_spatial_duplicate(
    candidate: Mapping[str, Any],
    previous: Mapping[str, Any],
    *,
    iou_threshold: float,
    min_center_distance_px: float,
) -> bool:
    candidate_box = _candidate_bbox(candidate)
    previous_box = _candidate_bbox(previous)
    if candidate_box is None or previous_box is None:
        return False
    if _bbox_iou(candidate_box, previous_box) >= iou_threshold:
        return True
    candidate_center = (
        (candidate_box[0] + candidate_box[2]) * 0.5,
        (candidate_box[1] + candidate_box[3]) * 0.5,
    )
    previous_center = (
        (previous_box[0] + previous_box[2]) * 0.5,
        (previous_box[1] + previous_box[3]) * 0.5,
    )
    return (
        hypot(
            candidate_center[0] - previous_center[0],
            candidate_center[1] - previous_center[1],
        )
        < min_center_distance_px
    )


def _candidate_bbox(
    candidate: Mapping[str, Any],
) -> tuple[float, float, float, float] | None:
    value = candidate.get("bbox_xyxy")
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        x0, y0, x1, y1 = (float(item) for item in value)
    except (TypeError, ValueError):
        return None
    if not all(isfinite(item) for item in (x0, y0, x1, y1)) or x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1, y1


def _clamped_candidate_bbox(
    candidate: Mapping[str, Any],
    shape: tuple[int, int],
) -> tuple[int, int, int, int] | None:
    bbox = _candidate_bbox(candidate)
    if bbox is None:
        return None
    height, width = shape
    x0, y0, x1, y1 = (int(value) for value in bbox)
    x0, x1 = max(0, min(width, x0)), max(0, min(width, x1))
    y0, y1 = max(0, min(height, y0)), max(0, min(height, y1))
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1, y1


def _candidate_ranking_key(item: Mapping[str, Any]) -> tuple[float, float, float]:
    return (
        _safe_float(item.get("review_ranking_score")),
        _safe_float(item.get("review_confidence")),
        _safe_float(item.get("area_px")),
    )


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if isfinite(result) else default


def _clamped_unit(value: Any, *, default: float = 0.0) -> float:
    return min(1.0, max(0.0, _safe_float(value, default=default)))


def _positive_int(value: Any, *, default: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError):
        result = default
    return max(1, result)


def _bbox_iou(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    x0 = max(first[0], second[0])
    y0 = max(first[1], second[1])
    x1 = min(first[2], second[2])
    y1 = min(first[3], second[3])
    intersection = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    if intersection <= 0.0:
        return 0.0
    first_area = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1])
    second_area = max(0.0, second[2] - second[0]) * max(0.0, second[3] - second[1])
    return float(intersection / max(first_area + second_area - intersection, 1e-6))


def _review_ranking_score(
    candidate: Mapping[str, Any],
    review_confidence: float,
    risk_fraction: float,
    uncertainty_fraction: float,
) -> float:
    area = max(1.0, _safe_float(candidate.get("area_px"), default=1.0))
    area_weight = min(1.0, log1p(area) / log1p(4096.0))
    evidence_strength = max(
        _safe_float(review_confidence),
        _safe_float(risk_fraction),
        _safe_float(uncertainty_fraction),
    )
    return min(1.0, max(0.0, 0.75 * evidence_strength + 0.25 * area_weight))


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in str(value))


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
