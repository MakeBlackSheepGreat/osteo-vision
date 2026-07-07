from __future__ import annotations

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
    Image.fromarray(np.clip(risk * 255.0, 0, 255).astype(np.uint8)).save(risk_path)
    Image.fromarray((uncertain * 255).astype(np.uint8)).save(uncertain_mask_path)
    return {
        "risk_mask_path": str(risk_path),
        "uncertain_mask_path": str(uncertain_mask_path),
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
) -> dict[str, Any]:
    return {
        "schema_version": "osteo-vision-video-signal-masks-v1",
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
        "medical_boundary": VIDEO_SIGNAL_MEDICAL_BOUNDARY,
    }


def risk_from_signal(
    *,
    probability: np.ndarray,
    mask: np.ndarray,
    uncertainty: np.ndarray | None,
) -> np.ndarray:
    probability_float = np.clip(probability.astype(np.float32), 0.0, 1.0)
    mask_float = (mask > 0).astype(np.float32)
    if uncertainty is None:
        uncertainty_float = np.zeros_like(probability_float, dtype=np.float32)
    else:
        uncertainty_float = np.clip(uncertainty.astype(np.float32), 0.0, 1.0)
    signal_risk = probability_float * np.maximum(mask_float, 0.35)
    uncertainty_risk = uncertainty_float * np.maximum(mask_float, 0.25)
    return np.clip(0.75 * signal_risk + 0.25 * uncertainty_risk, 0.0, 1.0).astype(np.float32)


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
