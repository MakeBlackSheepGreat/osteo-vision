from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

from osteo_vision_core.core.paths import ensure_dir


def assess_three_channel_quality(
    white_light_path: str | Path,
    fluorescence_path: str | Path,
    device_overlay_path: str | Path | None,
    output_dir: str | Path,
    *,
    metadata: dict[str, dict[str, Any]] | None = None,
    software_overlay_path: str | Path | None = None,
    synchronization_tolerance_ms: float = 100.0,
) -> dict[str, Any]:
    """Produce offline three-channel engineering QC evidence.

    The device overlay remains display-only evidence. Pixel differences never
    affect model inference or clinical candidate boundaries.
    """

    root = ensure_dir(output_dir)
    meta = metadata or {}
    white = _rgb(white_light_path)
    fluorescence = _rgb(fluorescence_path)
    overlay = _rgb(device_overlay_path) if device_overlay_path else None
    synchronization = _synchronization(meta, synchronization_tolerance_ms)
    geometry = _geometry(white, fluorescence, overlay)
    comparison = _overlay_comparison(
        overlay,
        software_overlay_path,
        root,
        geometry_usable=geometry["pixel_comparison_allowed"],
    )
    statuses = [synchronization["status"], geometry["status"]]
    if overlay is not None:
        statuses.append(comparison["status"])
    overall_status = "pass" if statuses and all(item == "pass" for item in statuses) else "review_required"
    report = {
        "schema_version": "three_channel_quality_v1",
        "overall": {
            "status": overall_status,
            "analysis_allowed": True,
            "model_input_channels": ["white_light", "fluorescence"],
            "device_overlay_used_for_inference": False,
            "medical_boundary": "Offline engineering QC only; device-overlay differences do not define disease or resection boundaries.",
        },
        "synchronization": synchronization,
        "geometry": geometry,
        "overlay_comparison": comparison,
    }
    report_path = root / "three_channel_quality.json"
    report["report_path"] = str(report_path)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _rgb(path: str | Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.uint8)


def _synchronization(metadata: dict[str, dict[str, Any]], tolerance_ms: float) -> dict[str, Any]:
    values = {
        channel: _timestamp_ms(metadata.get(channel, {}))
        for channel in ("white_light", "fluorescence", "device_overlay")
    }
    white, fluor, overlay = values.values()
    reasons: list[str] = []
    if white is None or fluor is None:
        reasons.append("white_light_or_fluorescence_timestamp_missing")
    white_fluor_delta = abs(white - fluor) if white is not None and fluor is not None else None
    overlay_delta = abs(overlay - white) if overlay is not None and white is not None else None
    if white_fluor_delta is not None and white_fluor_delta > tolerance_ms:
        reasons.append("white_light_fluorescence_time_offset_exceeds_tolerance")
    if overlay is not None and overlay_delta is not None and overlay_delta > tolerance_ms:
        reasons.append("device_overlay_time_offset_exceeds_tolerance")
    status = "pass" if not reasons else "review_required"
    return {
        "status": status,
        "source": "offline_input_metadata",
        "timestamps_ms": values,
        "white_fluorescence_delta_ms": _rounded(white_fluor_delta),
        "device_overlay_white_delta_ms": _rounded(overlay_delta),
        "tolerance_ms": float(tolerance_ms),
        "reasons": reasons,
    }


def _timestamp_ms(metadata: dict[str, Any]) -> float | None:
    for key in ("capture_timestamp_ms", "timestamp_ms", "frame_timestamp_ms"):
        value = metadata.get(key)
        try:
            if value is not None:
                return float(value)
        except (TypeError, ValueError):
            pass
    for key in ("capture_timestamp", "timestamp", "frame_timestamp", "acquired_at"):
        value = metadata.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            return datetime.fromisoformat(value.strip().replace("Z", "+00:00")).timestamp() * 1000.0
        except ValueError:
            continue
    return None


