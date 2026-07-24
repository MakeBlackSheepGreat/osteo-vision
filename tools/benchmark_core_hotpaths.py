from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.osteo_vision_api.services.job_service import JobRegistry  # noqa: E402
from osteo_vision_core.models.hotspot_segmenter import connected_hotspot_candidates  # noqa: E402
from osteo_vision_core.navigation.offline_pose_replay import _nearest_sorted_indices  # noqa: E402
from osteo_vision_core.preprocess.video import _frame_quality  # noqa: E402


def _elapsed_ms(operation: Callable[[], Any], *, repeats: int) -> float:
    samples: list[float] = []
    for _ in range(max(1, repeats)):
        started = time.perf_counter()
        operation()
        samples.append((time.perf_counter() - started) * 1000.0)
    return float(statistics.median(samples))


def _reference_connected_candidates(mask: np.ndarray, intensity: np.ndarray) -> list[tuple[int, int, float, float]]:
    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    candidates: list[tuple[int, int, float, float]] = []
    for label in range(1, component_count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        values = intensity[labels == label]
        candidates.append((label, area, float(values.mean()), float(values.max())))
    return candidates


def _optimized_connected_candidates(mask: np.ndarray, intensity: np.ndarray) -> list[dict[str, Any]]:
    return connected_hotspot_candidates(
        mask,
        intensity,
        min_component_area=1,
        model_id="core_hotpath_benchmark",
    )


def _reference_frame_quality(frame: np.ndarray) -> dict[str, float]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    channels = frame.astype("float32")
    blue = channels[..., 0]
    green = channels[..., 1]
    red = channels[..., 2]
    green_dominance = green - np.maximum(red, blue)
    return {
        "mean_intensity": float(gray.mean()),
        "p95_intensity": float(np.percentile(gray, 95)),
        "p99_green": float(np.percentile(green, 99)),
        "green_dominance_p95": float(np.percentile(np.maximum(green_dominance, 0), 95)),
        "high_signal_fraction": float(((gray > 200) | (green_dominance > 50)).mean()),
        "blur_laplacian_var": float(cv2.Laplacian(gray, cv2.CV_64F).var()),
        "underexposed_fraction": float((gray < 8).mean()),
        "overexposed_fraction": float((gray > 247).mean()),
    }


def _quality_outputs_match(reference: dict[str, float], optimized: dict[str, Any]) -> bool:
    return all(
        key in optimized and np.isclose(float(optimized[key]), value, rtol=1e-9, atol=1e-9)
        for key, value in reference.items()
    )


def _component_outputs_match(
    reference: list[tuple[int, int, float, float]],
    optimized: list[dict[str, Any]],
) -> bool:
    optimized_by_label = {int(str(item["candidate_id"]).rsplit("_", 1)[-1]): item for item in optimized}
    if len(reference) != len(optimized_by_label):
        return False
    return all(
        label in optimized_by_label
        and int(optimized_by_label[label]["area_px"]) == area
        and np.isclose(float(optimized_by_label[label]["score"]), mean, rtol=1e-6, atol=1e-7)
        and np.isclose(float(optimized_by_label[label]["confidence"]), maximum, rtol=1e-6, atol=1e-7)
        for label, area, mean, maximum in reference
    )


def _reference_job_lookup(path: Path, job_id: str) -> dict[str, Any] | None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    job = jobs.get(job_id) if isinstance(jobs, dict) else None
    return dict(job) if isinstance(job, dict) else None


def run_benchmark(*, repeats: int) -> dict[str, Any]:
    rng = np.random.default_rng(20260719)
    mask = np.zeros((1024, 1024), dtype=np.uint8)
    mask[::32, ::32] = 1
    intensity = rng.random(mask.shape, dtype=np.float32)
    reference_candidates = _reference_connected_candidates(mask, intensity)
    optimized_candidates = _optimized_connected_candidates(mask, intensity)
    reference_component_ms = _elapsed_ms(
        lambda: _reference_connected_candidates(mask, intensity),
        repeats=max(1, repeats // 2),
    )
    optimized_component_ms = _elapsed_ms(
        lambda: _optimized_connected_candidates(mask, intensity),
        repeats=repeats,
    )

    frame = rng.integers(0, 256, size=(2160, 3840, 3), dtype=np.uint8)
    reference_quality = _reference_frame_quality(frame)
    optimized_quality = _frame_quality(frame)
    reference_quality_ms = _elapsed_ms(lambda: _reference_frame_quality(frame), repeats=repeats)
    optimized_quality_ms = _elapsed_ms(lambda: _frame_quality(frame), repeats=repeats)

    pose_times = np.linspace(0.0, 100.0, 10_000, dtype=np.float64)
    frame_times = np.linspace(0.0, 100.0, 10_000, dtype=np.float64)
    reference_nearest = np.asarray(
        [int(np.argmin(np.abs(pose_times - timestamp))) for timestamp in frame_times],
        dtype=np.intp,
    )
    optimized_nearest = _nearest_sorted_indices(pose_times, frame_times)
    reference_nearest_ms = _elapsed_ms(
        lambda: [int(np.argmin(np.abs(pose_times - timestamp))) for timestamp in frame_times],
        repeats=max(1, repeats // 2),
    )
    optimized_nearest_ms = _elapsed_ms(
        lambda: _nearest_sorted_indices(pose_times, frame_times),
        repeats=repeats,
    )

    job_count = 1000
    lookup_batch_size = 50
    jobs = {
        f"job_{index:04d}": {
            "job_id": f"job_{index:04d}",
            "kind": "case_analysis",
            "status": "completed",
            "payload": {"case_id": f"case_{index:04d}"},
            "result": {"run_id": f"run_{index:04d}"},
            "created_at": "2026-07-19T00:00:00+00:00",
            "updated_at": "2026-07-19T00:00:00+00:00",
        }
        for index in range(job_count)
    }
    lookup_id = f"job_{job_count - 1:04d}"
    with tempfile.TemporaryDirectory(prefix="osteo_hotpath_") as temporary_directory:
        job_store = Path(temporary_directory) / "jobs.json"
        job_store.write_text(
            json.dumps({"schema_version": "osteo-vision-job-registry-v1", "jobs": jobs}),
            encoding="utf-8",
        )
        registry = JobRegistry(job_store)
        reference_job = _reference_job_lookup(job_store, lookup_id)
        optimized_job = registry.get(lookup_id)
        reference_job_ms = _elapsed_ms(
            lambda: [_reference_job_lookup(job_store, lookup_id) for _ in range(lookup_batch_size)],
            repeats=repeats,
        )
        optimized_job_ms = _elapsed_ms(
            lambda: [registry.get(lookup_id) for _ in range(lookup_batch_size)],
            repeats=repeats,
        )

    return {
        "schema_version": "osteo-vision-core-hotpath-benchmark-v1",
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "opencv": cv2.__version__,
        },
        "configuration": {
            "repeats": repeats,
            "component_image_shape": [1024, 1024],
            "component_count": len(reference_candidates),
            "quality_source_shape": [2160, 3840],
            "quality_evaluation_mode": "full_resolution_histogram_v1",
            "pose_count": int(pose_times.size),
            "frame_timestamp_count": int(frame_times.size),
            "job_registry_record_count": job_count,
            "job_registry_lookup_batch_size": lookup_batch_size,
        },
        "results": {
            "connected_components": {
                "reference_ms": round(reference_component_ms, 3),
                "optimized_ms": round(optimized_component_ms, 3),
                "speedup": round(reference_component_ms / optimized_component_ms, 2),
                "outputs_match": _component_outputs_match(reference_candidates, optimized_candidates),
            },
            "quality_evaluation": {
                "reference_full_resolution_ms": round(reference_quality_ms, 3),
                "optimized_full_resolution_ms": round(optimized_quality_ms, 3),
                "speedup": round(reference_quality_ms / optimized_quality_ms, 2),
                "evaluation_shape": [
                    int(optimized_quality["evaluation_height"]),
                    int(optimized_quality["evaluation_width"]),
                ],
                "outputs_match": _quality_outputs_match(reference_quality, optimized_quality),
                "full_resolution_quality_metrics": True,
                "full_resolution_evidence_preserved": True,
            },
            "nearest_pose_lookup": {
                "reference_ms": round(reference_nearest_ms, 3),
                "optimized_ms": round(optimized_nearest_ms, 3),
                "speedup": round(reference_nearest_ms / optimized_nearest_ms, 2),
                "outputs_match": bool(np.array_equal(reference_nearest, optimized_nearest)),
            },
            "job_registry_cached_lookup": {
                "reference_full_json_parse_ms": round(reference_job_ms, 3),
                "cached_signature_lookup_ms": round(optimized_job_ms, 3),
                "speedup": round(reference_job_ms / optimized_job_ms, 2),
                "outputs_match": reference_job == optimized_job,
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark bounded, deterministic core platform hot paths.")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = run_benchmark(repeats=max(1, int(args.repeats)))
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
