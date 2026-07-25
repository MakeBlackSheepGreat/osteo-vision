from __future__ import annotations

from time import perf_counter
from typing import Any

import numpy as np

_FUSION_WARMUP_CACHE: dict[tuple[int, int, bool], dict[str, Any]] = {}
_REGISTRATION_WARMUP_CACHE: dict[tuple[int, int, bool], dict[str, Any]] = {}


def warmup_fusion_accelerator(
    *,
    width: int = 3840,
    height: int = 2160,
    prefer_gpu: bool = True,
) -> dict[str, Any]:
    """Initialize the configured fusion backend before the first measured case run."""

    safe_width = max(32, int(width))
    safe_height = max(32, int(height))
    key = (safe_width, safe_height, bool(prefer_gpu))
    cached = _FUSION_WARMUP_CACHE.get(key)
    if cached is not None:
        return {**cached, "cached": True}
    started = perf_counter()
    white = np.zeros((safe_height, safe_width, 3), dtype=np.uint8)
    row = np.linspace(0.0, 255.0, safe_width, dtype=np.float32)
    fluorescence = np.broadcast_to(row, (safe_height, safe_width))
    _, _, _, acceleration = accelerated_normalize_pseudocolor_blend(
        white,
        fluorescence,
        alpha=0.45,
        colormap="green",
        prefer_gpu=prefer_gpu,
    )
    registration_warmup = {
        "requested": False,
        "gpu_ready": False,
        "cached": False,
        "reason": "resolution_below_registration_warmup_minimum",
    }
    if safe_width >= 256 and safe_height >= 256:
        registration_warmup = warmup_registration_pipeline(
            width=safe_width,
            height=safe_height,
            prefer_gpu=prefer_gpu,
        )
    payload = {
        "requested": True,
        "resolution": [safe_width, safe_height],
        "backend": acceleration.get("backend"),
        "device": acceleration.get("device"),
        "peak_gpu_memory_mb": acceleration.get("peak_gpu_memory_mb"),
        "warmup_elapsed_ms": round((perf_counter() - started) * 1000.0, 3),
        "gpu_ready": acceleration.get("backend") == "torch_cuda",
        "registration_warmup": registration_warmup,
        "cached": False,
    }
    _FUSION_WARMUP_CACHE[key] = payload
    return payload


