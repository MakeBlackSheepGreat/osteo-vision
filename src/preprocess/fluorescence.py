from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from src.core.paths import ensure_dir
from src.core.warnings import DISCLAIMER_TEXT


def fuse_white_light_fluorescence(
    white_light_path: str | Path,
    fluorescence_path: str | Path,
    output_dir: str | Path,
    *,
    case_id: str | None = None,
    alpha: float = 0.45,
    threshold: float = 0.6,
    colormap: str = "green",
) -> dict[str, Any]:
    """Create a basic pseudo-color fluorescence overlay for offline demos."""
    white_path = Path(white_light_path)
    fluor_path = Path(fluorescence_path)
    root = ensure_dir(output_dir)
    safe_case_id = _safe_case_id(case_id or white_path.stem)
    alpha = _clamp(alpha, 0.0, 1.0)
    threshold = _clamp(threshold, 0.0, 1.0)

    with Image.open(white_path) as white_image, Image.open(fluor_path) as fluorescence_image:
        white_rgb = white_image.convert("RGB")
        fluorescence_gray = fluorescence_image.convert("L")
        original_fluorescence_size = fluorescence_gray.size
        resized = fluorescence_gray.size != white_rgb.size
        if resized:
            fluorescence_gray = fluorescence_gray.resize(white_rgb.size, _bilinear_resampling())

        white_array = np.asarray(white_rgb, dtype=np.float32)
        fluorescence_array = np.asarray(fluorescence_gray, dtype=np.float32)
        normalized = normalize_fluorescence(fluorescence_array)
        pseudo_color = apply_fluorescence_colormap(normalized, colormap)
        overlay = np.clip((1.0 - alpha) * white_array + alpha * pseudo_color.astype(np.float32), 0, 255).astype(
            np.uint8
        )
        gray_uint8 = np.clip(normalized * 255.0, 0, 255).astype(np.uint8)

    overlay_path = root / f"{safe_case_id}_fluorescence_overlay.png"
    heatmap_path = root / f"{safe_case_id}_fluorescence_heatmap.png"
    normalized_path = root / f"{safe_case_id}_fluorescence_normalized.png"
    report_path = root / f"{safe_case_id}_fluorescence_fusion.json"
    markdown_report_path = root / f"{safe_case_id}_fluorescence_fusion.md"

    Image.fromarray(overlay).save(overlay_path)
    Image.fromarray(pseudo_color).save(heatmap_path)
    Image.fromarray(gray_uint8).save(normalized_path)

    report = {
        "case_id": safe_case_id,
        "white_light_path": str(white_path),
        "fluorescence_path": str(fluor_path),
        "outputs": {
            "overlay_path": str(overlay_path),
            "heatmap_path": str(heatmap_path),
            "normalized_fluorescence_path": str(normalized_path),
            "report_path": str(report_path),
            "markdown_report_path": str(markdown_report_path),
        },
        "fusion": {
            "method": "alpha_blend_pseudocolor",
            "alpha": alpha,
            "colormap": colormap,
            "white_light_size": list(white_rgb.size),
            "fluorescence_original_size": list(original_fluorescence_size),
            "fluorescence_resized_to_white_light": resized,
            "registration": "resize_only_initial_demo",
        },
        "quantification": fluorescence_quantification(normalized, threshold=threshold),
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


def _safe_case_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return cleaned or "case"


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, float(value)))


def _bilinear_resampling() -> int:
    return getattr(Image, "Resampling", Image).BILINEAR


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
        f"- JSON report: `{outputs.get('report_path')}`",
        "",
        "## Disclaimer",
        "",
        str(report.get("disclaimer") or DISCLAIMER_TEXT),
        "",
    ]
    return "\n".join(lines)
