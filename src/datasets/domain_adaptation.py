from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Sequence, cast

import cv2
import numpy as np
import torch
import yaml

DEFAULT_DOMAIN_ADAPTATION_CONFIG: dict[str, Any] = {
    "enabled": False,
    "sampling": {
        "domain_tier_weights": {"target": 4.0, "near_target": 2.0, "proxy": 1.0, "synthetic": 0.75},
        "review_state_weights": {"accepted": 2.0, "modified": 2.5, "review_required": 0.75, "rejected": 0.25},
        "balance_source_groups": True,
    },
    "augmentation": {
        "probability": 0.8,
        "exposure_gain": [0.75, 1.35],
        "gamma": [0.7, 1.5],
        "channel_gain": [0.85, 1.15],
        "gaussian_noise_std": [0.0, 10.0],
        "blur_probability": 0.25,
        "blur_kernel_choices": [3, 5],
        "specular_probability": 0.25,
        "occlusion_probability": 0.2,
        "jpeg_probability": 0.3,
        "jpeg_quality": [45, 90],
    },
}


def load_domain_adaptation_config(value: str | Path | dict[str, Any] | None) -> dict[str, Any]:
    config = _deep_merge({}, DEFAULT_DOMAIN_ADAPTATION_CONFIG)
    if value in (None, ""):
        return config
    if isinstance(value, dict):
        override = value
    else:
        text = str(value)
        path = Path(text)
        if path.exists():
            override = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        else:
            override = yaml.safe_load(text) or {}
    if not isinstance(override, dict):
        raise ValueError("Domain adaptation config must be a mapping")
    return _deep_merge(config, override)


def row_sampling_weights(rows: Sequence[dict[str, Any]], config: dict[str, Any]) -> np.ndarray:
    sampling = config.get("sampling") or {}
    tier_weights = sampling.get("domain_tier_weights") or {}
    review_weights = sampling.get("review_state_weights") or {}
    group_counts = Counter(_field(row, "source_group_id", "source_group", "source_video_path") for row in rows)
    weights: list[float] = []
    for row in rows:
        tier = canonical_domain_tier(_field(row, "domain_tier", default="proxy"))
        review_state = _field(row, "review_state", default="review_required").split(".")[-1].lower()
        group = _field(row, "source_group_id", "source_group", "source_video_path")
        weight = _positive(tier_weights.get(tier), 1.0) * _positive(review_weights.get(review_state), 1.0)
        weight *= _positive(row.get("sampling_weight"), 1.0)
        if bool(sampling.get("balance_source_groups", True)):
            weight /= max(1, group_counts[group])
        weights.append(max(weight, 1e-8))
    return np.asarray(weights, dtype=np.float64)


def canonical_domain_tier(value: Any) -> str:
    normalized = str(value or "proxy").strip().lower()
    aliases = {
        "target_domain": "target",
        "near_domain": "near_target",
        "fluorescence_proxy": "proxy",
        "derived_proxy": "proxy",
        "synthetic_proxy": "synthetic",
    }
    return aliases.get(normalized, normalized)


def sampled_indices(
    rows: Sequence[dict[str, Any]], *, config: dict[str, Any], sample_count: int, seed: int
) -> list[int]:
    if not rows or sample_count <= 0:
        return []
    weights = torch.as_tensor(row_sampling_weights(rows, config), dtype=torch.double)
    generator = torch.Generator().manual_seed(int(seed))
    return torch.multinomial(weights, sample_count, replacement=True, generator=generator).tolist()


def sampling_report(rows: Sequence[dict[str, Any]], indices: Sequence[int]) -> dict[str, Any]:
    selected = [rows[index] for index in indices]
    return {
        "sample_count": len(selected),
        "domain_tier_counts": _counts(selected, "domain_tier", default="proxy"),
        "source_group_counts": _counts(selected, "source_group_id", fallback="source_video_path"),
        "review_state_counts": _counts(selected, "review_state", default="review_required"),
    }