def warmup_registration_pipeline(
    *,
    width: int = 3840,
    height: int = 2160,
    prefer_gpu: bool = True,
) -> dict[str, Any]:
    """Warm the registration resampling kernels used by the first 4K frame.

    CUDA's first ``grid_sample`` invocation can be several times slower than
    subsequent frames.  The regular fusion warmup only exercises tensor
    arithmetic, so it leaves the affine/local-grid registration path cold.
    This bounded warmup uses a deterministic zero residual field and records
    the accelerator status without entering the evidence path.
    """

    safe_width = max(32, int(width))
    safe_height = max(32, int(height))
    key = (safe_width, safe_height, bool(prefer_gpu))
    cached = _REGISTRATION_WARMUP_CACHE.get(key)
    if cached is not None:
        return {**cached, "cached": True}

    started = perf_counter()
    payload: dict[str, Any]
    try:
        moving = np.zeros((safe_height, safe_width), dtype=np.float32)
        matrix = np.asarray([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32)
        deformation_grid = np.zeros((5, 7, 2), dtype=np.float32)
        _, accelerator, peak_mb = _warp_affine_with_local_deformation(
            moving,
            matrix,
            deformation_grid,
            output_size=(safe_width, safe_height),
            prefer_gpu=prefer_gpu,
            return_device_tensor=False,
        )
        payload = {
            "requested": True,
            "resolution": [safe_width, safe_height],
            "backend": accelerator,
            "device": "cuda" if accelerator.startswith("torch_cuda") else "cpu",
            "peak_gpu_memory_mb": peak_mb,
            "warmup_elapsed_ms": round((perf_counter() - started) * 1000.0, 3),
            "gpu_ready": accelerator.startswith("torch_cuda"),
            "cached": False,
        }
    except Exception as exc:  # pragma: no cover - hardware-specific fallback
        payload = {
            "requested": True,
            "resolution": [safe_width, safe_height],
            "backend": "unavailable",
            "device": "cpu",
            "peak_gpu_memory_mb": None,
            "warmup_elapsed_ms": round((perf_counter() - started) * 1000.0, 3),
            "gpu_ready": False,
            "cached": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    _REGISTRATION_WARMUP_CACHE[key] = payload
    return payload


def register_adaptive_multiscale(
    reference_rgb: np.ndarray,
    moving_gray: np.ndarray,
    *,
    min_response: float = 0.08,
    max_translation_fraction: float = 0.15,
    max_registration_side: int = 512,
    prefer_gpu: bool = True,
    previous_matrix: np.ndarray | None = None,
    temporal_smoothing_alpha: float = 0.7,
    max_temporal_jump_fraction: float = 0.03,
    enable_local_deformation: bool = True,
    local_deformation_min_residual_px: float = 2.0,
    max_local_deformation_fraction: float = 0.02,
    previous_deformation_grid: np.ndarray | None = None,
    deformation_smoothing_alpha: float = 0.55,
    return_device_tensor: bool = False,
) -> tuple[Any, dict[str, Any]]:
    """Register weakly textured multimodal frames with bounded, fail-closed candidates."""

    import cv2

    started = perf_counter()
    reference_source = np.asarray(reference_rgb)
    moving = np.asarray(moving_gray, dtype=np.float32)
    if reference_source.shape[:2] != moving.shape or min(moving.shape) < 32:
        return moving, _failed_report("registration_shape_unusable", started)

    height, width = moving.shape
    scale = min(1.0, float(max_registration_side) / float(max(height, width)))
    work_size = (max(32, int(round(width * scale))), max(32, int(round(height * scale))))
    reference_work_source = (
        cv2.resize(reference_source, work_size, interpolation=cv2.INTER_AREA) if scale < 1.0 else reference_source
    )
    reference_work = _gray_raw(reference_work_source)
    moving_work = cv2.resize(moving, work_size, interpolation=cv2.INTER_AREA) if scale < 1.0 else moving
    reference_edge = _edge_map(reference_work)
    moving_edge = _edge_map(moving_work)

    candidates: list[dict[str, Any]] = []
    candidates.extend(_phase_candidates(reference_edge, moving_edge, scale_to_full=1.0 / scale))
    tile_measurements = _tile_phase_measurements(reference_edge, moving_edge)
    tile_candidate = _robust_tile_translation(
        tile_measurements,
        scale_to_full=1.0 / scale,
    )
    if tile_candidate is not None:
        candidates.append(tile_candidate)
    tile_affine_candidate = _tile_affine_candidate(
        tile_measurements,
        scale_to_full=1.0 / scale,
    )
    if tile_affine_candidate is not None:
        candidates.append(tile_affine_candidate)
    strong_phase_evidence = max((float(item.get("response", 0.0)) for item in candidates), default=0.0) >= 0.2
    if not strong_phase_evidence:
        orb_candidate = _orb_affine_candidate(reference_edge, moving_edge, scale_to_full=1.0 / scale)
        if orb_candidate is not None:
            candidates.append(orb_candidate)

    max_shift = max(1.0, max(width, height) * float(max_translation_fraction))
    accepted: list[dict[str, Any]] = []
    for candidate in candidates:
        matrix = np.asarray(candidate["matrix"], dtype=np.float32)
        translation = matrix[:, 2]
        if not np.isfinite(matrix).all() or np.max(np.abs(translation)) > max_shift:
            continue
        linear = matrix[:, :2]
        singular_values = np.linalg.svd(linear, compute_uv=False)
        if singular_values.min() < 0.85 or singular_values.max() > 1.15:
            continue
        candidate["quality"] = _candidate_quality(reference_edge, moving_edge, matrix, scale=scale)
        if float(candidate.get("response", 0.0)) >= min_response or float(candidate["quality"]) >= 0.12:
            accepted.append(candidate)

    if not accepted:
        report = _failed_report("low_response_or_unsafe_transform", started)
        report.update(
            {
                "candidate_count": len(candidates),
                "min_response": float(min_response),
                "max_translation_px": round(max_shift, 4),
                "registration_size": list(work_size),
            }
        )
        return moving, report

    selected = max(accepted, key=lambda item: (float(item["quality"]), float(item.get("response", 0.0))))
    raw_matrix = np.asarray(selected["matrix"], dtype=np.float32)
    matrix, temporal = _stabilize_registration_matrix(
        raw_matrix,
        previous_matrix=previous_matrix,
        quality=float(selected["quality"]),
        image_size=(width, height),
        alpha=temporal_smoothing_alpha,
        max_jump_fraction=max_temporal_jump_fraction,
    )
    deformation_grid: np.ndarray | None = None
    if enable_local_deformation:
        deformation_grid, local_deformation = _estimate_local_deformation(
            tile_measurements,
            matrix,
            scale=scale,
            image_size=(width, height),
            min_residual_px=local_deformation_min_residual_px,
            max_deformation_fraction=max_local_deformation_fraction,
            previous_grid=previous_deformation_grid,
            smoothing_alpha=deformation_smoothing_alpha,
        )
    else:
        local_deformation = {
            "enabled": False,
            "applied": False,
            "reason": "disabled",
            "model": None,
        }
    if deformation_grid is not None:
        registered, accelerator, local_warp_peak_gpu_memory_mb = _warp_affine_with_local_deformation(
            moving,
            matrix,
            deformation_grid,
            output_size=(width, height),
            prefer_gpu=prefer_gpu,
            return_device_tensor=return_device_tensor,
        )
    else:
        registered, accelerator = _warp_affine(
            moving,
            matrix,
            output_size=(width, height),
            prefer_gpu=prefer_gpu,
        )
        local_warp_peak_gpu_memory_mb = None
    elapsed_ms = (perf_counter() - started) * 1000.0
    local_residual_before = local_deformation.get("residual_p95_before_px")
    local_residual_after = local_deformation.get("residual_p95_after_px")
    unresolved_local_residual = float(local_residual_after or local_residual_before or 0.0)
    if isinstance(registered, np.ndarray):
        registered = registered.astype(np.float32, copy=False)
        registered_frame_residency = "cpu"
    else:
        registered_frame_residency = "cuda"
    return registered, {
        "method": "adaptive_multiscale_registration_v2",
        "applied": True,
        "reason": "candidate_quality_gate_met",
        "selected_candidate": str(selected["name"]),
        "transform_model": str(selected["transform_model"]),
        "raw_matrix_2x3": [[round(float(value), 7) for value in row] for row in raw_matrix],
        "matrix_2x3": [[round(float(value), 7) for value in row] for row in matrix],
        "translation_xy": [round(float(matrix[0, 2]), 4), round(float(matrix[1, 2]), 4)],
        "response": round(float(selected.get("response", 0.0)), 6),
        "quality": round(float(selected["quality"]), 6),
        "min_response": float(min_response),
        "max_translation_px": round(max_shift, 4),
        "registration_size": list(work_size),
        "source_size": [width, height],
        "candidate_count": len(candidates),
        "accepted_candidate_count": len(accepted),
        "valid_tile_count": int(selected.get("valid_tile_count", 0)),
        "inlier_count": int(selected.get("inlier_count", 0)),
        "local_motion_mad_px": selected.get("local_motion_mad_px"),
        "local_residual_p95_px": (
            round(float(local_residual_after), 4)
            if local_residual_after is not None
            else selected.get("local_residual_p95_px")
        ),
        "local_residual_p95_before_px": local_residual_before,
        "local_deformation": local_deformation,
        "deformation_review_required": bool(unresolved_local_residual > 3.0),
        "temporal_stabilization": temporal,
        "accelerator": accelerator,
        "local_warp_peak_gpu_memory_mb": local_warp_peak_gpu_memory_mb,
        "registered_frame_residency": registered_frame_residency,
        "elapsed_ms": round(elapsed_ms, 3),
        "safety_boundary": "Bounded engineering registration; real-device geometric accuracy requires independent validation.",
    }


def accelerated_pseudocolor_blend(
    white_rgb: np.ndarray,
    normalized_fluorescence: np.ndarray,
    *,
    alpha: float,
    colormap: str,
    prefer_gpu: bool = True,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Generate pseudo-color and overlay with a CUDA path and deterministic CPU fallback."""

    started = perf_counter()
    white_source = np.array(white_rgb, copy=not np.asarray(white_rgb).flags.writeable)
    signal = np.clip(np.asarray(normalized_fluorescence, dtype=np.float32), 0.0, 1.0)
    key = str(colormap).strip().lower()
    if prefer_gpu:
        try:
            import torch

            if torch.cuda.is_available():
                device = torch.device("cuda")
                torch.cuda.reset_peak_memory_stats(device)
                with torch.inference_mode():
                    white_tensor = torch.from_numpy(np.ascontiguousarray(white_source)).to(
                        device=device,
                        dtype=torch.float16,
                        non_blocking=True,
                    )
                    signal_tensor = torch.from_numpy(np.ascontiguousarray(signal)).to(
                        device=device,
                        dtype=torch.float16,
                        non_blocking=True,
                    )
                    gpu_zeros = torch.zeros_like(signal_tensor)
                    if key == "amber":
                        pseudo_tensor = torch.stack((signal_tensor, signal_tensor * 0.68, gpu_zeros), dim=-1)
                    elif key == "magenta":
                        pseudo_tensor = torch.stack((signal_tensor, gpu_zeros, signal_tensor * 0.88), dim=-1)
                    else:
                        key = "green"
                        pseudo_tensor = torch.stack((gpu_zeros, signal_tensor, signal_tensor * 0.18), dim=-1)
                    pseudo_tensor = (pseudo_tensor * 255.0).clamp(0, 255)
                    overlay_tensor = ((1.0 - float(alpha)) * white_tensor + float(alpha) * pseudo_tensor).clamp(0, 255)
                    pseudo_cpu = pseudo_tensor.to(dtype=torch.uint8).cpu().numpy()
                    overlay_cpu = overlay_tensor.to(dtype=torch.uint8).cpu().numpy()
                    torch.cuda.synchronize(device)
                    peak_mb = float(torch.cuda.max_memory_allocated(device) / (1024**2))
                return (
                    pseudo_cpu,
                    overlay_cpu,
                    {
                        "device": "cuda",
                        "backend": "torch_cuda",
                        "colormap": key,
                        "elapsed_ms": round((perf_counter() - started) * 1000.0, 3),
                        "peak_gpu_memory_mb": round(peak_mb, 3),
                    },
                )
        except Exception:
            pass

    zeros = np.zeros_like(signal)
    if key == "amber":
        channels = (signal, signal * 0.68, zeros)
    elif key == "magenta":
        channels = (signal, zeros, signal * 0.88)
    else:
        key = "green"
        channels = (zeros, signal, signal * 0.18)
    pseudo_cpu = np.clip(np.stack(channels, axis=-1) * 255.0, 0, 255).astype(np.uint8)
    white_cpu = np.asarray(white_source, dtype=np.float32)
    overlay_cpu = np.clip((1.0 - float(alpha)) * white_cpu + float(alpha) * pseudo_cpu, 0, 255).astype(np.uint8)
    return (
        pseudo_cpu,
        overlay_cpu,
        {
            "device": "cpu",
            "backend": "numpy",
            "colormap": key,
            "elapsed_ms": round((perf_counter() - started) * 1000.0, 3),
            "peak_gpu_memory_mb": None,
        },
    )


def accelerated_normalize_pseudocolor_blend(
    white_rgb: np.ndarray,
    fluorescence: Any,
    *,
    alpha: float,
    colormap: str,
    lower_percentile: float = 1.0,
    upper_percentile: float = 99.0,
    prefer_gpu: bool = True,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    """Normalize and blend a 4K fluorescence plane in one accelerated stage."""

    started = perf_counter()
    white_array = np.asarray(white_rgb, dtype=np.uint8)
    white_source = np.array(white_array, copy=not white_array.flags.writeable)
    cuda_signal = None
    try:
        import torch

        if isinstance(fluorescence, torch.Tensor) and fluorescence.is_cuda:
            cuda_signal = fluorescence.detach()
    except Exception:
        pass
    if cuda_signal is not None:
        signal = None
        low, high = _sampled_percentile_limits_from_cuda(
            cuda_signal,
            lower_percentile=lower_percentile,
            upper_percentile=upper_percentile,
        )
    else:
        signal = np.asarray(fluorescence, dtype=np.float32)
        low, high = _sampled_percentile_limits(
            signal,
            lower_percentile=lower_percentile,
            upper_percentile=upper_percentile,
        )
    key = str(colormap).strip().lower()
    if prefer_gpu and high > low:
        try:
            import torch

            if torch.cuda.is_available():
                device = torch.device("cuda")
                torch.cuda.reset_peak_memory_stats(device)
                with torch.inference_mode():
                    white_tensor = torch.from_numpy(np.ascontiguousarray(white_source)).to(
                        device=device,
                        dtype=torch.float16,
                        non_blocking=True,
                    )
                    signal_tensor = (
                        cuda_signal.to(device=device, dtype=torch.float16)
                        if cuda_signal is not None
                        else torch.from_numpy(np.ascontiguousarray(signal)).to(
                            device=device,
                            dtype=torch.float16,
                            non_blocking=True,
                        )
                    )
                    normalized_tensor = ((signal_tensor - low) / (high - low)).clamp(0, 1)
                    gpu_zeros = torch.zeros_like(normalized_tensor)
                    if key == "amber":
                        pseudo_tensor = torch.stack((normalized_tensor, normalized_tensor * 0.68, gpu_zeros), dim=-1)
                    elif key == "magenta":
                        pseudo_tensor = torch.stack((normalized_tensor, gpu_zeros, normalized_tensor * 0.88), dim=-1)
                    else:
                        key = "green"
                        pseudo_tensor = torch.stack((gpu_zeros, normalized_tensor, normalized_tensor * 0.18), dim=-1)
                    pseudo_tensor = (pseudo_tensor * 255.0).clamp(0, 255)
                    overlay_tensor = ((1.0 - float(alpha)) * white_tensor + float(alpha) * pseudo_tensor).clamp(0, 255)
                    normalized_cpu = normalized_tensor.to(dtype=torch.float32).cpu().numpy()
                    pseudo_cpu = pseudo_tensor.to(dtype=torch.uint8).cpu().numpy()
                    overlay_cpu = overlay_tensor.to(dtype=torch.uint8).cpu().numpy()
                    torch.cuda.synchronize(device)
                    peak_mb = float(torch.cuda.max_memory_allocated(device) / (1024**2))
                return (
                    normalized_cpu,
                    pseudo_cpu,
                    overlay_cpu,
                    {
                        "device": "cuda",
                        "backend": "torch_cuda",
                        "colormap": key,
                        "normalization": {
                            "method": "sampled_percentile_robust",
                            "lower_percentile": float(lower_percentile),
                            "upper_percentile": float(upper_percentile),
                            "low": round(low, 6),
                            "high": round(high, 6),
                        },
                        "elapsed_ms": round((perf_counter() - started) * 1000.0, 3),
                        "peak_gpu_memory_mb": round(peak_mb, 3),
                        "input_residency": "cuda" if cuda_signal is not None else "cpu",
                    },
                )
        except Exception:
            pass

    if signal is None:
        assert cuda_signal is not None
        signal = cuda_signal.to(dtype=torch.float32).cpu().numpy()
    if high <= low:
        normalized_cpu = np.zeros_like(signal, dtype=np.float32)
    else:
        normalized_cpu = np.clip((signal - low) / (high - low), 0.0, 1.0).astype(np.float32)
    pseudo_cpu, overlay_cpu, blend_report = accelerated_pseudocolor_blend(
        white_source,
        normalized_cpu,
        alpha=alpha,
        colormap=key,
        prefer_gpu=False,
    )
    return (
        normalized_cpu,
        pseudo_cpu,
        overlay_cpu,
        {
            **blend_report,
            "normalization": {
                "method": "sampled_percentile_robust",
                "lower_percentile": float(lower_percentile),
                "upper_percentile": float(upper_percentile),
                "low": round(low, 6),
                "high": round(high, 6),
            },
            "elapsed_ms": round((perf_counter() - started) * 1000.0, 3),
        },
    )


def _phase_candidates(reference: np.ndarray, moving: np.ndarray, *, scale_to_full: float) -> list[dict[str, Any]]:
    import cv2

    candidates: list[dict[str, Any]] = []
    for factor in (0.5, 1.0):
        if factor < 1.0:
            size = (max(32, int(reference.shape[1] * factor)), max(32, int(reference.shape[0] * factor)))
            ref = cv2.resize(reference, size, interpolation=cv2.INTER_AREA)
            mov = cv2.resize(moving, size, interpolation=cv2.INTER_AREA)
        else:
            ref, mov = reference, moving
        window = cv2.createHanningWindow((ref.shape[1], ref.shape[0]), cv2.CV_32F)
        (shift_x, shift_y), response = cv2.phaseCorrelate(ref, mov, window)
        full_factor = scale_to_full / factor
        matrix = np.array(
            [[1.0, 0.0, -float(shift_x) * full_factor], [0.0, 1.0, -float(shift_y) * full_factor]],
            dtype=np.float32,
        )
        candidates.append(
            {
                "name": f"phase_correlation_scale_{factor:g}",
                "transform_model": "translation",
                "matrix": matrix,
                "response": float(response),
            }
        )
    return candidates


def _stabilize_registration_matrix(
    current: np.ndarray,
    *,
    previous_matrix: np.ndarray | None,
    quality: float,
    image_size: tuple[int, int],
    alpha: float,
    max_jump_fraction: float,
) -> tuple[np.ndarray, dict[str, Any]]:
    current_matrix = np.asarray(current, dtype=np.float32)
    if previous_matrix is None:
        return current_matrix, {
            "applied": False,
            "reason": "no_previous_transform",
            "translation_jump_px": None,
        }
    previous = np.asarray(previous_matrix, dtype=np.float32)
    if previous.shape != (2, 3) or not np.isfinite(previous).all():
        return current_matrix, {
            "applied": False,
            "reason": "previous_transform_invalid",
            "translation_jump_px": None,
        }
    jump = float(np.linalg.norm(current_matrix[:, 2] - previous[:, 2]))
    max_jump = max(1.0, max(image_size) * max(0.0, float(max_jump_fraction)))
    if jump > max_jump and quality < 0.25:
        return previous.copy(), {
            "applied": True,
            "reason": "previous_transform_held_after_low_quality_jump",
            "translation_jump_px": round(jump, 4),
            "max_temporal_jump_px": round(max_jump, 4),
            "alpha": 0.0,
        }
    if jump > max_jump:
        return current_matrix, {
            "applied": False,
            "reason": "high_quality_scene_change_accepted",
            "translation_jump_px": round(jump, 4),
            "max_temporal_jump_px": round(max_jump, 4),
        }
    bounded_alpha = min(1.0, max(0.0, float(alpha)))
    stabilized = previous * (1.0 - bounded_alpha) + current_matrix * bounded_alpha
    return stabilized.astype(np.float32), {
        "applied": True,
        "reason": "exponential_transform_smoothing",
        "translation_jump_px": round(jump, 4),
        "max_temporal_jump_px": round(max_jump, 4),
        "alpha": round(bounded_alpha, 4),
    }


def _robust_tile_translation(
    measurements: list[dict[str, float]],
    *,
    scale_to_full: float,
) -> dict[str, Any] | None:
    if len(measurements) < 3:
        return None
    values = np.asarray([(item["shift_x"], item["shift_y"]) for item in measurements], dtype=np.float32)
    median = np.median(values, axis=0)
    distance = np.linalg.norm(values - median, axis=1)
    mad = float(np.median(np.abs(distance - np.median(distance))))
    keep = distance <= max(1.5, 3.0 * mad)
    if int(keep.sum()) < 3:
        return None
    robust = np.median(values[keep], axis=0)
    responses = np.asarray([item["response"] for item in measurements], dtype=np.float32)[keep]
    matrix = np.array(
        [[1.0, 0.0, -float(robust[0]) * scale_to_full], [0.0, 1.0, -float(robust[1]) * scale_to_full]],
        dtype=np.float32,
    )
    return {
        "name": "occlusion_robust_tile_phase",
        "transform_model": "translation",
        "matrix": matrix,
        "response": float(np.median(responses)),
        "valid_tile_count": int(keep.sum()),
        "local_motion_mad_px": round(float(mad * scale_to_full), 4),
        "local_residual_p95_px": round(float(np.percentile(distance[keep], 95) * scale_to_full), 4),
    }


def _tile_phase_measurements(reference: np.ndarray, moving: np.ndarray) -> list[dict[str, float]]:
    import cv2

    height, width = reference.shape
    measurements: list[dict[str, float]] = []
    for row in range(3):
        for column in range(4):
            y0, y1 = row * height // 3, (row + 1) * height // 3
            x0, x1 = column * width // 4, (column + 1) * width // 4
            ref_tile = reference[y0:y1, x0:x1]
            mov_tile = moving[y0:y1, x0:x1]
            if min(ref_tile.shape) < 32 or float(ref_tile.std()) < 0.01 or float(mov_tile.std()) < 0.01:
                continue
            window = cv2.createHanningWindow((ref_tile.shape[1], ref_tile.shape[0]), cv2.CV_32F)
            (shift_x, shift_y), response = cv2.phaseCorrelate(ref_tile, mov_tile, window)
            if response >= 0.12 and np.isfinite([shift_x, shift_y, response]).all():
                measurements.append(
                    {
                        "shift_x": float(shift_x),
                        "shift_y": float(shift_y),
                        "response": float(response),
                        "center_x": float((x0 + x1 - 1) * 0.5),
                        "center_y": float((y0 + y1 - 1) * 0.5),
                    }
                )
    return measurements


def _tile_affine_candidate(
    measurements: list[dict[str, float]],
    *,
    scale_to_full: float,
) -> dict[str, Any] | None:
    import cv2

    if len(measurements) < 4:
        return None
    source = np.asarray([(item["center_x"], item["center_y"]) for item in measurements], dtype=np.float32)
    shifts = np.asarray([(item["shift_x"], item["shift_y"]) for item in measurements], dtype=np.float32)
    target = source - shifts
    matrix, inliers = cv2.estimateAffinePartial2D(
        source,
        target,
        method=cv2.RANSAC,
        ransacReprojThreshold=2.5,
        maxIters=500,
        confidence=0.99,
        refineIters=5,
    )
    if matrix is None or inliers is None or int(inliers.sum()) < 4:
        return None
    matrix_full = np.asarray(matrix, dtype=np.float32).copy()
    matrix_full[:, 2] *= float(scale_to_full)
    predicted = cv2.transform(source[None, ...], np.asarray(matrix, dtype=np.float32))[0]
    residual = np.linalg.norm(predicted - target, axis=1)
    inlier_mask = inliers.ravel() > 0
    responses = np.asarray([item["response"] for item in measurements], dtype=np.float32)
    return {
        "name": "occlusion_robust_tile_ransac_affine",
        "transform_model": "similarity",
        "matrix": matrix_full,
        "response": float(np.median(responses[inlier_mask])),
        "valid_tile_count": int(len(measurements)),
        "inlier_count": int(inlier_mask.sum()),
        "local_motion_mad_px": round(
            float(np.median(np.abs(residual[inlier_mask] - np.median(residual[inlier_mask]))) * scale_to_full),
            4,
        ),
        "local_residual_p95_px": round(float(np.percentile(residual[inlier_mask], 95) * scale_to_full), 4),
    }


def _orb_affine_candidate(
    reference: np.ndarray,
    moving: np.ndarray,
    *,
    scale_to_full: float,
) -> dict[str, Any] | None:
    import cv2

    reference_u8 = np.clip(reference * 255.0, 0, 255).astype(np.uint8)
    moving_u8 = np.clip(moving * 255.0, 0, 255).astype(np.uint8)
    detector = cv2.ORB_create(nfeatures=1600, scaleFactor=1.2, nlevels=6, fastThreshold=8)  # type: ignore[attr-defined]
    ref_points, ref_desc = detector.detectAndCompute(reference_u8, None)
    mov_points, mov_desc = detector.detectAndCompute(moving_u8, None)
    if ref_desc is None or mov_desc is None or len(ref_points) < 12 or len(mov_points) < 12:
        return None
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    pairs = matcher.knnMatch(mov_desc, ref_desc, k=2)
    good = [first for first, second in pairs if first.distance < 0.75 * second.distance]
    if len(good) < 8:
        return None
    source = np.asarray([mov_points[item.queryIdx].pt for item in good], dtype=np.float32)
    target = np.asarray([ref_points[item.trainIdx].pt for item in good], dtype=np.float32)
    matrix, inliers = cv2.estimateAffinePartial2D(
        source,
        target,
        method=cv2.RANSAC,
        ransacReprojThreshold=3.0,
        maxIters=2000,
        confidence=0.995,
        refineIters=10,
    )
    if matrix is None or inliers is None or int(inliers.sum()) < 6:
        return None
    matrix_float = np.asarray(matrix, dtype=np.float32).copy()
    matrix_float[0, 2] = float(matrix_float[0, 2]) * float(scale_to_full)
    matrix_float[1, 2] = float(matrix_float[1, 2]) * float(scale_to_full)
    return {
        "name": "orb_ransac_partial_affine",
        "transform_model": "similarity",
        "matrix": matrix_float,
        "response": float(inliers.mean()),
        "inlier_count": int(inliers.sum()),
    }


def _candidate_quality(reference: np.ndarray, moving: np.ndarray, matrix_full: np.ndarray, *, scale: float) -> float:
    import cv2

    matrix = np.asarray(matrix_full, dtype=np.float32).copy()
    matrix[:, 2] *= float(scale)
    warped = cv2.warpAffine(
        moving,
        matrix,
        (reference.shape[1], reference.shape[0]),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
    )
    margin_y = max(2, reference.shape[0] // 20)
    margin_x = max(2, reference.shape[1] // 20)
    ref = reference[margin_y:-margin_y, margin_x:-margin_x].ravel()
    mov = warped[margin_y:-margin_y, margin_x:-margin_x].ravel()
    if ref.size == 0 or float(ref.std()) < 1e-6 or float(mov.std()) < 1e-6:
        return -1.0
    return float(np.corrcoef(ref, mov)[0, 1])


def _estimate_local_deformation(
    measurements: list[dict[str, float]],
    matrix_full: np.ndarray,
    *,
    scale: float,
    image_size: tuple[int, int],
    min_residual_px: float,
    max_deformation_fraction: float,
    previous_grid: np.ndarray | None,
    smoothing_alpha: float,
) -> tuple[np.ndarray | None, dict[str, Any]]:
    """Fit a bounded quadratic residual field after the accepted global transform."""

    minimum_tiles = 6
    if len(measurements) < minimum_tiles:
        return None, {
            "enabled": True,
            "applied": False,
            "reason": "insufficient_valid_tiles",
            "model": "smooth_quadratic_residual_grid",
            "valid_tile_count": len(measurements),
            "minimum_valid_tile_count": minimum_tiles,
        }

    safe_scale = max(float(scale), 1e-6)
    width, height = image_size
    source = np.asarray([(item["center_x"], item["center_y"]) for item in measurements], dtype=np.float64)
    shifts = np.asarray([(item["shift_x"], item["shift_y"]) for item in measurements], dtype=np.float64)
    target = source - shifts
    matrix_work = np.asarray(matrix_full, dtype=np.float64).copy()
    matrix_work[:, 2] *= safe_scale
    predicted_global = source @ matrix_work[:, :2].T + matrix_work[:, 2]
    residual_full = (target - predicted_global) / safe_scale
    normalized_xy = np.column_stack(
        (
            source[:, 0] / max(1.0, float(width) * safe_scale - 1.0) * 2.0 - 1.0,
            source[:, 1] / max(1.0, float(height) * safe_scale - 1.0) * 2.0 - 1.0,
        )
    )
    responses = np.clip(
        np.asarray([item["response"] for item in measurements], dtype=np.float64),
        0.05,
        1.0,
    )

    affine_features = np.column_stack(
        (
            np.ones(len(normalized_xy), dtype=np.float64),
            normalized_xy[:, 0],
            normalized_xy[:, 1],
        )
    )
    affine_residual = affine_features @ _weighted_ridge_fit(
        affine_features,
        residual_full,
        responses,
        regularization=1e-5,
        robust_iterations=2,
    )
    observed_local = residual_full - affine_residual
    observed_norm = np.linalg.norm(observed_local, axis=1)
    residual_before = float(np.percentile(observed_norm, 95))
    safe_min_residual = max(0.5, float(min_residual_px))
    if residual_before < safe_min_residual:
        return None, {
            "enabled": True,
            "applied": False,
            "reason": "local_residual_below_activation_gate",
            "model": "smooth_quadratic_residual_grid",
            "valid_tile_count": len(measurements),
            "residual_p95_before_px": round(residual_before, 4),
            "activation_residual_px": round(safe_min_residual, 4),
        }

    quadratic_raw = np.column_stack(
        (
            normalized_xy[:, 0] ** 2,
            normalized_xy[:, 0] * normalized_xy[:, 1],
            normalized_xy[:, 1] ** 2,
        )
    )
    feature_center = np.average(quadratic_raw, axis=0, weights=responses)
    quadratic_features = quadratic_raw - feature_center
    coefficients = _weighted_ridge_fit(
        quadratic_features,
        observed_local,
        responses,
        regularization=0.04,
        robust_iterations=4,
    )
    fitted_local = quadratic_features @ coefficients
    fit_error = np.linalg.norm(observed_local - fitted_local, axis=1)
    robust_scale = max(0.5, float(np.median(fit_error) * 2.5))
    inlier_mask = fit_error <= robust_scale
    if int(inlier_mask.sum()) < minimum_tiles:
        return None, {
            "enabled": True,
            "applied": False,
            "reason": "local_deformation_fit_inliers_insufficient",
            "model": "smooth_quadratic_residual_grid",
            "valid_tile_count": len(measurements),
            "inlier_count": int(inlier_mask.sum()),
            "residual_p95_before_px": round(residual_before, 4),
        }
    residual_after = float(np.percentile(fit_error[inlier_mask], 95))
    improvement_fraction = float((residual_before - residual_after) / max(residual_before, 1e-6))
    if improvement_fraction < 0.2:
        return None, {
            "enabled": True,
            "applied": False,
            "reason": "local_deformation_fit_improvement_insufficient",
            "model": "smooth_quadratic_residual_grid",
            "valid_tile_count": len(measurements),
            "inlier_count": int(inlier_mask.sum()),
            "residual_p95_before_px": round(residual_before, 4),
            "residual_p95_after_px": round(residual_after, 4),
            "improvement_fraction": round(improvement_fraction, 6),
        }

    grid_height, grid_width = 5, 7
    grid_y, grid_x = np.meshgrid(
        np.linspace(-1.0, 1.0, grid_height, dtype=np.float64),
        np.linspace(-1.0, 1.0, grid_width, dtype=np.float64),
        indexing="ij",
    )
    grid_raw = np.stack((grid_x**2, grid_x * grid_y, grid_y**2), axis=-1)
    deformation_grid = (grid_raw.reshape(-1, 3) - feature_center) @ coefficients
    deformation_grid = deformation_grid.reshape(grid_height, grid_width, 2)
    max_deformation_px = max(2.0, max(width, height) * max(0.0, float(max_deformation_fraction)))
    grid_magnitude = np.linalg.norm(deformation_grid, axis=2)
    if float(grid_magnitude.max(initial=0.0)) > max_deformation_px:
        return None, {
            "enabled": True,
            "applied": False,
            "reason": "local_deformation_exceeds_bounded_transform_gate",
            "model": "smooth_quadratic_residual_grid",
            "valid_tile_count": len(measurements),
            "inlier_count": int(inlier_mask.sum()),
            "residual_p95_before_px": round(residual_before, 4),
            "residual_p95_after_px": round(residual_after, 4),
            "max_deformation_px": round(float(grid_magnitude.max()), 4),
            "max_allowed_deformation_px": round(max_deformation_px, 4),
        }

    temporal_applied = False
    previous = np.asarray(previous_grid, dtype=np.float32) if previous_grid is not None else None
    if previous is not None and previous.shape == deformation_grid.shape and np.isfinite(previous).all():
        bounded_alpha = min(1.0, max(0.0, float(smoothing_alpha)))
        deformation_grid = previous * (1.0 - bounded_alpha) + deformation_grid * bounded_alpha
        temporal_applied = True
    else:
        bounded_alpha = 1.0
    deformation_grid = deformation_grid.astype(np.float32)
    return deformation_grid, {
        "enabled": True,
        "applied": True,
        "reason": "bounded_local_residual_fit_accepted",
        "model": "smooth_quadratic_residual_grid",
        "grid_shape": [grid_height, grid_width],
        "coarse_displacement_grid_xy": np.round(deformation_grid, 5).tolist(),
        "valid_tile_count": len(measurements),
        "inlier_count": int(inlier_mask.sum()),
        "residual_p95_before_px": round(residual_before, 4),
        "residual_p95_after_px": round(residual_after, 4),
        "improvement_fraction": round(improvement_fraction, 6),
        "max_deformation_px": round(float(np.linalg.norm(deformation_grid, axis=2).max(initial=0.0)), 4),
        "max_allowed_deformation_px": round(max_deformation_px, 4),
        "temporal_smoothing": {
            "applied": temporal_applied,
            "alpha": round(float(bounded_alpha), 4),
        },
    }


def _weighted_ridge_fit(
    features: np.ndarray,
    targets: np.ndarray,
    base_weights: np.ndarray,
    *,
    regularization: float,
    robust_iterations: int,
) -> np.ndarray:
    feature_array = np.asarray(features, dtype=np.float64)
    target_array = np.asarray(targets, dtype=np.float64)
    weights = np.asarray(base_weights, dtype=np.float64).copy()
    identity = np.eye(feature_array.shape[1], dtype=np.float64)
    coefficients: np.ndarray = np.zeros((feature_array.shape[1], target_array.shape[1]), dtype=np.float64)
    for _ in range(max(1, int(robust_iterations))):
        weighted_features = feature_array * weights[:, None]
        system = feature_array.T @ weighted_features + max(0.0, float(regularization)) * identity
        right_hand = feature_array.T @ (target_array * weights[:, None])
        try:
            coefficients = np.linalg.solve(system, right_hand)
        except np.linalg.LinAlgError:
            coefficients = np.linalg.lstsq(system, right_hand, rcond=None)[0]
        residual = np.linalg.norm(target_array - feature_array @ coefficients, axis=1)
        huber_delta = max(0.25, float(np.median(residual) * 2.5))
        robust_weights = np.minimum(1.0, huber_delta / np.maximum(residual, 1e-6))
        weights = np.asarray(base_weights, dtype=np.float64) * robust_weights
    return coefficients


def _warp_affine_with_local_deformation(
    moving: np.ndarray,
    matrix: np.ndarray,
    deformation_grid: np.ndarray,
    *,
    output_size: tuple[int, int],
    prefer_gpu: bool,
    return_device_tensor: bool,
) -> tuple[Any, str, float | None]:
    """Compose affine and smooth local residual warps in one resampling pass."""

    import cv2

    width, height = output_size
    inverse = cv2.invertAffineTransform(np.asarray(matrix, dtype=np.float32))
    if prefer_gpu:
        try:
            import torch
            import torch.nn.functional as torch_functional

            if torch.cuda.is_available():
                device = torch.device("cuda")
                torch.cuda.reset_peak_memory_stats(device)
                with torch.inference_mode():
                    source = torch.from_numpy(np.ascontiguousarray(moving, dtype=np.float32))[None, None].to(
                        device=device,
                        non_blocking=True,
                    )
                    theta = torch.from_numpy(
                        _pixel_inverse_affine_to_normalized_theta(
                            inverse,
                            input_size=(width, height),
                            output_size=(width, height),
                        )
                    )[None].to(device=device)
                    sample_grid = torch_functional.affine_grid(
                        theta,
                        size=[1, 1, height, width],
                        align_corners=True,
                    )
                    coarse = torch.from_numpy(np.ascontiguousarray(np.moveaxis(deformation_grid, -1, 0))[None]).to(
                        device=device
                    )
                    residual = torch_functional.interpolate(
                        coarse,
                        size=(height, width),
                        mode="bilinear",
                        align_corners=True,
                    )
                    inverse_linear = torch.as_tensor(inverse[:, :2], device=device, dtype=torch.float32)
                    correction_x = -(inverse_linear[0, 0] * residual[:, 0] + inverse_linear[0, 1] * residual[:, 1])
                    correction_y = -(inverse_linear[1, 0] * residual[:, 0] + inverse_linear[1, 1] * residual[:, 1])
                    sample_grid[..., 0] += correction_x * (2.0 / max(1, width - 1))
                    sample_grid[..., 1] += correction_y * (2.0 / max(1, height - 1))
                    output = torch_functional.grid_sample(
                        source,
                        sample_grid,
                        mode="bilinear",
                        padding_mode="border",
                        align_corners=True,
                    )
                    torch.cuda.synchronize(device)
                    peak_mb = float(torch.cuda.max_memory_allocated(device) / (1024**2))
                    result = output[0, 0] if return_device_tensor else output[0, 0].cpu().numpy()
                return result, "torch_cuda_affine_local_grid", round(peak_mb, 3)
        except Exception:
            pass

    displacement_x = cv2.resize(
        np.asarray(deformation_grid[..., 0], dtype=np.float32),
        output_size,
        interpolation=cv2.INTER_LINEAR,
    )
    displacement_y = cv2.resize(
        np.asarray(deformation_grid[..., 1], dtype=np.float32),
        output_size,
        interpolation=cv2.INTER_LINEAR,
    )
    output_x = np.arange(width, dtype=np.float32)[None, :]
    output_y = np.arange(height, dtype=np.float32)[:, None]
    local_x = output_x - displacement_x
    local_y = output_y - displacement_y
    map_x = inverse[0, 0] * local_x + inverse[0, 1] * local_y + inverse[0, 2]
    map_y = inverse[1, 0] * local_x + inverse[1, 1] * local_y + inverse[1, 2]
    registered = cv2.remap(
        np.asarray(moving, dtype=np.float32),
        map_x.astype(np.float32, copy=False),
        map_y.astype(np.float32, copy=False),
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return registered, "opencv_cpu_affine_local_grid", None


def _pixel_inverse_affine_to_normalized_theta(
    inverse_matrix: np.ndarray,
    *,
    input_size: tuple[int, int],
    output_size: tuple[int, int],
) -> np.ndarray:
    input_width, input_height = input_size
    output_width, output_height = output_size
    output_denorm = np.asarray(
        [
            [(output_width - 1) * 0.5, 0.0, (output_width - 1) * 0.5],
            [0.0, (output_height - 1) * 0.5, (output_height - 1) * 0.5],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    input_norm = np.asarray(
        [
            [2.0 / max(1, input_width - 1), 0.0, -1.0],
            [0.0, 2.0 / max(1, input_height - 1), -1.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    inverse_homogeneous = np.vstack(
        (
            np.asarray(inverse_matrix, dtype=np.float64),
            np.asarray([0.0, 0.0, 1.0], dtype=np.float64),
        )
    )
    return np.asarray((input_norm @ inverse_homogeneous @ output_denorm)[:2], dtype=np.float32)


def _warp_affine(
    moving: np.ndarray,
    matrix: np.ndarray,
    *,
    output_size: tuple[int, int],
    prefer_gpu: bool,
) -> tuple[np.ndarray, str]:
    import cv2

    if prefer_gpu and hasattr(cv2, "cuda") and hasattr(cv2.cuda, "warpAffine"):
        try:
            if cv2.cuda.getCudaEnabledDeviceCount() > 0:
                source = cv2.cuda_GpuMat()  # type: ignore[attr-defined]
                source.upload(np.asarray(moving, dtype=np.float32))
                warped = cv2.cuda.warpAffine(
                    source,
                    matrix,
                    output_size,
                    flags=cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_REPLICATE,
                )
                return warped.download(), "opencv_cuda"
        except Exception:
            pass
    return (
        cv2.warpAffine(
            np.asarray(moving, dtype=np.float32),
            matrix,
            output_size,
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        ),
        "opencv_cpu",
    )


def _gray_float(image: np.ndarray) -> np.ndarray:
    gray = _gray_raw(image)
    low, high = np.percentile(gray, (1.0, 99.0))
    if high <= low:
        return np.zeros_like(gray, dtype=np.float32)
    return np.clip((gray - low) / (high - low), 0.0, 1.0).astype(np.float32)


def _sampled_percentile_limits(
    image: np.ndarray,
    *,
    lower_percentile: float,
    upper_percentile: float,
    max_sample_side: int = 512,
) -> tuple[float, float]:
    import cv2

    sample = np.asarray(image, dtype=np.float32)
    height, width = sample.shape[:2]
    scale = min(1.0, float(max_sample_side) / float(max(height, width)))
    if scale < 1.0:
        sample = np.asarray(
            cv2.resize(
                sample,
                (max(32, int(round(width * scale))), max(32, int(round(height * scale)))),
                interpolation=cv2.INTER_AREA,
            ),
            dtype=np.float32,
        )
    finite = sample[np.isfinite(sample)]
    if finite.size == 0:
        return 0.0, 0.0
    low, high = np.percentile(finite, (lower_percentile, upper_percentile))
    if high <= low:
        low, high = float(np.min(finite)), float(np.max(finite))
    return float(low), float(high)


def _sampled_percentile_limits_from_cuda(
    image: Any,
    *,
    lower_percentile: float,
    upper_percentile: float,
    max_sample_side: int = 512,
) -> tuple[float, float]:
    height, width = [int(value) for value in image.shape[-2:]]
    stride = max(1, int(np.ceil(max(height, width) / max(32, int(max_sample_side)))))
    sample = image[::stride, ::stride].to(dtype=image.dtype).cpu().numpy()
    return _sampled_percentile_limits(
        np.asarray(sample, dtype=np.float32),
        lower_percentile=lower_percentile,
        upper_percentile=upper_percentile,
        max_sample_side=max_sample_side,
    )


def _gray_raw(image: np.ndarray) -> np.ndarray:
    array = np.asarray(image, dtype=np.float32)
    if array.ndim == 2:
        return array
    return array[..., 0] * 0.299 + array[..., 1] * 0.587 + array[..., 2] * 0.114


def _edge_map(image: np.ndarray) -> np.ndarray:
    import cv2

    normalized = _gray_float(image)
    gx = cv2.Sobel(normalized, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(normalized, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = cv2.magnitude(gx, gy)
    return _gray_float(magnitude)


def _failed_report(reason: str, started: float) -> dict[str, Any]:
    return {
        "method": "adaptive_multiscale_registration_v2",
        "applied": False,
        "reason": reason,
        "translation_xy": [0.0, 0.0],
        "response": None,
        "quality": None,
        "accelerator": "none",
        "elapsed_ms": round((perf_counter() - started) * 1000.0, 3),
    }
