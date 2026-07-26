from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from osteo_vision_core.preprocess.fluorescence import fuse_white_light_fluorescence  # noqa: E402


def run_gate(
    *,
    white_path: str | Path,
    fluorescence_path: str | Path,
    output_dir: str | Path,
    runs: int = 10,
    shift_x: int = 24,
    shift_y: int = -16,
    max_registration_fusion_p95_ms: float = 100.0,
    max_full_evidence_p95_ms: float = 1500.0,
) -> dict[str, Any]:
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    white = Path(white_path).resolve()
    fluorescence = Path(fluorescence_path).resolve()
    shifted_path = root / "inputs" / "competition_icg_4k_shifted_occluded.jpg"
    shifted_path.parent.mkdir(parents=True, exist_ok=True)
    _build_shifted_occluded_input(
        fluorescence,
        shifted_path,
        shift_x=shift_x,
        shift_y=shift_y,
    )

    warmup = fuse_white_light_fluorescence(
        white,
        shifted_path,
        root / "warmup",
        case_id="fusion_4k_warmup",
        registration="adaptive_multiscale",
        prefer_gpu=True,
    )
    records: list[dict[str, Any]] = []
    for index in range(max(1, int(runs))):
        report = fuse_white_light_fluorescence(
            white,
            shifted_path,
            root / "runs" / f"run_{index + 1:02d}",
            case_id=f"fusion_4k_{index + 1:02d}",
            registration="adaptive_multiscale",
            prefer_gpu=True,
        )
        registration = dict(report["fusion"]["registration_details"])
        acceleration = dict(report["fusion"]["acceleration"])
        performance = dict(report["fusion"]["performance"])
        translation = registration.get("translation_xy") or [0.0, 0.0]
        registration_ms = float(registration.get("elapsed_ms") or performance["registration_ms"])
        gpu_fusion_ms = float(acceleration["elapsed_ms"])
        records.append(
            {
                "run": index + 1,
                "registration_applied": registration.get("applied") is True,
                "selected_candidate": registration.get("selected_candidate"),
                "valid_tile_count": registration.get("valid_tile_count"),
                "quality": registration.get("quality"),
                "translation_xy": translation,
                "translation_error_px": round(
                    float(np.linalg.norm(np.asarray(translation) - np.asarray([-shift_x, -shift_y]))),
                    6,
                ),
                "registration_ms": registration_ms,
                "gpu_fusion_ms": gpu_fusion_ms,
                "registration_fusion_compute_ms": _task2_compute_ms(registration_ms, gpu_fusion_ms),
                "full_evidence_ms": float(performance["total_ms"]),
                "accelerator": acceleration.get("backend"),
                "peak_gpu_memory_mb": acceleration.get("peak_gpu_memory_mb"),
                "report_path": report["outputs"]["report_path"],
            }
        )

    summary = {
        "registration_ms": _summary([item["registration_ms"] for item in records]),
        "gpu_fusion_ms": _summary([item["gpu_fusion_ms"] for item in records]),
        "registration_fusion_compute_ms": _summary([item["registration_fusion_compute_ms"] for item in records]),
        "full_evidence_ms": _summary([item["full_evidence_ms"] for item in records]),
        "translation_error_px": _summary([item["translation_error_px"] for item in records]),
    }
    checks = {
        "official_4k_input": _image_size(white) == (3840, 2160) and _image_size(shifted_path) == (3840, 2160),
        "all_registration_runs_applied": all(item["registration_applied"] for item in records),
        "occlusion_robust_tiles_available": all(int(item["valid_tile_count"] or 0) >= 3 for item in records),
        "translation_error_within_2px": summary["translation_error_px"]["max"] <= 2.0,
        "gpu_backend_used": all(item["accelerator"] == "torch_cuda" for item in records),
        "task2_registration_fusion_p95_under_100ms": (
            summary["registration_fusion_compute_ms"]["p95"] < max_registration_fusion_p95_ms
        ),
        "full_evidence_p95_within_gate": summary["full_evidence_ms"]["p95"] <= max_full_evidence_p95_ms,
    }
    checks["pass"] = all(checks.values())
    payload = {
        "schema_version": "osteo-vision-competition-fusion-performance-gate-v2",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "inputs": {
            "white_path": str(white),
            "fluorescence_path": str(fluorescence),
            "derived_shifted_occluded_path": str(shifted_path),
            "size": [3840, 2160],
            "injected_translation_xy": [shift_x, shift_y],
            "occlusion": "fixed upper-right rectangular exclusion",
        },
        "protocol": {
            "warmup_runs_excluded": 1,
            "timed_runs": len(records),
            "registration": "adaptive_multiscale_registration_v2",
            "fusion_accelerator": "torch_cuda_with_numpy_fallback",
            "thresholds": {
                "max_registration_fusion_p95_ms_exclusive": max_registration_fusion_p95_ms,
                "max_full_evidence_p95_ms": max_full_evidence_p95_ms,
                "max_translation_error_px": 2.0,
            },
            "task2_latency_scope": (
                "registration estimation and transform plus GPU normalization, pseudocolor mapping, and alpha blend"
            ),
            "excluded_from_task2_100ms": [
                "file_decode_resize",
                "background_correction",
                "evidence_encoding",
                "disk_write",
                "network_transport",
                "task3_ai_inference",
            ],
        },
        "warmup": {
            "registration": warmup["fusion"]["registration_details"],
            "acceleration": warmup["fusion"]["acceleration"],
            "performance": warmup["fusion"]["performance"],
        },
        "records": records,
        "summary": summary,
        "checks": checks,
        "claim_boundary": (
            "The 100 ms gate follows the detailed Task 2 wording supplied by the project team. The local formal "
            "competition PDF requires real-time display but contains no numeric latency. This is internal engineering "
            "acceptance on a traced 4K synthetic competition-format pair with injected shift and occlusion. Real "
            "microscope synchronization, transport latency, and geometric accuracy remain independently verifiable items."
        ),
    }
    output_path = root / "competition_fusion_performance_gate.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def _build_shifted_occluded_input(source: Path, destination: Path, *, shift_x: int, shift_y: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        gray = np.asarray(image.convert("L"), dtype=np.uint8)
    height, width = gray.shape
    matrix = np.asarray([[1.0, 0.0, float(shift_x)], [0.0, 1.0, float(shift_y)]], dtype=np.float32)
    shifted = cv2.warpAffine(gray, matrix, (width, height), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    shifted[height // 10 : height // 4, width * 3 // 4 : width * 19 // 20] = 0
    Image.fromarray(shifted).save(destination, quality=92, optimize=False)


def _summary(values: list[float]) -> dict[str, float]:
    ordered = sorted(float(value) for value in values)
    return {
        "p50": round(_percentile(ordered, 50.0), 3),
        "p95": round(_percentile(ordered, 95.0), 3),
        "min": round(min(ordered), 3),
        "max": round(max(ordered), 3),
        "mean": round(statistics.fmean(ordered), 3),
    }


def _task2_compute_ms(registration_ms: float, gpu_fusion_ms: float) -> float:
    return round(float(registration_ms) + float(gpu_fusion_ms), 6)


def _percentile(values: list[float], percentile: float) -> float:
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * percentile / 100.0
    lower = int(np.floor(position))
    upper = int(np.ceil(position))
    if lower == upper:
        return values[lower]
    weight = position - lower
    return values[lower] * (1.0 - weight) + values[upper] * weight


def _image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the internal 4K registration and accelerated-fusion gate.")
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
        default="artifacts/platform_smoke/competition_fusion_performance_20260724",
    )
    parser.add_argument("--runs", type=int, default=10)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = run_gate(
        white_path=args.white_path,
        fluorescence_path=args.fluorescence_path,
        output_dir=args.output_dir,
        runs=args.runs,
    )
    print(json.dumps({"checks": payload["checks"], "summary": payload["summary"]}, ensure_ascii=False, indent=2))
    return 0 if payload["checks"]["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