def augment_microscope_image(image: np.ndarray, *, config: dict[str, Any], rng: np.random.Generator) -> np.ndarray:
    aug = config.get("augmentation") or {}
    source = np.asarray(image, dtype=np.uint8)
    if not bool(config.get("enabled")) or rng.random() > float(aug.get("probability", 0.0)):
        return source.copy()
    working = source.astype(np.float32) / 255.0
    working *= _uniform(rng, aug.get("exposure_gain"), 1.0)
    gamma = max(0.05, _uniform(rng, aug.get("gamma"), 1.0))
    working = np.power(np.clip(working, 0.0, 1.0), gamma)
    channel_low, channel_high = _range(aug.get("channel_gain"), 1.0)
    working *= rng.uniform(channel_low, channel_high, size=(1, 1, 3)).astype(np.float32)
    noise_low, noise_high = _range(aug.get("gaussian_noise_std"), 0.0)
    noise_std = float(rng.uniform(noise_low, noise_high)) / 255.0
    if noise_std > 0:
        working += rng.normal(0.0, noise_std, size=working.shape).astype(np.float32)
    output: np.ndarray = np.clip(working * 255.0, 0, 255).astype(np.uint8)
    if rng.random() < float(aug.get("blur_probability", 0.0)):
        choices = [int(v) | 1 for v in aug.get("blur_kernel_choices", [3]) if int(v) > 0]
        kernel = int(rng.choice(choices or [3]))
        output = cv2.GaussianBlur(output, (kernel, kernel), 0)
    if rng.random() < float(aug.get("specular_probability", 0.0)):
        output = _add_specular_highlight(output, rng)
    if rng.random() < float(aug.get("occlusion_probability", 0.0)):
        output = _add_occlusion(output, rng)
    if rng.random() < float(aug.get("jpeg_probability", 0.0)):
        low, high = _range(aug.get("jpeg_quality"), 75.0)
        quality = int(rng.integers(max(1, int(low)), min(100, int(high)) + 1))
        ok, encoded = cv2.imencode(".jpg", cv2.cvtColor(output, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, quality])
        if ok:
            output = cv2.cvtColor(cv2.imdecode(encoded, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    return output


def augmentation_report(config: dict[str, Any]) -> dict[str, Any]:
    return {"enabled": bool(config.get("enabled")), "augmentation": config.get("augmentation") or {}}


def _add_specular_highlight(image: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    height, width = image.shape[:2]
    overlay = np.zeros_like(image, dtype=np.float32)
    center = (int(rng.integers(0, width)), int(rng.integers(0, height)))
    axes = (max(2, int(rng.uniform(0.02, 0.12) * width)), max(2, int(rng.uniform(0.02, 0.12) * height)))
    cv2.ellipse(overlay, center, axes, float(rng.uniform(0, 180)), 0, 360, (255, 255, 255), -1)
    overlay = cast(
        np.ndarray,
        cv2.GaussianBlur(overlay, (0, 0), sigmaX=max(1.0, min(height, width) * 0.02)),
    )
    return np.clip(image.astype(np.float32) + overlay * float(rng.uniform(0.35, 0.9)), 0, 255).astype(np.uint8)


def _add_occlusion(image: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    output = image.copy()
    height, width = output.shape[:2]
    box_w = max(2, int(rng.uniform(0.04, 0.2) * width))
    box_h = max(2, int(rng.uniform(0.04, 0.2) * height))
    x0 = int(rng.integers(0, max(1, width - box_w + 1)))
    y0 = int(rng.integers(0, max(1, height - box_h + 1)))
    value = int(rng.integers(0, 65))
    output[y0 : y0 + box_h, x0 : x0 + box_w] = value
    return output


def _field(row: dict[str, Any], *keys: str, default: str = "unspecified") -> str:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return default


def _counts(
    rows: Sequence[dict[str, Any]], key: str, *, fallback: str | None = None, default: str = "unspecified"
) -> dict[str, int]:
    return dict(Counter(_field(row, key, *(tuple([fallback]) if fallback else ()), default=default) for row in rows))


def _positive(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _range(value: Any, default: float) -> tuple[float, float]:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        low, high = float(value[0]), float(value[1])
        return (low, high) if low <= high else (high, low)
    return default, default


def _uniform(rng: np.random.Generator, value: Any, default: float) -> float:
    low, high = _range(value, default)
    return float(rng.uniform(low, high))


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
