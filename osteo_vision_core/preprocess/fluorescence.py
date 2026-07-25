from __future__ import annotations

import json
import re
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
from PIL import Image

from osteo_vision_core.core.paths import ensure_dir
from osteo_vision_core.core.warnings import DISCLAIMER_TEXT
from osteo_vision_core.preprocess.accelerated_fusion import (
    accelerated_normalize_pseudocolor_blend,
    register_adaptive_multiscale,
)
from osteo_vision_core.preprocess.roi import normalized_rects_from_hints, roi_intensity_quantification


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
    registration: str = "adaptive_multiscale",
    background_percentile: float = 5.0,
    prefer_gpu: bool = True,
) -> dict[str, Any]:
    """Create pseudo-color fluorescence evidence for the local competition platform."""
    white_path = Path(white_light_path)
    fluor_path = Path(fluorescence_path)
    root = ensure_dir(output_dir)
    safe_case_id = _safe_case_id(case_id or white_path.stem)
    alpha = _clamp(alpha, 0.0, 1.0)
    threshold = _clamp(threshold, 0.0, 1.0)
    background_percentile = _clamp(background_percentile, 0.0, 50.0)

    total_started = perf_counter()
    with Image.open(white_path) as white_image, Image.open(fluor_path) as fluorescence_image:
        decode_started = perf_counter()
        white_rgb = white_image.convert("RGB")
        fluorescence_gray = fluorescence_image.convert("L")
        original_fluorescence_size = fluorescence_gray.size
        resized = fluorescence_gray.size != white_rgb.size
        if resized:
            fluorescence_gray = fluorescence_gray.resize(white_rgb.size, _bilinear_resampling())

        white_array = np.asarray(white_rgb, dtype=np.uint8)
        fluorescence_array = np.asarray(fluorescence_gray, dtype=np.float32)
        decode_ms = (perf_counter() - decode_started) * 1000.0
        preprocess_started = perf_counter()
        corrected, background_report = subtract_fluorescence_background(
            fluorescence_array, percentile=background_percentile
        )
        preprocess_ms = (perf_counter() - preprocess_started) * 1000.0
        registration_started = perf_counter()
        registered, registration_report = register_fluorescence_to_reference(
            white_array,
            corrected,
            method=registration,
            prefer_gpu=prefer_gpu,
        )
        registration_ms = (perf_counter() - registration_started) * 1000.0
        fusion_started = perf_counter()
        normalized, pseudo_color, overlay, acceleration_report = accelerated_normalize_pseudocolor_blend(
            white_array,
            registered,
            alpha=alpha,
            colormap=colormap,
            prefer_gpu=prefer_gpu,
        )
        gray_uint8 = np.clip(normalized * 255.0, 0, 255).astype(np.uint8)
        colorbar = fluorescence_colorbar(colormap=colormap, threshold=threshold)
        fusion_ms = (perf_counter() - fusion_started) * 1000.0

    overlay_path = root / f"{safe_case_id}_fluorescence_overlay.png"
    heatmap_path = root / f"{safe_case_id}_fluorescence_heatmap.png"
    normalized_path = root / f"{safe_case_id}_fluorescence_normalized.png"
    colorbar_path = root / f"{safe_case_id}_fluorescence_colorbar.png"
    report_path = root / f"{safe_case_id}_fluorescence_fusion.json"
    markdown_report_path = root / f"{safe_case_id}_fluorescence_fusion.md"

    encoding_started = perf_counter()
    Image.fromarray(overlay).save(overlay_path, compress_level=1)
    Image.fromarray(pseudo_color).save(heatmap_path, compress_level=1)
    Image.fromarray(gray_uint8).save(normalized_path, compress_level=1)
    Image.fromarray(colorbar).save(colorbar_path, compress_level=1)
    encoding_ms = (perf_counter() - encoding_started) * 1000.0

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
            "acceleration": acceleration_report,
            "performance": {
                "decode_resize_ms": round(decode_ms, 3),
                "background_correction_ms": round(preprocess_ms, 3),
                "registration_ms": round(registration_ms, 3),
                "normalization_pseudocolor_blend_ms": round(fusion_ms, 3),
                "evidence_encoding_ms": round(encoding_ms, 3),
                "total_ms": round((perf_counter() - total_started) * 1000.0, 3),
                "source_size": [int(white_array.shape[1]), int(white_array.shape[0])],
            },
            "colorbar": {"path": str(colorbar_path), "threshold_marker": threshold, "range": [0.0, 1.0]},
        },
        "quantification": {**quantification, **roi_quantification},
        "roi_quantification": roi_quantification,
        "disclaimer": DISCLAIMER_TEXT,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_report_path.write_text(_fluorescence_markdown_report(report), encoding="utf-8")
    return report


