from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

VIDEO_SIGNAL_MASK_TAXONOMY: dict[str, dict[str, str]] = {
    "exposed_bone": {
        "label": "Exposed bone or suspected bone surface",
        "boundary": "Requires physician or SAM-assisted review; not inferred as ground truth in v1.",
    },
    "soft_tissue": {
        "label": "Surrounding soft tissue",
        "boundary": "Optional assisted annotation target; not a disease label.",
    },
    "instrument_or_occlusion": {
        "label": "Instrument, smoke, glare, or occlusion",
        "boundary": "Quality and review routing signal.",
    },
    "fluorescence_hotspot": {
        "label": "High fluorescence signal",
        "boundary": "Perfusion or fluorescence signal candidate; not disease-specific.",
    },
    "hypo_fluorescent_bone": {
        "label": "Hypo-fluorescent area within exposed bone",
        "boundary": "Requires bone gate review before use as boundary-risk evidence.",
    },
    "boundary_risk": {
        "label": "Boundary risk or transition zone",
        "boundary": "Decision-support risk prompt requiring physician review.",
    },
    "uncertain": {
        "label": "Low-confidence or quality-limited area",
        "boundary": "Uncertainty prompt; not a segmentation target by itself.",
    },
}

VIDEO_SIGNAL_MEDICAL_BOUNDARY = (
    "Video signal segmentation describes fluorescence/perfusion activity, uncertainty, and review routing. "
    "It is not an automatic jaw osteomyelitis diagnosis or a physician-verified disease boundary."
)


def save_video_signal_maps(
    *,
    probability: np.ndarray,
    mask: np.ndarray,
    uncertainty: np.ndarray | None,
    output_dir: str | Path,
    safe_case: str,
    model_id: str,
    threshold: float,
) -> dict[str, Any]:
    """Write v1 risk and uncertain masks without changing the binary segmentation mask."""

    out_dir = Path(output_dir)
    risk = risk_from_signal(probability=probability, mask=mask, uncertainty=uncertainty)
    uncertain = uncertain_from_signal(probability=probability, uncertainty=uncertainty, threshold=threshold)
    risk_path = out_dir / f"{safe_case}_{model_id}_risk.png"
    uncertain_mask_path = out_dir / f"{safe_case}_{model_id}_uncertain_mask.png"
    activity_score_path = out_dir / f"{safe_case}_{model_id}_activity_score.png"
    Image.fromarray(np.clip(risk * 255.0, 0, 255).astype(np.uint8)).save(risk_path)
    Image.fromarray((uncertain * 255).astype(np.uint8)).save(uncertain_mask_path)
    Image.fromarray(np.clip(np.asarray(probability) * 255.0, 0, 255).astype(np.uint8)).save(activity_score_path)
    return {
        "risk_mask_path": str(risk_path),
        "uncertain_mask_path": str(uncertain_mask_path),
        "activity_score_path": str(activity_score_path),
        "risk_summary": {
            "method": "fluorescence_signal_with_uncertainty_v1",
            "mean_risk": float(risk.mean()) if risk.size else 0.0,
            "max_risk": float(risk.max()) if risk.size else 0.0,
            "risk_area_fraction": float((risk >= max(0.05, float(threshold) * 0.5)).mean()) if risk.size else 0.0,
            "uncertain_area_fraction": float(uncertain.mean()) if uncertain.size else 0.0,
            "smoothing_applied_to_mask": False,
        },
    }


