from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from src.core.paths import ensure_dir
from src.core.warnings import DISCLAIMER_TEXT
from src.preprocess.roi import roi_intensity_quantification


def fuse_white_light_fluorescence(
    white_light_path: str | Path,
    fluorescence_path: str | Path,
    output_dir: str | Path,
    *,
    case_id: str | None = None,
    alpha: float = 0.45,
    threshold: float = 0.6,
    colormap: str = "green",
    roi_hints: list[dict[str, Any]] | None = None,
    registration: str = "phase_correlation_translation",
    background_percentile: float = 5.0,
) -> dict[str, Any]:
    """Create pseudo-color fluorescence evidence for the local competition platform."""
    white_path = Path(white_light_path)
    fluor_path = Path(fluorescence_path)
    root = ensure_dir(output_dir)
    safe_case_id = _safe_case_id(case_id or white_path.stem)
    alpha = _clamp(alpha, 0.0, 1.0)
    threshold = _clamp(threshold, 0.0, 1.0)
    background_percentile = _clamp(background_percentile, 0.0, 50.0)

    with Image.open(white_path) as white_image, Image.open(fluor_path) as fluorescence_image:
        white_rgb = white_image.convert("RGB")
        fluorescence_gray = fluorescence_image.convert("L")
        original_fluorescence_size = fluorescence_gray.size
        resized = fluorescence_gray.size != white_rgb.size
        if resized:
            fluorescence_gray = fluorescence_gray.resize(white_rgb.size, _bilinear_resampling())

        white_array = np.asarray(white_rgb, dtype=np.float32)
        fluorescence_array = np.asarray(fluorescence_gray, dtype=np.float32)
        corrected, background_report = subtract_fluorescence_background(
            fluorescence_array, percentile=background_percentile
        )
        registered, registration_report = register_fluorescence_to_reference(
            white_array, corrected, method=registration
        )
        normalized = normalize_fluorescence(registered)
        pseudo_color = apply_fluorescence_colormap(normalized, colormap)
        overlay = np.clip((1.0 - alpha) * white_array + alpha * pseudo_color.astype(np.float32), 0, 255).astype(
            np.uint8
        )
        gray_uint8 = np.clip(normalized * 255.0, 0, 255).astype(np.uint8)
        colorbar = fluorescence_colorbar(colormap=colormap, threshold=threshold)

    overlay_path = root / f"{safe_case_id}_fluorescence_overlay.png"
    heatmap_path = root / f"{safe_case_id}_fluorescence_heatmap.png"
    normalized_path = root / f"{safe_case_id}_fluorescence_normalized.png"
    colorbar_path = root / f"{safe_case_id}_fluorescence_colorbar.png"
    report_path = root / f"{safe_case_id}_fluorescence_fusion.json"
    markdown_report_path = root / f"{safe_case_id}_fluorescence_fusion.md"

    Image.fromarray(overlay).save(overlay_path)
    Image.fromarray(pseudo_color).save(heatmap_path)
    Image.fromarray(gray_uint8).save(normalized_path)
    Image.fromarray(colorbar).save(colorbar_path)

    quantification = fluorescence_quantification(normalized, threshold=threshold)
    roi_quantification = roi_intensity_quantification(normalized, roi_hints, threshold=threshold)
    report = {
        "case_id": safe_case_id,
        "white_light_path": str(white_path),
        "fluorescence_path": str(fluor_path),
        "outputs": {
            "overlay_path": str(overlay_path),
            "heatmap_path": str(heatmap_path),
            "normalized_fluorescence_path": str(normalized_path),
            "colorbar_path": str(colorbar_path),
            "report_path": str(report_path),
            "markdown_report_path": str(markdown_report_path),
        },
        "fusion": {
            "algorithm_version": "fluorescence_fusion_v2",
            "method": "background_corrected_registered_alpha_blend_pseudocolor",
            "alpha": alpha,
            "colormap": colormap,
            "white_light_size": list(white_rgb.size),
            "fluorescence_original_size": list(original_fluorescence_size),
            "fluorescence_resized_to_white_light": resized,
            "registration": registration_report["method"],
            "registration_details": registration_report,
            "background_correction": background_report,
            "colorbar": {"path": str(colorbar_path), "threshold_marker": threshold, "range": [0.0, 1.0]},
        },
        "quantification": {**quantification, **roi_quantification},
        "roi_quantification": roi_quantification,
        "disclaimer": DISCLAIMER_TEXT,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_report_path.write_text(_fluorescence_markdown_report(report), encoding="utf-8")
    return report


def normalize_fluorescence(image: np.ndarray, *, lower_percentile: float = 1.0, upper_percentile: float = 99.0) -> np.ndarray:
    """Robustly normalize a fluorescence intensity image to [0, 1]."""
    array = np.asarray(image, dtype=np.float32)
    finite = array[np.isfinite(array)]
    if finite.size == 0:
        return np.zeros_like(array, dtype=np.float32)
    low = float(np.percentile(finite, lower_percentile))
    high = float(np.percentile(finite, upper_percentile))
    if high <= low:
        low = float(np.min(finite))
        high = float(np.max(finite))
    if high <= low:
        return np.zeros_like(array, dtype=np.float32)
    return np.clip((array - low) / (high - low), 0.0, 1.0).astype(np.float32)


def apply_fluorescence_colormap(normalized: np.ndarray, colormap: str = "green") -> np.ndarray:
    """Map normalized fluorescence intensity to an RGB pseudo-color image."""
    value = np.clip(np.asarray(normalized, dtype=np.float32), 0.0, 1.0)
    zeros = np.zeros_like(value)
    key = colormap.lower().strip()
    if key == "amber":
        channels = [value, value * 0.68, zeros]
    elif key == "magenta":
        channels = [value, zeros, value * 0.88]
    else:
        channels = [zeros, value, value * 0.18]
        key = "green"
    return np.clip(np.stack(channels, axis=-1) * 255.0, 0, 255).astype(np.uint8)


def subtract_fluorescence_background(
    image: np.ndarray,
    *,
    percentile: float = 5.0,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Subtract a low-percentile background floor before normalization."""

    array = np.asarray(image, dtype=np.float32)
    finite = array[np.isfinite(array)]
    if finite.size == 0:
        return np.zeros_like(array, dtype=np.float32), {
            "method": "percentile_floor_subtraction",
            "percentile": float(percentile),
            "baseline": 0.0,
            "applied": False,
        }
    percentile = _clamp(percentile, 0.0, 50.0)
    baseline = float(np.percentile(finite, percentile))
    corrected = np.clip(array - baseline, 0.0, None).astype(np.float32)
    return corrected, {
        "method": "percentile_floor_subtraction",
        "percentile": float(percentile),
        "baseline": round(baseline, 6),
        "applied": baseline > 0,
    }


def register_fluorescence_to_reference(
    reference_rgb: np.ndarray,
    fluorescence_gray: np.ndarray,
    *,
    method: str = "phase_correlation_translation",
    min_response: float = 0.08,
    max_translation_fraction: float = 0.15,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Estimate a small translation between white-light and fluorescence frames."""

    normalized_method = method.lower().strip()
    moving = np.asarray(fluorescence_gray, dtype=np.float32)
    if normalized_method in {"none", "disabled", "resize_only"}:
        return moving, {
            "method": "disabled",
            "applied": False,
            "reason": "registration_disabled",
            "translation_xy": [0.0, 0.0],
            "response": None,
        }
    if normalized_method != "phase_correlation_translation":
        return moving, {
            "method": "unsupported",
            "requested_method": method,
            "applied": False,
            "reason": "unsupported_registration_method",
            "translation_xy": [0.0, 0.0],
            "response": None,
        }
    reference_gray = normalize_fluorescence(_to_grayscale_float(reference_rgb))
    moving_norm = normalize_fluorescence(moving)
    if reference_gray.shape != moving_norm.shape or min(reference_gray.shape) < 8:
        return moving, {
            "method": "phase_correlation_translation",
            "applied": False,
            "reason": "registration_shape_unusable",
            "translation_xy": [0.0, 0.0],
            "response": None,
        }
    try:
        import cv2

        (shift_x, shift_y), response = cv2.phaseCorrelate(reference_gray.astype(np.float32), moving_norm.astype(np.float32))
    except Exception as exc:
        return moving, {
            "method": "phase_correlation_translation",
            "applied": False,
            "reason": f"registration_failed: {exc}",
            "translation_xy": [0.0, 0.0],
            "response": None,
        }
    height, width = moving.shape[:2]
    max_shift = max(1.0, max(width, height) * float(max_translation_fraction))
    shift_x = float(shift_x)
    shift_y = float(shift_y)
    response = float(response)
    can_apply = response >= min_response and abs(shift_x) <= max_shift and abs(shift_y) <= max_shift
    if not can_apply:
        return moving, {
            "method": "phase_correlation_translation",
            "applied": False,
            "reason": "low_response_or_large_shift",
            "translation_xy": [round(shift_x, 4), round(shift_y, 4)],
            "response": round(response, 6),
            "min_response": float(min_response),
            "max_translation_px": round(max_shift, 4),
        }
    matrix = np.array([[1.0, 0.0, -shift_x], [0.0, 1.0, -shift_y]], dtype=np.float32)
    registered = cv2.warpAffine(
        moving,
        matrix,
        (width, height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return registered.astype(np.float32), {
        "method": "phase_correlation_translation",
        "applied": True,
        "reason": "phase_correlation_response_met",
        "translation_xy": [round(shift_x, 4), round(shift_y, 4)],
        "response": round(response, 6),
        "min_response": float(min_response),
        "max_translation_px": round(max_shift, 4),
    }


def fluorescence_colorbar(*, colormap: str = "green", threshold: float = 0.6, width: int = 256, height: int = 28) -> np.ndarray:
    """Create a compact pseudo-color scale with a threshold marker."""

    safe_width = max(32, int(width))
    safe_height = max(12, int(height))
    gradient = np.tile(np.linspace(0.0, 1.0, safe_width, dtype=np.float32), (safe_height, 1))
    bar = apply_fluorescence_colormap(gradient, colormap)
    marker_x = int(round(_clamp(threshold, 0.0, 1.0) * (safe_width - 1)))
    x0 = max(0, marker_x - 1)
    x1 = min(safe_width, marker_x + 2)
    bar[:, x0:x1, :] = 255
    bar[0:2, :, :] = 0
    bar[-2:, :, :] = 0
    bar[:, 0:2, :] = 0
    bar[:, -2:, :] = 0
    return bar.astype(np.uint8)


def fluorescence_quantification(normalized: np.ndarray, *, threshold: float = 0.6) -> dict[str, Any]:
    value = np.clip(np.asarray(normalized, dtype=np.float32), 0.0, 1.0)
    positive = value >= threshold
    return {
        "threshold": float(threshold),
        "mean_intensity": round(float(np.mean(value)), 6),
        "max_intensity": round(float(np.max(value)), 6),
        "p95_intensity": round(float(np.percentile(value, 95)), 6),
        "positive_area_px": int(np.count_nonzero(positive)),
        "positive_area_fraction": round(float(np.mean(positive)), 6),
        "source": "normalized_fluorescence",
    }


def enhance_fluorescence_signal(
    image: np.ndarray,
    *,
    threshold: float = 0.6,
    colormap: str = "green",
    denoise_kernel: int = 5,
    clahe_clip_limit: float = 2.0,
) -> dict[str, Any]:
    """Denoise, contrast-normalize, pseudo-color, and quantify a fluorescence frame."""

    gray = _to_grayscale_float(image)
    denoised = _denoise_gray(gray, kernel_size=denoise_kernel)
    normalized = normalize_fluorescence(denoised)
    enhanced = _clahe_normalized(normalized, clip_limit=clahe_clip_limit)
    pseudo_color = apply_fluorescence_colormap(enhanced, colormap)
    enhanced_uint8 = np.clip(enhanced * 255.0, 0, 255).astype(np.uint8)
    return {
        "normalized": normalized,
        "enhanced": enhanced,
        "enhanced_uint8": enhanced_uint8,
        "pseudo_color": pseudo_color,
        "quantification": {
            **fluorescence_quantification(enhanced, threshold=threshold),
            "source": "ofdvdnet_fluorescence_baseline",
            "denoise_kernel": int(denoise_kernel),
            "contrast_method": "clahe_after_percentile_normalization",
        },
    }


def blend_pseudocolor_on_reference(
    reference_image: np.ndarray,
    pseudo_color_rgb: np.ndarray,
    *,
    alpha: float = 0.45,
) -> np.ndarray:
    reference = _as_rgb(reference_image).astype(np.float32)
    pseudo = _as_rgb(pseudo_color_rgb).astype(np.float32)
    if pseudo.shape[:2] != reference.shape[:2]:
        pseudo = np.asarray(Image.fromarray(pseudo.astype(np.uint8)).resize(reference.shape[1::-1], _bilinear_resampling()))
    alpha = _clamp(alpha, 0.0, 1.0)
    return np.clip((1.0 - alpha) * reference + alpha * pseudo, 0, 255).astype(np.uint8)


def _safe_case_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return cleaned or "case"


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, float(value)))


def _bilinear_resampling() -> int:
    return getattr(Image, "Resampling", Image).BILINEAR


def _to_grayscale_float(image: np.ndarray) -> np.ndarray:
    array = np.asarray(image)
    if array.ndim == 2:
        return array.astype(np.float32, copy=False)
    if array.ndim != 3 or array.shape[2] < 3:
        raise ValueError(f"Fluorescence image must be 2D or 3-channel, got shape {array.shape}")
    rgb = _as_rgb(array).astype(np.float32)
    return 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]


def _as_rgb(image: np.ndarray) -> np.ndarray:
    array = np.asarray(image)
    if array.ndim == 2:
        return np.stack([array, array, array], axis=-1).astype(np.uint8)
    if array.ndim == 3 and array.shape[2] >= 3:
        return array[..., :3].astype(np.uint8, copy=False)
    raise ValueError(f"Image must be 2D or 3-channel, got shape {array.shape}")


def _denoise_gray(gray: np.ndarray, *, kernel_size: int) -> np.ndarray:
    if kernel_size <= 1:
        return gray.astype(np.float32, copy=False)
    kernel = kernel_size if kernel_size % 2 == 1 else kernel_size + 1
    try:
        import cv2

        return cv2.GaussianBlur(gray.astype(np.float32), (kernel, kernel), 0)
    except Exception:
        return gray.astype(np.float32, copy=False)


def _clahe_normalized(normalized: np.ndarray, *, clip_limit: float) -> np.ndarray:
    source = np.clip(normalized * 255.0, 0, 255).astype(np.uint8)
    try:
        import cv2

        enhanced = cv2.createCLAHE(clipLimit=float(clip_limit), tileGridSize=(8, 8)).apply(source)
    except Exception:
        enhanced = source
    return normalize_fluorescence(enhanced)


def _fluorescence_markdown_report(report: dict[str, Any]) -> str:
    quantification = report.get("quantification", {})
    outputs = report.get("outputs", {})
    fusion = report.get("fusion", {})
    lines = [
        "# Fluorescence Fusion Report",
        "",
        "## Summary",
        "",
        f"- Case ID: `{report.get('case_id')}`",
        f"- Method: `{fusion.get('method')}`",
        f"- Alpha: `{fusion.get('alpha')}`",
        f"- Colormap: `{fusion.get('colormap')}`",
        f"- Registration: `{fusion.get('registration')}`",
        f"- Registration applied: `{fusion.get('registration_details', {}).get('applied')}`",
        f"- Background correction: `{fusion.get('background_correction', {}).get('method')}`",
        "",
        "## Quantification",
        "",
        f"- Threshold: `{quantification.get('threshold')}`",
        f"- Mean intensity: `{quantification.get('mean_intensity')}`",
        f"- Max intensity: `{quantification.get('max_intensity')}`",
        f"- P95 intensity: `{quantification.get('p95_intensity')}`",
        f"- Positive area px: `{quantification.get('positive_area_px')}`",
        f"- Positive area fraction: `{quantification.get('positive_area_fraction')}`",
        "",
        "## Outputs",
        "",
        f"- Overlay: `{outputs.get('overlay_path')}`",
        f"- Heatmap: `{outputs.get('heatmap_path')}`",
        f"- Normalized fluorescence: `{outputs.get('normalized_fluorescence_path')}`",
        f"- Colorbar: `{outputs.get('colorbar_path')}`",
        f"- JSON report: `{outputs.get('report_path')}`",
        "",
        "## Disclaimer",
        "",
        str(report.get("disclaimer") or DISCLAIMER_TEXT),
        "",
    ]
    return "\n".join(lines)