def normalize_fluorescence(
    image: np.ndarray, *, lower_percentile: float = 1.0, upper_percentile: float = 99.0
) -> np.ndarray:
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
    prefer_gpu: bool = True,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Estimate a small translation between white-light and fluorescence frames."""

    normalized_method = method.lower().strip()
    moving = np.asarray(fluorescence_gray, dtype=np.float32)
    if normalized_method in {
        "adaptive_multiscale",
        "adaptive_multiscale_registration_v1",
        "adaptive_multiscale_registration_v2",
    }:
        return register_adaptive_multiscale(
            reference_rgb,
            moving,
            min_response=min_response,
            max_translation_fraction=max_translation_fraction,
            prefer_gpu=prefer_gpu,
            return_device_tensor=prefer_gpu,
        )
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

        (shift_x, shift_y), response = cv2.phaseCorrelate(
            reference_gray.astype(np.float32), moving_norm.astype(np.float32)
        )
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


def fluorescence_colorbar(
    *, colormap: str = "green", threshold: float = 0.6, width: int = 256, height: int = 28
) -> np.ndarray:
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


def decoded_frame_fluorescence_quantification(
    image_or_path: np.ndarray | str | Path,
    *,
    roi_hints: list[dict[str, Any]] | None = None,
    background_percentile: float = 5.0,
) -> dict[str, Any]:
    """Measure decoded-frame luminance without using segmentation probabilities."""

    if isinstance(image_or_path, (str, Path)):
        source_path = Path(image_or_path)
        with Image.open(source_path) as image:
            gray = np.asarray(image.convert("L"), dtype=np.float32) / 255.0
    else:
        source_path = None
        gray = _decoded_intensity_unit_range(np.asarray(image_or_path))

    finite_mask = np.isfinite(gray)
    finite_values = gray[finite_mask]
    if finite_values.size == 0:
        return {
            "available": False,
            "reason": "decoded_frame_has_no_finite_pixels",
            "source": "decoded_keyframe_intensity",
            "source_path": str(source_path) if source_path else None,
        }

    signal_rects, background_rects = _split_signal_and_background_rects(roi_hints)
    signal_mask = _rect_union_mask(gray.shape, signal_rects)
    background_mask = _rect_union_mask(gray.shape, background_rects)
    signal_values = gray[signal_mask & finite_mask] if signal_mask.any() else finite_values
    if background_mask.any():
        background_values = gray[background_mask & finite_mask]
        background_method = "explicit_background_roi_median"
        background = float(np.median(background_values)) if background_values.size else 0.0
    else:
        outside_signal = finite_values if not signal_mask.any() else gray[(~signal_mask) & finite_mask]
        background_values = outside_signal if outside_signal.size else finite_values
        percentile = _clamp(background_percentile, 0.0, 50.0)
        background_method = "outside_signal_roi_low_percentile" if signal_mask.any() else "whole_frame_low_percentile"
        background = float(np.percentile(background_values, percentile))

    if signal_values.size == 0:
        signal_values = finite_values
    return {
        "available": True,
        "schema_version": "osteo-vision-decoded-frame-intensity-v1",
        "source": "decoded_keyframe_intensity",
        "source_path": str(source_path) if source_path else None,
        "intensity_domain": "decoded_8bit_luminance_unit_range",
        "intensity_source_boundary": (
            "Decoded MP4/JPEG keyframe luminance is used as the fluorescence-channel signal proxy; "
            "raw NIR sensor values remain required for calibrated device-level quantification."
        ),
        "roi_applied": bool(signal_mask.any()),
        "signal_roi_count": len(signal_rects),
        "background_roi_count": len(background_rects),
        "signal_pixel_count": int(signal_values.size),
        "background_pixel_count": int(background_values.size),
        "mean_intensity": round(float(np.mean(signal_values)), 6),
        "max_intensity": round(float(np.max(signal_values)), 6),
        "p95_intensity": round(float(np.percentile(signal_values, 95)), 6),
        "background_intensity": round(background, 6),
        "background_method": background_method,
        "background_percentile": (None if background_mask.any() else float(_clamp(background_percentile, 0.0, 50.0))),
    }


def fluorescence_time_intensity_curve(
    frame_quantifications: list[dict[str, Any]],
    *,
    time_key: str = "timestamp_sec",
    intensity_key: str = "p95_intensity",
    background_key: str = "background_intensity",
) -> dict[str, Any]:
    """Summarize a background-corrected, normalized keyframe intensity curve."""

    points: list[tuple[float, float, float]] = []
    invalid_timestamp_count = 0
    invalid_intensity_count = 0
    for item in frame_quantifications:
        timestamp = _finite_float(item.get(time_key), fallback=None)
        intensity = _finite_float(item.get(intensity_key), fallback=None)
        if timestamp is None:
            invalid_timestamp_count += 1
            continue
        if intensity is None:
            invalid_intensity_count += 1
            continue
        background = _finite_float(item.get(background_key), fallback=0.0) or 0.0
        points.append((timestamp, intensity, background))
    points.sort(key=lambda point: point[0])
    distinct_timestamp_count = len({point[0] for point in points})
    if len(points) < 2 or distinct_timestamp_count < 2:
        return {
            "available": False,
            "reason": "at_least_two_distinct_timestamped_keyframes_required",
            "point_count": len(points),
            "distinct_timestamp_count": distinct_timestamp_count,
            "curve_quality": {
                "invalid_timestamp_count": invalid_timestamp_count,
                "invalid_intensity_count": invalid_intensity_count,
                "duplicate_timestamp_count": max(0, len(points) - distinct_timestamp_count),
            },
            "medical_boundary": "Keyframe curve is an engineering perfusion reference requiring physician review.",
        }

    times = np.asarray([point[0] for point in points], dtype=np.float64)
    corrected = np.maximum(
        np.asarray([point[1] for point in points], dtype=np.float64)
        - np.asarray([point[2] for point in points], dtype=np.float64),
        0.0,
    )
    baseline = float(corrected[0])
    peak = float(np.max(corrected))
    dynamic_range = peak - baseline
    normalized = (
        np.clip((corrected - baseline) / dynamic_range, 0.0, 1.0) if dynamic_range > 1e-8 else np.zeros_like(corrected)
    )
    peak_index = int(np.argmax(corrected))
    relative_times = times - times[0]
    slopes = np.divide(
        np.diff(normalized),
        np.diff(relative_times),
        out=np.zeros(len(normalized) - 1, dtype=np.float64),
        where=np.diff(relative_times) > 0,
    )
    duplicate_timestamps = int(len(times) - len(np.unique(times)))
    return {
        "available": True,
        "schema_version": "osteo-vision-keyframe-tic-v1",
        "point_count": len(points),
        "source_intensity_key": intensity_key,
        "background_correction": "per_frame_background_subtraction",
        "normalization": "baseline_to_peak_unit_range",
        "motion_compensation": "keyframe_selection_and_existing_registration_only",
        "baseline_corrected_intensity": round(baseline, 6),
        "peak_corrected_intensity": round(peak, 6),
        "time_to_peak_sec": round(float(relative_times[peak_index]), 6),
        "max_normalized_rise_slope_per_sec": round(float(np.max(slopes)) if slopes.size else 0.0, 6),
        "normalized_auc": round(float(np.trapezoid(normalized, relative_times)), 6),
        "duration_sec": round(float(relative_times[-1]), 6),
        "curve_quality": {
            "invalid_timestamp_count": invalid_timestamp_count,
            "invalid_intensity_count": invalid_intensity_count,
            "duplicate_timestamp_count": duplicate_timestamps,
            "strictly_increasing_time": bool(np.all(np.diff(times) > 0)),
            "dynamic_range_nonzero": bool(dynamic_range > 1e-8),
            "sparse_keyframe_curve": True,
            "quality_status": "usable" if dynamic_range > 1e-8 and duplicate_timestamps == 0 else "limited",
        },
        "points": [
            {
                "timestamp_sec": round(float(timestamp), 6),
                "relative_time_sec": round(float(timestamp - times[0]), 6),
                "raw_intensity": round(float(intensity), 6),
                "background_intensity": round(float(background), 6),
                "corrected_intensity": round(float(value), 6),
                "normalized_intensity": round(float(norm), 6),
            }
            for (timestamp, intensity, background), value, norm in zip(points, corrected, normalized)
        ],
        "medical_boundary": (
            "Sparse keyframe time-intensity metrics are engineering perfusion references; locked acquisition and "
            "injection protocols plus physician review are required for cross-case interpretation."
        ),
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
    reference: np.ndarray = _as_rgb(reference_image).astype(np.float32)
    pseudo: np.ndarray = _as_rgb(pseudo_color_rgb).astype(np.float32)
    if pseudo.shape[:2] != reference.shape[:2]:
        pseudo = np.asarray(
            Image.fromarray(pseudo.astype(np.uint8)).resize(reference.shape[1::-1], _bilinear_resampling())
        )
    alpha = _clamp(alpha, 0.0, 1.0)
    return np.clip((1.0 - alpha) * reference + alpha * pseudo, 0, 255).astype(np.uint8)


def _safe_case_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return cleaned or "case"


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, float(value)))


def _finite_float(value: Any, *, fallback: float | None) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if np.isfinite(parsed) else fallback


def _decoded_intensity_unit_range(image: np.ndarray) -> np.ndarray:
    gray = _to_grayscale_float(image).astype(np.float32, copy=False)
    finite = gray[np.isfinite(gray)]
    if finite.size == 0:
        return gray
    if np.issubdtype(np.asarray(image).dtype, np.integer):
        maximum = float(np.iinfo(np.asarray(image).dtype).max)
    else:
        maximum = 1.0 if float(np.max(finite)) <= 1.0 else 255.0
    return np.clip(gray / max(maximum, 1.0), 0.0, 1.0).astype(np.float32)


def _split_signal_and_background_rects(
    roi_hints: list[dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    signal: list[dict[str, Any]] = []
    background: list[dict[str, Any]] = []
    for rect in normalized_rects_from_hints(roi_hints):
        label = str(rect.get("label") or "").strip().lower()
        if "background" in label or "背景" in label:
            background.append(rect)
        else:
            signal.append(rect)
    return signal, background


def _rect_union_mask(shape: tuple[int, ...], rects: list[dict[str, Any]]) -> np.ndarray:
    height, width = shape[:2]
    mask = np.zeros((height, width), dtype=bool)
    for rect in rects:
        x0 = max(0, min(width, int(np.floor(float(rect["x"]) * width))))
        y0 = max(0, min(height, int(np.floor(float(rect["y"]) * height))))
        x1 = max(0, min(width, int(np.ceil((float(rect["x"]) + float(rect["width"])) * width))))
        y1 = max(0, min(height, int(np.ceil((float(rect["y"]) + float(rect["height"])) * height))))
        if x1 > x0 and y1 > y0:
            mask[y0:y1, x0:x1] = True
    return mask


def _bilinear_resampling() -> int:
    return getattr(Image, "Resampling", Image).BILINEAR


def _to_grayscale_float(image: np.ndarray) -> np.ndarray:
    array = np.asarray(image)
    if array.ndim == 2:
        return array.astype(np.float32, copy=False)
    if array.ndim != 3 or array.shape[2] < 3:
        raise ValueError(f"Fluorescence image must be 2D or 3-channel, got shape {array.shape}")
    rgb: np.ndarray = _as_rgb(array).astype(np.float32)
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
