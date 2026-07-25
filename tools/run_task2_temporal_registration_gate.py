from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from osteo_vision_core.preprocess.accelerated_fusion import accelerated_normalize_pseudocolor_blend  # noqa: E402
from osteo_vision_core.preprocess.fluorescence import subtract_fluorescence_background  # noqa: E402
from osteo_vision_core.preprocess.task2_protocol import (  # noqa: E402
    TASK2_COMPUTE_BUDGET_MS,
    TASK2_CONTINUOUS_DISPLAY_INTERNAL_BUDGET_MS,
)
from osteo_vision_core.preprocess.temporal_registration import TemporalRegistrationSession  # noqa: E402


def run_gate(
    *,
    white_path: str | Path,
    fluorescence_path: str | Path,
    output_dir: str | Path,
    frames: int = 12,
    shift_x: float = 24.0,
    shift_y: float = -16.0,
    deformation_amplitude_px: float = 8.0,
    display_ready_budget_ms: float = TASK2_CONTINUOUS_DISPLAY_INTERNAL_BUDGET_MS,
) -> dict[str, Any]:
    white_file = Path(white_path).expanduser().resolve()
    fluorescence_file = Path(fluorescence_path).expanduser().resolve()
    root = Path(output_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    with Image.open(white_file) as image:
        white = np.asarray(image.convert("RGB"), dtype=np.uint8).copy()
    with Image.open(fluorescence_file) as image:
        fluorescence = np.asarray(image.convert("L"), dtype=np.uint8).copy()
    corrected, _ = subtract_fluorescence_background(fluorescence.astype(np.float32), percentile=5.0)
    if white.shape[:2] != corrected.shape:
        raise ValueError("Task 2 temporal gate requires equal 4K channel dimensions")

    warmup_session = TemporalRegistrationSession(temporal_smoothing_alpha=0.65)
    warmup_registered, _ = warmup_session.register(
        white,
        _sequence_frame(
            corrected,
            frame_index=0,
            shift_x=shift_x,
            shift_y=shift_y,
            deformation_amplitude_px=deformation_amplitude_px,
        ),
        magnification=2.0,
        working_distance_mm=300.0,
        prefer_gpu=True,
        keep_registered_on_device=True,
    )
    accelerated_normalize_pseudocolor_blend(
        white,
        warmup_registered,
        alpha=0.45,
        colormap="green",
        prefer_gpu=True,
    )
    session = TemporalRegistrationSession(temporal_smoothing_alpha=0.65)
    expected = np.asarray([-shift_x, -shift_y], dtype=np.float32)
    records: list[dict[str, Any]] = []
    overlay_preview: np.ndarray | None = None
    frame_count = max(4, int(frames))
    for index in range(frame_count):
        moving = _sequence_frame(
            corrected,
            frame_index=index,
            shift_x=shift_x,
            shift_y=shift_y,
            deformation_amplitude_px=deformation_amplitude_px,
        )
        first_boundary = max(1, frame_count // 3)
        second_boundary = max(first_boundary + 1, (frame_count * 2) // 3)
        if index < first_boundary:
            magnification, working_distance_mm = 1.3, 200.0
        elif index < second_boundary:
            magnification, working_distance_mm = 17.0, 200.0
        else:
            magnification, working_distance_mm = 17.0, 630.0
        registered, registration = session.register(
            white,
            moving,
            magnification=magnification,
            working_distance_mm=working_distance_mm,
            prefer_gpu=True,
            keep_registered_on_device=True,
        )
        _, _, overlay, acceleration = accelerated_normalize_pseudocolor_blend(
            white,
            registered,
            alpha=0.45,
            colormap="green",
            prefer_gpu=True,
        )
        if overlay_preview is None:
            overlay_preview = overlay
        encode_started = perf_counter()
        encode_ok, encoded_preview = cv2.imencode(
            ".jpg",
            cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR),
            [cv2.IMWRITE_JPEG_QUALITY, 85],
        )
        preview_encode_ms = (perf_counter() - encode_started) * 1000.0
        raw_matrix = np.asarray(registration.get("raw_matrix_2x3"), dtype=np.float32)
        applied_matrix = np.asarray(registration.get("matrix_2x3"), dtype=np.float32)
        raw_translation = raw_matrix[:, 2]
        applied_translation = applied_matrix[:, 2]
        registration_ms = float(registration.get("elapsed_ms") or 0.0)
        gpu_fusion_ms = float(acceleration.get("elapsed_ms") or 0.0)
        compute_ms = registration_ms + gpu_fusion_ms
        display_ready_ms = compute_ms + preview_encode_ms
        local_deformation = _mapping(registration.get("local_deformation"))
        records.append(
            {
                "frame_index": index + 1,
                "magnification": magnification,
                "working_distance_mm": working_distance_mm,
                "registration_applied": registration.get("applied") is True,
                "selected_candidate": registration.get("selected_candidate"),
                "raw_translation_xy": [round(float(value), 4) for value in raw_translation],
                "applied_translation_xy": [round(float(value), 4) for value in applied_translation],
                "translation_error_px": round(float(np.linalg.norm(applied_translation - expected)), 6),
                "registration_ms": registration_ms,
                "gpu_fusion_ms": gpu_fusion_ms,
                "registration_fusion_compute_ms": round(compute_ms, 6),
                "preview_encode_ms": round(preview_encode_ms, 6),
                "display_ready_ms": round(display_ready_ms, 6),
                "preview_encode_succeeded": bool(encode_ok),
                "preview_payload_bytes": int(encoded_preview.size) if encode_ok else 0,
                "compute_budget_missed": compute_ms >= TASK2_COMPUTE_BUDGET_MS,
                "display_budget_missed": display_ready_ms >= float(display_ready_budget_ms),
                "temporal_stabilization": registration.get("temporal_stabilization"),
                "temporal_session": registration.get("temporal_session"),
                "local_residual_p95_px": registration.get("local_residual_p95_px"),
                "local_deformation_applied": local_deformation.get("applied") is True,
                "local_deformation_reason": local_deformation.get("reason"),
                "local_residual_p95_before_px": local_deformation.get("residual_p95_before_px"),
                "local_residual_p95_after_px": local_deformation.get("residual_p95_after_px"),
                "local_deformation_improvement_fraction": local_deformation.get("improvement_fraction"),
                "registration_accelerator": registration.get("accelerator"),
                "registration_peak_gpu_memory_mb": registration.get("local_warp_peak_gpu_memory_mb"),
                "registered_frame_residency": registration.get("registered_frame_residency"),
                "fusion_input_residency": acceleration.get("input_residency"),
                "accelerator": acceleration.get("backend"),
            }
        )

    if overlay_preview is not None:
        Image.fromarray(overlay_preview).save(root / "task2_temporal_overlay_preview.jpg", quality=88)
    raw_jitter = _translation_jitter(records, "raw_translation_xy")
    stabilized_jitter = _translation_jitter(records, "applied_translation_xy")
    local_before = [
        float(item["local_residual_p95_before_px"])
        for item in records
        if item["local_residual_p95_before_px"] is not None
    ]
    local_after = [
        float(item["local_residual_p95_after_px"])
        for item in records
        if item["local_residual_p95_after_px"] is not None
    ]
    deformation_applied_count = sum(item["local_deformation_applied"] for item in records)
    summary: dict[str, Any] = {
        "registration_ms": _summary([item["registration_ms"] for item in records]),
        "gpu_fusion_ms": _summary([item["gpu_fusion_ms"] for item in records]),
        "registration_fusion_compute_ms": _summary([item["registration_fusion_compute_ms"] for item in records]),
        "preview_encode_ms": _summary([item["preview_encode_ms"] for item in records]),
        "display_ready_ms": _summary([item["display_ready_ms"] for item in records]),
        "preview_payload_bytes": _summary([item["preview_payload_bytes"] for item in records]),
        "translation_error_px": _summary([item["translation_error_px"] for item in records]),
        "raw_translation_jitter_px": raw_jitter,
        "stabilized_translation_jitter_px": stabilized_jitter,
        "local_deformation": {
            "applied_frame_count": deformation_applied_count,
            "applied_frame_rate": round(deformation_applied_count / max(1, len(records)), 6),
            "residual_p95_before_px": _summary(local_before) if local_before else None,
            "residual_p95_after_px": _summary(local_after) if local_after else None,
            "all_applied_frames_improved": all(
                float(item["local_residual_p95_after_px"]) < float(item["local_residual_p95_before_px"])
                for item in records
                if item["local_deformation_applied"]
            ),
            "peak_gpu_memory_mb": round(
                max(float(item["registration_peak_gpu_memory_mb"] or 0.0) for item in records),
                3,
            ),
        },
        "zero_copy_handoff_frame_count": sum(
            item["registered_frame_residency"] == "cuda" and item["fusion_input_residency"] == "cuda"
            for item in records
        ),
        "continuous_display": {
            "processed_frame_count": len(records),
            "preview_encode_failure_count": sum(not item["preview_encode_succeeded"] for item in records),
            "compute_budget_ms": TASK2_COMPUTE_BUDGET_MS,
            "compute_budget_miss_count": sum(item["compute_budget_missed"] for item in records),
            "compute_budget_miss_rate": round(
                sum(item["compute_budget_missed"] for item in records) / max(1, len(records)),
                6,
            ),
            "display_ready_budget_ms": float(display_ready_budget_ms),
            "display_budget_miss_count": sum(item["display_budget_missed"] for item in records),
            "display_budget_miss_rate": round(
                sum(item["display_budget_missed"] for item in records) / max(1, len(records)),
                6,
            ),
            "longest_consecutive_compute_budget_misses": _longest_true_run(
                [bool(item["compute_budget_missed"]) for item in records]
            ),
            "longest_consecutive_display_budget_misses": _longest_true_run(
                [bool(item["display_budget_missed"]) for item in records]
            ),
            "scope": "in-memory registration, GPU fusion, and JPEG preview encoding",
        },
    }
    checks = {
        "official_4k_input": white.shape[:2] == (2160, 3840),
        "all_frames_registered": all(item["registration_applied"] for item in records),
        "gpu_backend_used": all(item["accelerator"] == "torch_cuda" for item in records),
        "task2_compute_p95_under_100ms": (summary["registration_fusion_compute_ms"]["p95"] < TASK2_COMPUTE_BUDGET_MS),
        "all_preview_frames_encoded": all(item["preview_encode_succeeded"] for item in records),
        "continuous_display_p95_within_internal_budget": (
            summary["display_ready_ms"]["p95"] < float(display_ready_budget_ms)
        ),
        "no_repeated_compute_budget_misses": (
            summary["continuous_display"]["longest_consecutive_compute_budget_misses"] <= 1
        ),
        "compute_budget_miss_rate_under_1pct": (summary["continuous_display"]["compute_budget_miss_rate"] <= 0.01),
        "translation_error_p95_within_2px": summary["translation_error_px"]["p95"] <= 2.0,
        "temporal_jitter_not_increased": stabilized_jitter <= raw_jitter + 1e-6,
        "local_deformation_compensation_exercised": (summary["local_deformation"]["applied_frame_rate"] >= 0.9),
        "local_deformation_residual_improved": (summary["local_deformation"]["all_applied_frames_improved"]),
        "magnification_change_reset_observed": any(
            _mapping(item.get("temporal_session")).get("context_reset_reason") == "magnification_change"
            for item in records
        ),
        "working_distance_change_reset_observed": any(
            _mapping(item.get("temporal_session")).get("context_reset_reason") == "working_distance_change"
            for item in records
        ),
        "official_optical_extremes_exercised": (
            {float(item["magnification"]) for item in records} == {1.3, 17.0}
            and {float(item["working_distance_mm"]) for item in records} == {200.0, 630.0}
        ),
    }
    checks["pass"] = all(checks.values())
    payload = {
        "schema_version": "osteo-vision-task2-temporal-registration-gate-v3",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "inputs": {
            "white_path": str(white_file),
            "fluorescence_path": str(fluorescence_file),
            "resolution": [3840, 2160],
            "frame_count": frame_count,
            "injected_translation_xy": [shift_x, shift_y],
            "injected_smooth_deformation_amplitude_px": float(deformation_amplitude_px),
            "occlusion": "moving rectangular occlusion with deterministic intensity perturbation",
        },
        "protocol": {
            "temporal_smoothing_alpha": session.temporal_smoothing_alpha,
            "deformation_smoothing_alpha": session.deformation_smoothing_alpha,
            "local_deformation_model": "smooth_quadratic_residual_grid",
            "magnification_sequence": [1.3, 17.0],
            "working_distance_mm_sequence": [200.0, 630.0],
            "task2_latency_scope": "registration estimation and transform plus GPU normalization and fusion",
            "continuous_display_scope": "in-memory compute plus JPEG preview encoding; excludes capture and network",
            "continuous_display_internal_budget_ms": float(display_ready_budget_ms),
        },
        "records": records,
        "summary": summary,
        "checks": checks,
        "claim_boundary": (
            "Internal 4K engineering sequence with deterministic perturbation. Real paired microscope timing, zoom, "
            "working-distance calibration, and tissue deformation require independent validation."
        ),
    }
    output_path = root / "task2_temporal_registration_gate.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def _sequence_frame(
    source: np.ndarray,
    *,
    frame_index: int,
    shift_x: float,
    shift_y: float,
    deformation_amplitude_px: float,
) -> np.ndarray:
    height, width = source.shape
    output_y, output_x = np.mgrid[0:height, 0:width].astype(np.float32)
    normalized_x = (output_x - (width - 1) * 0.5) / max(1.0, (width - 1) * 0.5)
    normalized_y = (output_y - (height - 1) * 0.5) / max(1.0, (height - 1) * 0.5)
    phase = 1.0 + 0.08 * np.sin(frame_index * 0.37)
    local_x = float(deformation_amplitude_px) * phase * (normalized_x**2 - 1.0 / 3.0)
    local_y = float(deformation_amplitude_px) * 0.75 * phase * normalized_x * normalized_y
    shifted = cv2.remap(
        source,
        np.asarray(output_x - float(shift_x) - local_x, dtype=np.float32),
        np.asarray(output_y - float(shift_y) - local_y, dtype=np.float32),
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
    )
    rectangle_width = width // 9
    x0 = width * 2 // 3 + (frame_index % 3) * width // 30
    y0 = height // 12 + (frame_index % 4) * height // 40
    shifted[y0 : y0 + height // 7, x0 : min(width, x0 + rectangle_width)] = 0
    perturbation = np.float32(((frame_index % 5) - 2) * 0.35)
    return np.clip(shifted + perturbation, 0.0, 255.0).astype(np.float32)


def _translation_jitter(records: list[dict[str, Any]], field: str) -> float:
    groups: list[np.ndarray] = []
    optical_contexts = sorted(
        {(float(item["magnification"]), float(item.get("working_distance_mm") or 0.0)) for item in records}
    )
    for magnification, working_distance_mm in optical_contexts:
        values = np.asarray(
            [
                item[field]
                for item in records
                if float(item["magnification"]) == magnification
                and float(item.get("working_distance_mm") or 0.0) == working_distance_mm
            ],
            dtype=np.float32,
        )
        if len(values) > 1:
            groups.append(values)
    if not groups:
        return 0.0
    deviations = np.concatenate([values - np.median(values, axis=0) for values in groups], axis=0)
    return round(float(np.sqrt(np.mean(np.sum(deviations**2, axis=1)))), 6)


def _summary(values: list[float]) -> dict[str, float]:
    ordered = sorted(float(value) for value in values)
    return {
        "p50": round(_percentile(ordered, 50.0), 3),
        "p95": round(_percentile(ordered, 95.0), 3),
        "min": round(min(ordered), 3),
        "max": round(max(ordered), 3),
        "mean": round(statistics.fmean(ordered), 3),
    }


def _percentile(values: list[float], percentile: float) -> float:
    position = (len(values) - 1) * percentile / 100.0
    lower = int(np.floor(position))
    upper = int(np.ceil(position))
    if lower == upper:
        return values[lower]
    weight = position - lower
    return values[lower] * (1.0 - weight) + values[upper] * weight


def _longest_true_run(values: list[bool]) -> int:
    longest = 0
    current = 0
    for value in values:
        current = current + 1 if value else 0
        longest = max(longest, current)
    return longest


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Task 2 temporal 4K registration and fusion gate.")
    parser.add_argument(
        "--white-path",
        default=(
            "research/reports/submission/challenge_cup_report_draft_20260721/assets/sources/" "competition_white_4k.jpg"
        ),
    )
    parser.add_argument(
        "--fluorescence-path",
        default=(
            "research/reports/submission/challenge_cup_report_draft_20260721/assets/sources/" "competition_icg_4k.jpg"
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/platform_smoke/task2_temporal_registration_20260724",
    )
    parser.add_argument("--frames", type=int, default=12)
    parser.add_argument("--deformation-amplitude-px", type=float, default=8.0)
    parser.add_argument(
        "--display-ready-budget-ms",
        type=float,
        default=TASK2_CONTINUOUS_DISPLAY_INTERNAL_BUDGET_MS,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = run_gate(
        white_path=args.white_path,
        fluorescence_path=args.fluorescence_path,
        output_dir=args.output_dir,
        frames=args.frames,
        deformation_amplitude_px=args.deformation_amplitude_px,
        display_ready_budget_ms=args.display_ready_budget_ms,
    )
    print(json.dumps({"checks": payload["checks"], "summary": payload["summary"]}, ensure_ascii=False, indent=2))
    return 0 if payload["checks"]["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
