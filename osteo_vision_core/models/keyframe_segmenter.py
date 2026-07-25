from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torch import nn

from osteo_vision_core.core.paths import ensure_dir
from osteo_vision_core.metrics.calibration import predictive_entropy
from osteo_vision_core.models.video_signal_masks import save_video_signal_maps, video_signal_mask_contract
from osteo_vision_core.preprocess.fluorescence import blend_pseudocolor_on_reference


class ConvNeXtBlock2D(nn.Module):
    """Small ConvNeXt-style residual block for trainable keyframe segmentation."""

    def __init__(self, channels: int, *, kernel_size: int = 5) -> None:
        super().__init__()
        padding = kernel_size // 2
        self.depthwise = nn.Conv2d(channels, channels, kernel_size, padding=padding, groups=channels)
        self.norm = nn.GroupNorm(1, channels)
        self.pointwise = nn.Sequential(
            nn.Conv2d(channels, channels * 2, 1),
            nn.GELU(),
            nn.Conv2d(channels * 2, channels, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.pointwise(self.norm(self.depthwise(x)))


class ConvStage2D(nn.Module):
    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        self.stage = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, 3, padding=1),
            nn.GroupNorm(1, out_channels),
            nn.GELU(),
            ConvNeXtBlock2D(out_channels),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.stage(x)


class TinyKeyframeSegmenter2D(nn.Module):
    """A compact trainable 2D U-Net for MP4/JPEG keyframe proxy segmentation."""

    def __init__(self, in_channels: int = 3, out_channels: int = 2, base_channels: int = 8) -> None:
        super().__init__()
        c1 = base_channels
        c2 = base_channels * 2
        c3 = base_channels * 4
        self.enc0 = ConvStage2D(in_channels, c1)
        self.down1 = nn.Sequential(nn.Conv2d(c1, c2, 3, stride=2, padding=1), nn.GroupNorm(1, c2), nn.GELU())
        self.enc1 = ConvStage2D(c2, c2)
        self.down2 = nn.Sequential(nn.Conv2d(c2, c3, 3, stride=2, padding=1), nn.GroupNorm(1, c3), nn.GELU())
        self.bottleneck = ConvStage2D(c3, c3)
        self.up1 = nn.ConvTranspose2d(c3, c2, 2, stride=2)
        self.dec1 = ConvStage2D(c2 + c2, c2)
        self.up0 = nn.ConvTranspose2d(c2, c1, 2, stride=2)
        self.dec0 = ConvStage2D(c1 + c1, c1)
        self.head = nn.Conv2d(c1, out_channels, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x0 = self.enc0(x)
        x1 = self.enc1(self.down1(x0))
        x2 = self.bottleneck(self.down2(x1))
        y1 = self.up1(x2)
        if y1.shape[2:] != x1.shape[2:]:
            y1 = F.interpolate(y1, size=x1.shape[2:], mode="bilinear", align_corners=False)
        y1 = self.dec1(torch.cat([y1, x1], dim=1))
        y0 = self.up0(y1)
        if y0.shape[2:] != x0.shape[2:]:
            y0 = F.interpolate(y0, size=x0.shape[2:], mode="bilinear", align_corners=False)
        return self.head(self.dec0(torch.cat([y0, x0], dim=1)))


def build_keyframe_segmenter(config: dict[str, Any] | None = None) -> nn.Module:
    model_config = dict(config or {})
    architecture = str(model_config.get("architecture") or "convnext_unet")
    if architecture != "convnext_unet":
        from osteo_vision_core.models.keyframe_candidates import build_candidate_keyframe_segmenter

        return build_candidate_keyframe_segmenter(model_config)
    return TinyKeyframeSegmenter2D(
        in_channels=int(model_config.get("in_channels", 3)),
        out_channels=int(model_config.get("out_channels", 2)),
        base_channels=int(model_config.get("base_channels", 8)),
    )


def select_torch_device(policy: str = "auto") -> torch.device:
    if policy in {"auto", "gpu", "cuda"} and torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def load_keyframe_segmenter_checkpoint(
    checkpoint_path: str | Path,
    *,
    device: torch.device,
) -> tuple[nn.Module, dict[str, Any]]:
    checkpoint = _torch_load(checkpoint_path, device)
    if not isinstance(checkpoint, dict):
        raise ValueError(f"Unsupported keyframe segmenter checkpoint payload: {checkpoint_path}")
    model_config = dict(checkpoint.get("model_config") or {})
    model = build_keyframe_segmenter(model_config).to(device)
    state_dict = checkpoint.get("state_dict")
    if not isinstance(state_dict, dict):
        raise ValueError(f"Checkpoint missing state_dict: {checkpoint_path}")
    model.load_state_dict(state_dict)
    model.eval()
    metadata = {key: value for key, value in checkpoint.items() if key != "state_dict"}
    return model, metadata


def load_rgb_image(input_path: str | Path) -> np.ndarray:
    with Image.open(input_path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.uint8)


def predict_keyframe_image(
    model: nn.Module,
    input_path: str | Path,
    *,
    device: torch.device,
    output_dir: str | Path,
    case_id: str,
    threshold: float = 0.5,
    model_id: str = "convnext2d_keyframe_proxy_segmenter",
    tile_size: int | None = None,
    tile_overlap: int = 64,
    tile_batch_size: int = 1,
    force_tiled: bool = False,
    max_whole_pixels: int = 1024 * 1024,
    target_domain: bool = False,
    input_domain: str = "2D JPEG/MP4 keyframe fluorescence proxy",
    data_boundary: str = "synthetic_or_pseudo_labeled_non_target_domain",
    temperature: float = 1.0,
    tta_enabled: bool = False,
    fast_output: bool = False,
    overlay_format: str = "png",
    overlay_jpeg_quality: int = 85,
    use_amp: bool = False,
    evidence_png_compression: int = 3,
    candidate_min_component_area: int = 16,
    candidate_min_area_fraction: float = 0.0,
    candidate_max_count: int | None = None,
    rgb: np.ndarray | None = None,
) -> dict[str, Any]:
    rgb = load_rgb_image(input_path) if rgb is None else _validate_rgb_array(rgb)
    model.eval()
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    started = time.perf_counter()
    probability, technical_variance, inference_meta = predict_keyframe_probability_with_uncertainty(
        model,
        rgb,
        device=device,
        tile_size=tile_size,
        tile_overlap=tile_overlap,
        tile_batch_size=tile_batch_size,
        force_tiled=force_tiled,
        max_whole_pixels=max_whole_pixels,
        temperature=temperature,
        tta_enabled=tta_enabled,
        use_amp=use_amp,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    inference_meta["elapsed_ms"] = round(elapsed_ms, 3)
    inference_meta["temperature"] = float(temperature)
    inference_meta["tta_enabled"] = bool(tta_enabled)
    inference_meta["use_amp"] = bool(use_amp and device.type == "cuda")
    inference_meta["output_profile"] = "live_fast" if fast_output else "full_evidence"
    inference_meta["peak_gpu_memory_mb"] = (
        round(float(torch.cuda.max_memory_allocated(device) / (1024**2)), 3) if device.type == "cuda" else None
    )
    postprocess_started = time.perf_counter()
    mask = (probability >= float(threshold)).astype(np.uint8)
    out_dir = ensure_dir(output_dir)
    safe_case = _safe_name(case_id)
    mask_path = out_dir / f"{safe_case}_{model_id}_mask.png"
    probability_path = None if fast_output else out_dir / f"{safe_case}_{model_id}_probability.png"
    uncertainty_path = None if fast_output else out_dir / f"{safe_case}_{model_id}_uncertainty.png"
    normalized_overlay_format = "jpeg" if overlay_format.lower() in {"jpg", "jpeg"} else "png"
    overlay_suffix = ".jpg" if normalized_overlay_format == "jpeg" else ".png"
    overlay_path = out_dir / f"{safe_case}_{model_id}_overlay{overlay_suffix}"
    pseudo_path = None if fast_output else out_dir / f"{safe_case}_{model_id}_pseudo_color.png"
    uncertainty_started = time.perf_counter()
    threshold_uncertainty = uncertainty_from_probability(probability, threshold=float(threshold))
    if fast_output:
        uncertainty = threshold_uncertainty.astype(np.float32, copy=False)
        uncertainty_method = "distance_to_threshold_live_fast"
    else:
        entropy = predictive_entropy(probability)
        variance_uncertainty = np.clip(np.sqrt(np.maximum(technical_variance, 0.0)) * 4.0, 0.0, 1.0)
        uncertainty = np.maximum.reduce([entropy, threshold_uncertainty * 0.5, variance_uncertainty]).astype(np.float32)
        uncertainty_method = "predictive_entropy_plus_tta_variance" if tta_enabled else "predictive_entropy_calibrated"
    uncertainty_ms = (time.perf_counter() - uncertainty_started) * 1000.0
    signal_maps_started = time.perf_counter()
    evidence_compression = max(0, min(9, int(evidence_png_compression)))
    signal_paths = save_video_signal_maps(
        probability=probability,
        mask=mask,
        uncertainty=uncertainty,
        output_dir=out_dir,
        safe_case=safe_case,
        model_id=model_id,
        threshold=float(threshold),
        activity_score_path=probability_path,
        write_activity_score=not fast_output,
        png_compress_level=0 if fast_output else evidence_compression,
    )
    signal_maps_ms = (time.perf_counter() - signal_maps_started) * 1000.0
    visualization_started = time.perf_counter()
    pseudo = _green_pseudocolor(probability)
    overlay = blend_pseudocolor_on_reference(rgb, pseudo, alpha=0.45)
    visualization_ms = (time.perf_counter() - visualization_started) * 1000.0
    evidence_encoding_started = time.perf_counter()
    png_compression = 0 if fast_output else evidence_compression
    _write_png(mask_path, (mask * 255).astype(np.uint8), compression=png_compression)
    if uncertainty_path is not None:
        _write_png(
            uncertainty_path,
            np.clip(uncertainty * 255.0, 0, 255).astype(np.uint8),
            compression=png_compression,
        )
    if pseudo_path is not None:
        _write_png(pseudo_path, pseudo, compression=png_compression, rgb=True)
    if normalized_overlay_format == "jpeg":
        _write_jpeg(overlay_path, overlay, quality=max(30, min(95, int(overlay_jpeg_quality))))
    else:
        _write_png(overlay_path, overlay, compression=png_compression, rgb=True)
    evidence_encoding_ms = (time.perf_counter() - evidence_encoding_started) * 1000.0
    candidate_stats_started = time.perf_counter()
    min_area_fraction = max(0.0, float(candidate_min_area_fraction))
    effective_min_component_area = max(
        1,
        int(candidate_min_component_area),
        int(np.ceil(mask.size * min_area_fraction)),
    )
    candidates, candidate_extraction = connected_probability_candidates_with_summary(
        mask,
        probability,
        min_component_area=effective_min_component_area,
        model_id=model_id,
        max_candidates=candidate_max_count,
    )
    candidate_extraction["configured_min_component_area_px"] = int(candidate_min_component_area)
    candidate_extraction["configured_min_area_fraction"] = min_area_fraction
    positive_area = int(mask.sum())
    total_area = int(mask.size)
    uncertainty_summary = uncertainty_stats(
        uncertainty,
        mask,
        method=uncertainty_method,
        technical_variance=technical_variance,
    )
    review_priority = keyframe_review_priority(
        positive_area_fraction=float(positive_area / total_area) if total_area else 0.0,
        component_count=len(candidates),
        mean_boundary_uncertainty=float(uncertainty_summary["mean_uncertainty_in_mask"]),
        target_domain=bool(target_domain),
    )
    candidate_stats_ms = (time.perf_counter() - candidate_stats_started) * 1000.0
    inference_meta["postprocess"] = {
        "uncertainty_ms": round(uncertainty_ms, 3),
        "signal_map_generation_and_encoding_ms": round(signal_maps_ms, 3),
        "visualization_ms": round(visualization_ms, 3),
        "evidence_encoding_ms": round(evidence_encoding_ms, 3),
        "candidate_statistics_ms": round(candidate_stats_ms, 3),
        "total_ms": round((time.perf_counter() - postprocess_started) * 1000.0, 3),
        "probability_activity_score_shared": probability_path is not None,
        "evidence_png_compression": png_compression,
        "candidate_extraction": candidate_extraction,
    }
    quantification = {
        "available": True,
        "source": model_id,
        "threshold": float(threshold),
        "positive_area_px": positive_area,
        "total_area_px": total_area,
        "positive_area_fraction": float(positive_area / total_area) if total_area else 0.0,
        "mean_probability": float(probability.mean()),
        "max_probability": float(probability.max()),
        "component_count": len(candidates),
        "candidate_extraction": candidate_extraction,
        "uncertainty": uncertainty_summary,
        "review_priority": review_priority,
        "target_domain_flag": bool(target_domain),
        "inference": inference_meta,
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
        "uncertainty_path": str(uncertainty_path) if uncertainty_path is not None else None,
        "risk_mask_path": signal_paths["risk_mask_path"],
        "uncertain_mask_path": signal_paths["uncertain_mask_path"],
        "review_priority": review_priority,
        "target_domain_flag": bool(target_domain),
        "inference": inference_meta,
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
        probability_path=str(probability_path) if probability_path is not None else None,
        uncertainty_path=str(uncertainty_path) if uncertainty_path is not None else None,
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
            "adapter_mode": "trainable_convnext2d_keyframe_segmenter",
            "inference_mode": inference_meta["mode"],
            "review_priority": review_priority,
            "target_domain_flag": bool(target_domain),
            "failure_reason": None,
        },
        "score": quantification["positive_area_fraction"],
        "segmentation_mask": segmentation_mask,
        "lesion_evidence": {
            "type": "trainable_2d_keyframe_mask",
            "source": model_id,
            "mask_path": str(mask_path),
            "probability_path": str(probability_path) if probability_path is not None else None,
            "uncertainty_path": str(uncertainty_path) if uncertainty_path is not None else None,
            "risk_mask_path": signal_paths["risk_mask_path"],
            "uncertain_mask_path": signal_paths["uncertain_mask_path"],
            "pseudo_color_path": str(pseudo_path) if pseudo_path is not None else None,
            "overlay_path": str(overlay_path),
            "candidates": candidates,
            "candidate_extraction": candidate_extraction,
            "signal_masks": signal_masks,
            "video_signal_segmentation": signal_masks,
            "input_domain": input_domain,
            "data_boundary": data_boundary,
            "target_domain_flag": bool(target_domain),
            "review_priority": review_priority,
            "failure_reason": None,
            "inference": inference_meta,
        },
        "quantification": quantification,
        "signal_masks": signal_masks,
        "video_signal_segmentation": signal_masks,
    }


def predict_keyframe_probability(
    model: nn.Module,
    rgb: np.ndarray,
    *,
    device: torch.device,
    tile_size: int | None,
    tile_overlap: int,
    force_tiled: bool,
    max_whole_pixels: int,
    tile_batch_size: int = 1,
    temperature: float = 1.0,
    tta_enabled: bool = False,
    use_amp: bool = False,
) -> tuple[np.ndarray, dict[str, Any]]:
    probability, _variance, metadata = predict_keyframe_probability_with_uncertainty(
        model,
        rgb,
        device=device,
        tile_size=tile_size,
        tile_overlap=tile_overlap,
        tile_batch_size=tile_batch_size,
        force_tiled=force_tiled,
        max_whole_pixels=max_whole_pixels,
        temperature=temperature,
        tta_enabled=tta_enabled,
        use_amp=use_amp,
    )
    return probability, metadata


def predict_keyframe_probability_with_uncertainty(
    model: nn.Module,
    rgb: np.ndarray,
    *,
    device: torch.device,
    tile_size: int | None,
    tile_overlap: int,
    force_tiled: bool,
    max_whole_pixels: int,
    tile_batch_size: int = 1,
    temperature: float = 1.0,
    tta_enabled: bool = False,
    use_amp: bool = False,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    height, width = rgb.shape[:2]
    total_pixels = int(height * width)
    use_tiled = bool(force_tiled or (tile_size and total_pixels > max_whole_pixels))
    if not use_tiled:
        probability, variance = _predict_probability_tile(
            model,
            rgb,
            device=device,
            temperature=temperature,
            tta_enabled=tta_enabled,
            use_amp=use_amp,
        )
        return (
            probability,
            variance,
            {
                "mode": "whole_frame",
                "tile_size": None,
                "tile_overlap": None,
                "tile_count": 1,
                "tile_batch_size": 1,
                "max_whole_pixels": int(max_whole_pixels),
                "input_width": int(width),
                "input_height": int(height),
            },
        )
    effective_tile = int(tile_size or 512)
    effective_tile = max(32, effective_tile)
    effective_overlap = max(0, min(int(tile_overlap), effective_tile - 1))
    effective_batch_size = max(1, int(tile_batch_size))
    y_starts = _tile_starts(height, effective_tile, effective_overlap)
    x_starts = _tile_starts(width, effective_tile, effective_overlap)
    accumulator = np.zeros((height, width), dtype=np.float32)
    variance_accumulator = np.zeros((height, width), dtype=np.float32)
    weights = np.zeros((height, width), dtype=np.float32)
    tile_regions = [
        (y0, min(height, y0 + effective_tile), x0, min(width, x0 + effective_tile))
        for y0 in y_starts
        for x0 in x_starts
    ]
    device_result = _predict_tiled_probability_on_device(
        model,
        rgb,
        tile_regions=tile_regions,
        tile_batch_size=effective_batch_size,
        device=device,
        temperature=temperature,
        tta_enabled=tta_enabled,
        use_amp=use_amp,
    )
    if device_result is not None:
        probability, variance = device_result
        return (
            probability,
            variance,
            {
                "mode": "tiled",
                "tile_size": effective_tile,
                "tile_overlap": effective_overlap,
                "tile_count": int(len(y_starts) * len(x_starts)),
                "tile_batch_size": effective_batch_size,
                "max_whole_pixels": int(max_whole_pixels),
                "input_width": int(width),
                "input_height": int(height),
            },
        )
    for start in range(0, len(tile_regions), effective_batch_size):
        batch_regions = tile_regions[start : start + effective_batch_size]
        batch_rgb = [rgb[y0:y1, x0:x1] for y0, y1, x0, x1 in batch_regions]
        batch_probabilities, batch_variances = _predict_probability_batch(
            model,
            batch_rgb,
            device=device,
            temperature=temperature,
            tta_enabled=tta_enabled,
            use_amp=use_amp,
        )
        for (y0, y1, x0, x1), tile_probability, tile_variance in zip(
            batch_regions,
            batch_probabilities,
            batch_variances,
            strict=True,
        ):
            accumulator[y0:y1, x0:x1] += tile_probability
            variance_accumulator[y0:y1, x0:x1] += tile_variance
            weights[y0:y1, x0:x1] += 1.0
    probability = accumulator / np.maximum(weights, 1.0)
    variance = variance_accumulator / np.maximum(weights, 1.0)
    return (
        probability.astype(np.float32),
        variance.astype(np.float32),
        {
            "mode": "tiled",
            "tile_size": effective_tile,
            "tile_overlap": effective_overlap,
            "tile_count": int(len(y_starts) * len(x_starts)),
            "tile_batch_size": effective_batch_size,
            "max_whole_pixels": int(max_whole_pixels),
            "input_width": int(width),
            "input_height": int(height),
        },
    )


def _predict_probability_tile(
    model: nn.Module,
    rgb: np.ndarray,
    *,
    device: torch.device,
    temperature: float,
    tta_enabled: bool,
    use_amp: bool,
) -> tuple[np.ndarray, np.ndarray]:
    probabilities, variances = _predict_probability_batch(
        model,
        [rgb],
        device=device,
        temperature=temperature,
        tta_enabled=tta_enabled,
        use_amp=use_amp,
    )
    return probabilities[0], variances[0]


def _predict_probability_batch(
    model: nn.Module,
    rgb_batch: list[np.ndarray],
    *,
    device: torch.device,
    temperature: float,
    tta_enabled: bool,
    use_amp: bool,
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    if not rgb_batch:
        return [], []
    shapes = {image.shape for image in rgb_batch}
    if len(shapes) != 1:
        return _predict_probability_tiles_individually(
            model,
            rgb_batch,
            device=device,
            temperature=temperature,
            tta_enabled=tta_enabled,
            use_amp=use_amp,
        )
    try:
        mean, variance = _predict_probability_batch_tensor(
            model,
            rgb_batch,
            device=device,
            temperature=temperature,
            tta_enabled=tta_enabled,
            use_amp=use_amp,
        )
        mean_cpu = mean.detach().cpu().numpy().astype(np.float32)
        variance_cpu = variance.detach().cpu().numpy().astype(np.float32)
    except torch.OutOfMemoryError:
        if len(rgb_batch) == 1:
            raise
        if device.type == "cuda":
            torch.cuda.empty_cache()
        return _predict_probability_tiles_individually(
            model,
            rgb_batch,
            device=device,
            temperature=temperature,
            tta_enabled=tta_enabled,
            use_amp=use_amp,
        )
    return [mean_cpu[index] for index in range(mean_cpu.shape[0])], [
        variance_cpu[index] for index in range(variance_cpu.shape[0])
    ]


def _predict_probability_batch_tensor(
    model: nn.Module,
    rgb_batch: list[np.ndarray],
    *,
    device: torch.device,
    temperature: float,
    tta_enabled: bool,
    use_amp: bool,
) -> tuple[torch.Tensor, torch.Tensor]:
    tensor = torch.from_numpy(np.stack(rgb_batch).astype(np.float32).transpose(0, 3, 1, 2) / 255.0).to(device=device)
    with (
        torch.inference_mode(),
        torch.autocast(
            device_type="cuda",
            dtype=torch.float16,
            enabled=bool(use_amp and device.type == "cuda"),
        ),
    ):
        logits = model(tensor)
        probability = torch.softmax(logits / max(1e-3, float(temperature)), dim=1)[:, 1]
        predictions = [probability]
        if tta_enabled:
            flipped = torch.flip(tensor, dims=[3])
            flipped_logits = model(flipped)
            flipped_probability = torch.softmax(flipped_logits / max(1e-3, float(temperature)), dim=1)[:, 1]
            predictions.append(torch.flip(flipped_probability, dims=[2]))
        stacked = torch.stack(predictions)
        return stacked.mean(dim=0), stacked.var(dim=0, unbiased=False)


def _predict_tiled_probability_on_device(
    model: nn.Module,
    rgb: np.ndarray,
    *,
    tile_regions: list[tuple[int, int, int, int]],
    tile_batch_size: int,
    device: torch.device,
    temperature: float,
    tta_enabled: bool,
    use_amp: bool,
) -> tuple[np.ndarray, np.ndarray] | None:
    if device.type != "cuda" or tile_batch_size <= 1:
        return None
    tile_shapes = {(y1 - y0, x1 - x0) for y0, y1, x0, x1 in tile_regions}
    if len(tile_shapes) != 1:
        return None
    height, width = rgb.shape[:2]
    try:
        accumulator = torch.zeros((height, width), dtype=torch.float32, device=device)
        variance_accumulator = torch.zeros_like(accumulator)
        weights = torch.zeros_like(accumulator)
        for start in range(0, len(tile_regions), tile_batch_size):
            batch_regions = tile_regions[start : start + tile_batch_size]
            batch_rgb = [rgb[y0:y1, x0:x1] for y0, y1, x0, x1 in batch_regions]
            batch_probability, batch_variance = _predict_probability_batch_tensor(
                model,
                batch_rgb,
                device=device,
                temperature=temperature,
                tta_enabled=tta_enabled,
                use_amp=use_amp,
            )
            for index, (y0, y1, x0, x1) in enumerate(batch_regions):
                accumulator[y0:y1, x0:x1] += batch_probability[index]
                variance_accumulator[y0:y1, x0:x1] += batch_variance[index]
                weights[y0:y1, x0:x1] += 1.0
        denominator = weights.clamp_min(1.0)
        probability = (accumulator / denominator).detach().cpu().numpy().astype(np.float32)
        variance = (variance_accumulator / denominator).detach().cpu().numpy().astype(np.float32)
        return probability, variance
    except torch.OutOfMemoryError:
        torch.cuda.empty_cache()
        return None


def _predict_probability_tiles_individually(
    model: nn.Module,
    rgb_batch: list[np.ndarray],
    *,
    device: torch.device,
    temperature: float,
    tta_enabled: bool,
    use_amp: bool,
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    results = [
        _predict_probability_tile(
            model,
            image,
            device=device,
            temperature=temperature,
            tta_enabled=tta_enabled,
            use_amp=use_amp,
        )
        for image in rgb_batch
    ]
    return [probability for probability, _variance in results], [variance for _probability, variance in results]


def uncertainty_from_probability(probability: np.ndarray, *, threshold: float) -> np.ndarray:
    """Return threshold-proximity uncertainty without changing the binary mask."""

    effective_threshold = float(np.clip(threshold, 1e-6, 1.0 - 1e-6))
    scale = max(effective_threshold, 1.0 - effective_threshold)
    uncertainty = 1.0 - (np.abs(np.asarray(probability, dtype=np.float32) - effective_threshold) / scale)
    return np.clip(uncertainty, 0.0, 1.0).astype(np.float32)


def uncertainty_stats(
    uncertainty: np.ndarray,
    mask: np.ndarray,
    *,
    method: str = "threshold_proximity",
    technical_variance: np.ndarray | None = None,
) -> dict[str, Any]:
    if uncertainty.size == 0:
        return {
            "method": method,
            "mean_uncertainty": 0.0,
            "max_uncertainty": 0.0,
            "mean_uncertainty_in_mask": 0.0,
            "high_uncertainty_fraction": 0.0,
        }
    foreground = uncertainty[mask > 0]
    return {
        "method": method,
        "mean_uncertainty": float(uncertainty.mean()),
        "max_uncertainty": float(uncertainty.max()),
        "mean_uncertainty_in_mask": float(foreground.mean()) if foreground.size else 0.0,
        "high_uncertainty_fraction": float((uncertainty >= 0.75).mean()),
        "mean_tta_variance": float(np.mean(technical_variance)) if technical_variance is not None else 0.0,
        "max_tta_variance": float(np.max(technical_variance)) if technical_variance is not None else 0.0,
    }


def keyframe_review_priority(
    *,
    positive_area_fraction: float,
    component_count: int,
    mean_boundary_uncertainty: float,
    target_domain: bool,
) -> str:
    if not target_domain:
        return "high"
    if component_count <= 0 or positive_area_fraction <= 0:
        return "low"
    if positive_area_fraction > 0.45 or mean_boundary_uncertainty >= 0.65:
        return "high"
    if positive_area_fraction >= 0.005:
        return "medium"
    return "low"


def _tile_starts(length: int, tile_size: int, tile_overlap: int) -> list[int]:
    if length <= tile_size:
        return [0]
    stride = max(1, tile_size - tile_overlap)
    starts = list(range(0, max(1, length - tile_size + 1), stride))
    final_start = max(0, length - tile_size)
    if starts[-1] != final_start:
        starts.append(final_start)
    return starts


def connected_probability_candidates(
    mask: np.ndarray,
    probability: np.ndarray,
    *,
    min_component_area: int,
    model_id: str,
    max_candidates: int | None = None,
) -> list[dict[str, Any]]:
    candidates, _summary = connected_probability_candidates_with_summary(
        mask,
        probability,
        min_component_area=min_component_area,
        model_id=model_id,
        max_candidates=max_candidates,
    )
    return candidates


def connected_probability_candidates_with_summary(
    mask: np.ndarray,
    probability: np.ndarray,
    *,
    min_component_area: int,
    model_id: str,
    max_candidates: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    safe_min_area = max(1, int(min_component_area))
    try:
        import cv2

        component_count, labels, stats, _centroids = cv2.connectedComponentsWithStats(
            mask.astype(np.uint8), connectivity=8
        )
    except Exception:
        fallback = _single_candidate(mask, probability, min_component_area=safe_min_area, model_id=model_id)
        return fallback, {
            "method": "single_candidate_fallback",
            "total_component_count": len(fallback),
            "eligible_component_count": len(fallback),
            "retained_candidate_count": len(fallback),
            "suppressed_small_component_count": 0,
            "suppressed_limit_count": 0,
            "min_component_area_px": safe_min_area,
            "max_candidates": max_candidates,
        }
    flat_labels = np.asarray(labels, dtype=np.int32).ravel()
    flat_probability = probability.astype(np.float32, copy=False).ravel()
    component_count = int(component_count)
    component_sums = np.bincount(flat_labels, weights=flat_probability, minlength=component_count)
    component_max = np.full(component_count, -np.inf, dtype=np.float32)
    np.maximum.at(component_max, flat_labels, flat_probability)
    candidates: list[dict[str, Any]] = []
    suppressed_small = 0
    for label in range(1, component_count):
        x, y, width, height, area = [int(value) for value in stats[label]]
        if area < safe_min_area:
            suppressed_small += 1
            continue
        score = float(component_sums[label] / area) if area else 0.0
        ranking_score = score * float(np.sqrt(max(1, area)))
        candidates.append(
            {
                "candidate_id": f"{model_id}_component_{label}",
                "bbox_xyxy": [x, y, x + width, y + height],
                "area_px": area,
                "score": score,
                "confidence": float(component_max[label]) if area else 0.0,
                "ranking_score": round(ranking_score, 6),
                "source": model_id,
            }
        )
    candidates.sort(
        key=lambda item: (
            float(item["ranking_score"]),
            float(item["score"]),
            int(item["area_px"]),
        ),
        reverse=True,
    )
    eligible_count = len(candidates)
    safe_limit = max(1, int(max_candidates)) if max_candidates is not None else None
    if safe_limit is not None:
        candidates = candidates[:safe_limit]
    return candidates, {
        "method": "scale_aware_connected_components_v2",
        "total_component_count": max(0, component_count - 1),
        "eligible_component_count": eligible_count,
        "retained_candidate_count": len(candidates),
        "suppressed_small_component_count": suppressed_small,
        "suppressed_limit_count": max(0, eligible_count - len(candidates)),
        "min_component_area_px": safe_min_area,
        "max_candidates": safe_limit,
        "ranking": "mean_probability_times_sqrt_area",
    }


def checkpoint_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _single_candidate(
    mask: np.ndarray,
    probability: np.ndarray,
    *,
    min_component_area: int,
    model_id: str,
) -> list[dict[str, Any]]:
    ys, xs = np.where(mask > 0)
    area = int(xs.size)
    if area < min_component_area:
        return []
    values = probability[mask > 0]
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


def _green_pseudocolor(probability: np.ndarray) -> np.ndarray:
    normalized = np.clip(probability, 0.0, 1.0)
    output = np.zeros((*normalized.shape, 3), dtype=np.uint8)
    output[..., 1] = np.clip(normalized * 255.0, 0, 255).astype(np.uint8)
    output[..., 0] = np.clip(normalized * 40.0, 0, 40).astype(np.uint8)
    return output


def _validate_rgb_array(rgb: np.ndarray) -> np.ndarray:
    if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("Predecoded keyframe image must be an RGB uint8 array.")
    return np.ascontiguousarray(rgb)


def _write_png(path: Path, array: np.ndarray, *, compression: int, rgb: bool = False) -> None:
    try:
        import cv2

        value = cv2.cvtColor(array, cv2.COLOR_RGB2BGR) if rgb else array
        if cv2.imwrite(str(path), value, [cv2.IMWRITE_PNG_COMPRESSION, int(compression)]):
            return
    except Exception:
        pass
    Image.fromarray(array).save(path, compress_level=int(compression))


def _write_jpeg(path: Path, rgb: np.ndarray, *, quality: int) -> None:
    try:
        import cv2

        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        if cv2.imwrite(str(path), bgr, [cv2.IMWRITE_JPEG_QUALITY, int(quality), cv2.IMWRITE_JPEG_OPTIMIZE, 0]):
            return
    except Exception:
        pass
    Image.fromarray(rgb).save(path, quality=int(quality), optimize=False)


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value) or "case"


def _torch_load(path: str | Path, device: torch.device) -> Any:
    try:
        return torch.load(path, map_location=device, weights_only=False)
    except TypeError:
        return torch.load(path, map_location=device)