def _geometry(white: np.ndarray, fluorescence: np.ndarray, overlay: np.ndarray | None) -> dict[str, Any]:
    dimensions = {
        "white_light": [int(white.shape[1]), int(white.shape[0])],
        "fluorescence": [int(fluorescence.shape[1]), int(fluorescence.shape[0])],
        "device_overlay": [int(overlay.shape[1]), int(overlay.shape[0])] if overlay is not None else None,
    }
    white_ratio = white.shape[1] / max(1, white.shape[0])
    ratio_deltas = {
        "fluorescence": abs(fluorescence.shape[1] / max(1, fluorescence.shape[0]) - white_ratio) / white_ratio,
        "device_overlay": (
            abs(overlay.shape[1] / max(1, overlay.shape[0]) - white_ratio) / white_ratio
            if overlay is not None
            else None
        ),
    }
    reasons = [
        name + "_aspect_ratio_mismatch" for name, value in ratio_deltas.items() if value is not None and value > 0.02
    ]
    allowed = not reasons
    return {
        "status": "pass" if allowed else "review_required",
        "dimensions": dimensions,
        "aspect_ratio_relative_delta": {key: _rounded(value, 6) for key, value in ratio_deltas.items()},
        "pixel_comparison_allowed": allowed,
        "reasons": reasons,
    }


def _overlay_comparison(
    device_overlay: np.ndarray | None,
    software_overlay_path: str | Path | None,
    root: Path,
    *,
    geometry_usable: bool,
) -> dict[str, Any]:
    boundary = "Display-consistency evidence only; metrics are excluded from model inference and clinical decisions."
    if device_overlay is None or not software_overlay_path:
        return {
            "available": False,
            "status": "unavailable",
            "reason": "device_or_software_overlay_missing",
            "boundary": boundary,
        }
    if not geometry_usable:
        return {"available": False, "status": "review_required", "reason": "geometry_unusable", "boundary": boundary}
    software = _rgb(software_overlay_path)
    if device_overlay.shape[:2] != software.shape[:2]:
        device_overlay = cv2.resize(
            device_overlay, (software.shape[1], software.shape[0]), interpolation=cv2.INTER_LINEAR
        )
    device_float = device_overlay.astype(np.float32) / 255.0
    software_float = software.astype(np.float32) / 255.0
    difference = np.abs(device_float - software_float)
    mae = float(np.mean(difference))
    rmse = float(np.sqrt(np.mean(np.square(device_float - software_float))))
    device_gray = cv2.cvtColor(device_overlay, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    software_gray = cv2.cvtColor(software, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    ssim = _global_ssim(device_gray, software_gray)
    device_edges = cv2.Canny((device_gray * 255).astype(np.uint8), 50, 150) > 0
    software_edges = cv2.Canny((software_gray * 255).astype(np.uint8), 50, 150) > 0
    edge_disagreement = float(np.mean(np.logical_xor(device_edges, software_edges)))
    heat = np.clip(np.mean(difference, axis=2) * 255.0 * 2.0, 0, 255).astype(np.uint8)
    heatmap = cv2.applyColorMap(heat, cv2.COLORMAP_TURBO)
    heatmap_path = root / "device_software_overlay_difference.png"
    cv2.imwrite(str(heatmap_path), heatmap)
    return {
        "available": True,
        "status": "pass" if mae <= 0.25 and ssim >= 0.35 else "review_required",
        "difference_heatmap_path": str(heatmap_path),
        "mae_rgb": _rounded(mae, 6),
        "rmse_rgb": _rounded(rmse, 6),
        "ssim_luma": _rounded(ssim, 6),
        "edge_disagreement": _rounded(edge_disagreement, 6),
        "thresholds": {"mae_rgb_max": 0.25, "ssim_luma_min": 0.35},
        "boundary": boundary,
    }


def _global_ssim(left: np.ndarray, right: np.ndarray) -> float:
    c1, c2 = 0.01**2, 0.03**2
    mu_l, mu_r = float(left.mean()), float(right.mean())
    var_l, var_r = float(left.var()), float(right.var())
    covariance = float(np.mean((left - mu_l) * (right - mu_r)))
    denominator = (mu_l**2 + mu_r**2 + c1) * (var_l + var_r + c2)
    return float(((2 * mu_l * mu_r + c1) * (2 * covariance + c2)) / denominator) if denominator else 1.0


def _rounded(value: float | None, digits: int = 3) -> float | None:
    return round(float(value), digits) if value is not None else None