def video_signal_mask_contract(
    *,
    mask_path: str,
    risk_mask_path: str,
    uncertain_mask_path: str,
    width: int,
    height: int,
    positive_area_px: int,
    threshold: float,
    source: str,
    probability_path: str | None = None,
    uncertainty_path: str | None = None,
    overlay_path: str | None = None,
    risk_summary: dict[str, Any] | None = None,
    activity_score_path: str | None = None,
    activity_class_map_path: str | None = None,
    bone_gate_status: str = "not_available_pending_review",
) -> dict[str, Any]:
    activity_candidates = derive_bone_activity_candidates(
        probability=None,
        threshold=threshold,
        bone_gate=None,
        bone_gate_status=bone_gate_status,
        activity_score_path=activity_score_path or probability_path,
        activity_class_map_path=activity_class_map_path,
    )
    return {
        "schema_version": "osteo-vision-video-signal-masks-v2",
        "taxonomy": VIDEO_SIGNAL_MASK_TAXONOMY,
        "bone_gate_mask": {
            "mask_type": "exposed_bone",
            "available": False,
            "status": "not_available_pending_review",
            "path": None,
            "label_source": "pending_sam_or_physician_review",
            "medical_boundary": (
                "Bone gate is intentionally not inferred in v1 without physician or SAM-assisted annotation."
            ),
        },
        "fluorescence_signal_mask": {
            "mask_type": "fluorescence_hotspot",
            "available": True,
            "format": "png_binary_mask",
            "path": mask_path,
            "probability_path": probability_path,
            "overlay_path": overlay_path,
            "width": int(width),
            "height": int(height),
            "positive_area_px": int(positive_area_px),
            "threshold": float(threshold),
            "label_source": source,
            "medical_boundary": "Fluorescence signal mask is a perfusion/activity proxy and not a disease-specific label.",
        },
        "risk_mask": {
            "mask_type": "boundary_risk",
            "available": True,
            "format": "png_grayscale_risk_map",
            "path": risk_mask_path,
            "summary": risk_summary or {},
            "medical_boundary": "Risk mask is a decision-support prompt requiring physician review.",
        },
        "uncertain_mask": {
            "mask_type": "uncertain",
            "available": True,
            "format": "png_binary_mask",
            "path": uncertain_mask_path,
            "uncertainty_path": uncertainty_path,
            "medical_boundary": "Uncertain mask marks low-confidence or quality-limited areas.",
        },
        "bone_activity_spectrum": activity_candidates,
        "medical_boundary": VIDEO_SIGNAL_MEDICAL_BOUNDARY,
    }


def derive_bone_activity_candidates(
    *,
    probability: np.ndarray | None,
    threshold: float,
    bone_gate: np.ndarray | None,
    bone_gate_status: str,
    activity_score_path: str | None = None,
    activity_class_map_path: str | None = None,
    ignore_mask: np.ndarray | None = None,
    ignore_sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Derive a review-gated activity spectrum without changing the model prediction."""

    reviewed_statuses = {"physician_accepted", "physician_modified", "reviewed_bone_gate"}
    gate_reviewed = bone_gate is not None and bone_gate_status in reviewed_statuses
    candidates_available = bool(gate_reviewed and probability is not None)
    sources = _normalized_ignore_sources(ignore_sources)
    result: dict[str, Any] = {
        "schema_version": "osteo-vision-bone-activity-spectrum-v2",
        "available": candidates_available,
        "status": "available_for_physician_review" if gate_reviewed else "pending_reviewed_bone_gate",
        "activity_score": {
            "available": probability is not None or bool(activity_score_path),
            "path": activity_score_path,
            "scale": [0.0, 1.0],
            "meaning": "Continuous fluorescence or perfusion activity reference score.",
        },
        "activity_class_map_path": activity_class_map_path if candidates_available else None,
        "low_activity_candidate": {"available": candidates_available, "label": "低活性候选"},
        "transition_candidate": {"available": candidates_available, "label": "过渡复核区"},
        "high_activity_candidate": {"available": candidates_available, "label": "高活性参考"},
        "ignore_region": {
            "available": candidates_available,
            "label": "无法判断区",
            "positive_area_px": None,
            "bone_gate_fraction": None,
            "path": None,
            "sha256": None,
            "sources": sources,
        },
        "class_map_encoding": {
            "0": "outside_reviewed_bone_gate",
            "1": "low_activity_candidate",
            "2": "transition_candidate",
            "3": "high_activity_candidate",
            "4": "ignore_region",
        },
        "partition_check": None,
        "thresholds": {
            "low_max": float(np.clip(threshold * 0.5, 0.0, 1.0)),
            "high_min": float(np.clip(threshold, 0.0, 1.0)),
        },
        "confidence_statement": "0.80 等数值仅表示信号候选置信度，不表示切除成功率或可切除比例。",
        "calibration_status": "pending_target_domain_validation",
        "spatial_effect_applied": False,
        "review_required": True,
        "medical_boundary": "空间活性候选需基于已复核骨面门控，并由医生确认。",
    }
    if not gate_reviewed or probability is None:
        return result
    assert bone_gate is not None

    probability_float, gate, ignored, low, transition, high = _bone_activity_partition(
        probability=probability,
        bone_gate=bone_gate,
        threshold=threshold,
        ignore_mask=ignore_mask,
    )
    gate_area = int(gate.sum())
    for key, candidate in (
        ("low_activity_candidate", low),
        ("transition_candidate", transition),
        ("high_activity_candidate", high),
    ):
        result[key]["positive_area_px"] = int(candidate.sum())
        result[key]["bone_gate_fraction"] = float(candidate.sum() / gate_area) if gate_area else 0.0
    result["ignore_region"]["positive_area_px"] = int(ignored.sum())
    result["ignore_region"]["bone_gate_fraction"] = float(ignored.sum() / gate_area) if gate_area else 0.0
    result["partition_check"] = _partition_check(
        gate=gate,
        ignored=ignored,
        low=low,
        transition=transition,
        high=high,
    )
    result["spatial_effect_applied"] = True
    return result


def save_bone_activity_candidate_maps(
    *,
    probability: np.ndarray,
    bone_gate: np.ndarray,
    threshold: float,
    output_dir: str | Path,
    safe_case: str,
    bone_gate_status: str = "reviewed_bone_gate",
    activity_score_path: str | None = None,
    ignore_mask: np.ndarray | None = None,
    ignore_sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Materialize review-gated activity candidates and their compact class map."""

    probability_float, gate, ignored, low, transition, high = _bone_activity_partition(
        probability=probability,
        bone_gate=bone_gate,
        threshold=threshold,
        ignore_mask=ignore_mask,
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    class_map = np.zeros(probability_float.shape, dtype=np.uint8)
    class_map[low] = 1
    class_map[transition] = 2
    class_map[high] = 3
    class_map[ignored] = 4
    paths = {
        "low_activity_candidate": out_dir / f"{safe_case}_low_activity.png",
        "transition_candidate": out_dir / f"{safe_case}_transition.png",
        "high_activity_candidate": out_dir / f"{safe_case}_high_activity.png",
    }
    for key, candidate in (
        ("low_activity_candidate", low),
        ("transition_candidate", transition),
        ("high_activity_candidate", high),
    ):
        Image.fromarray(candidate.astype(np.uint8) * 255).save(paths[key])
    ignore_path = out_dir / f"{safe_case}_ignore.png"
    Image.fromarray(ignored.astype(np.uint8) * 255).save(ignore_path)
    class_map_path = out_dir / f"{safe_case}_activity_class_map.png"
    Image.fromarray(class_map).save(class_map_path)
    spectrum = derive_bone_activity_candidates(
        probability=probability_float,
        threshold=threshold,
        bone_gate=gate,
        bone_gate_status=bone_gate_status,
        activity_score_path=activity_score_path,
        activity_class_map_path=str(class_map_path),
        ignore_mask=ignored,
        ignore_sources=ignore_sources,
    )
    for key, path in paths.items():
        spectrum[key]["path"] = str(path)
        spectrum[key]["format"] = "png_binary_mask"
    spectrum["ignore_region"].update(
        {
            "path": str(ignore_path),
            "sha256": _sha256_file(ignore_path),
            "format": "png_binary_mask",
        }
    )
    return spectrum


def _bone_activity_partition(
    *,
    probability: np.ndarray,
    bone_gate: np.ndarray,
    threshold: float,
    ignore_mask: np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    probability_float = np.asarray(probability, dtype=np.float32)
    if probability_float.ndim != 2 or not np.isfinite(probability_float).all():
        raise ValueError("probability must be a finite 2D array")
    probability_float = np.clip(probability_float, 0.0, 1.0)
    gate_float = np.asarray(bone_gate, dtype=np.float32)
    if gate_float.shape != probability_float.shape:
        raise ValueError("bone_gate shape must match probability shape")
    if not np.isfinite(gate_float).all():
        raise ValueError("bone_gate must contain only finite values")
    gate = gate_float > 0
    if ignore_mask is None:
        ignored = np.zeros_like(gate)
    else:
        ignore_float = np.asarray(ignore_mask, dtype=np.float32)
        if ignore_float.shape != probability_float.shape:
            raise ValueError("ignore_mask shape must match probability shape")
        if not np.isfinite(ignore_float).all():
            raise ValueError("ignore_mask must contain only finite values")
        ignored = gate & (ignore_float > 0)
    low_max = float(np.clip(threshold * 0.5, 0.0, 1.0))
    high_min = float(np.clip(threshold, 0.0, 1.0))
    evaluable = gate & ~ignored
    low = evaluable & (probability_float <= low_max)
    high = evaluable & (probability_float >= high_min)
    transition = evaluable & ~low & ~high
    return probability_float, gate, ignored, low, transition, high


def _partition_check(
    *,
    gate: np.ndarray,
    ignored: np.ndarray,
    low: np.ndarray,
    transition: np.ndarray,
    high: np.ndarray,
) -> dict[str, Any]:
    members = (ignored, low, transition, high)
    union = np.logical_or.reduce(members)
    membership_count = np.zeros_like(gate, dtype=np.uint8)
    for member in members:
        membership_count += member.astype(np.uint8)
    overlap_px = int((membership_count > 1).sum())
    outside_gate_px = int((union & ~gate).sum())
    uncovered_gate_px = int((gate & ~union).sum())
    return {
        "valid": overlap_px == 0 and outside_gate_px == 0 and uncovered_gate_px == 0,
        "reviewed_bone_px": int(gate.sum()),
        "classified_px": int((low | transition | high).sum()),
        "ignore_px": int(ignored.sum()),
        "union_px": int(union.sum()),
        "overlap_px": overlap_px,
        "outside_gate_px": outside_gate_px,
        "uncovered_gate_px": uncovered_gate_px,
    }


def _normalized_ignore_sources(value: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if value:
        return [dict(item) for item in value]
    return [
        {
            "source_type": "compatibility_default_empty",
            "path": None,
            "sha256": None,
            "status": "not_provided",
        }
    ]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def risk_from_signal(
    *,
    probability: np.ndarray,
    mask: np.ndarray,
    uncertainty: np.ndarray | None,
) -> np.ndarray:
    probability_float = np.clip(np.asarray(probability, dtype=np.float32), 0.0, 1.0)
    mask_float = (mask > 0).astype(np.float32)
    risk = probability_float * np.maximum(mask_float, 0.35)
    risk *= 0.75
    if uncertainty is not None:
        uncertainty_float = np.clip(np.asarray(uncertainty, dtype=np.float32), 0.0, 1.0)
        risk += (uncertainty_float * np.maximum(mask_float, 0.25)) * 0.25
    return np.clip(risk, 0.0, 1.0, out=risk)


def uncertain_from_signal(
    *,
    probability: np.ndarray,
    uncertainty: np.ndarray | None,
    threshold: float,
) -> np.ndarray:
    if uncertainty is not None:
        return (np.asarray(uncertainty, dtype=np.float32) >= 0.75).astype(np.uint8)
    threshold_float = float(np.clip(threshold, 1e-6, 1.0))
    band = max(0.05, threshold_float * 0.15)
    return (np.abs(np.asarray(probability, dtype=np.float32) - threshold_float) <= band).astype(np.uint8)
