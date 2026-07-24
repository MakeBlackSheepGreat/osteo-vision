from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from osteo_vision_core.navigation import RigidRegistrationError, register_rigid_points  # noqa: E402

DEFAULT_ZIP = (
    ROOT / "research/datasets/public-candidates/navigation_cbct_stl_audit_20260718/"
    "teeth3ds_landmarks/raw/3DTeethLand_landmarks_train.zip"
)
DEFAULT_SOURCE_MANIFEST = (
    ROOT / "research/datasets/public-candidates/navigation_cbct_stl_audit_20260718/" "navigation_cbct_stl_manifest.json"
)
DEFAULT_OUTPUT = ROOT / "artifacts/navigation/d086_landmark_registration_benchmark"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_cases(path: Path, *, minimum_points: int, max_cases: int) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    with ZipFile(path) as archive:
        for info in sorted(archive.infolist(), key=lambda item: item.filename):
            if info.is_dir() or not info.filename.lower().endswith(".json"):
                continue
            encoded = archive.read(info)
            payload = json.loads(encoded.decode("utf-8"))
            objects = payload.get("objects")
            if not isinstance(objects, list):
                continue
            coordinates = [item.get("coord") for item in objects if isinstance(item, dict)]
            try:
                points = np.asarray(coordinates, dtype=np.float64)
            except (TypeError, ValueError):
                continue
            if (
                points.ndim != 2
                or points.shape[1] != 3
                or points.shape[0] < minimum_points
                or not np.isfinite(points).all()
                or np.linalg.matrix_rank(points - points.mean(axis=0)) < 2
            ):
                continue
            cases.append(
                {
                    "entry_name": info.filename,
                    "entry_sha256": hashlib.sha256(encoded).hexdigest(),
                    "points": points,
                }
            )
            if len(cases) >= max_cases:
                break
    if not cases:
        raise ValueError("D086 archive contains no valid landmark cases for registration stress testing.")
    return cases


def _rotation_xyz(angles_degrees: np.ndarray) -> np.ndarray:
    x, y, z = np.deg2rad(angles_degrees)
    rx = np.asarray([[1, 0, 0], [0, np.cos(x), -np.sin(x)], [0, np.sin(x), np.cos(x)]])
    ry = np.asarray([[np.cos(y), 0, np.sin(y)], [0, 1, 0], [-np.sin(y), 0, np.cos(y)]])
    rz = np.asarray([[np.cos(z), -np.sin(z), 0], [np.sin(z), np.cos(z), 0], [0, 0, 1]])
    return rz @ ry @ rx


def _rotation_error_degrees(estimated: np.ndarray, expected: np.ndarray) -> float:
    relative = estimated @ expected.T
    cosine = float(np.clip((np.trace(relative) - 1.0) / 2.0, -1.0, 1.0))
    return float(np.rad2deg(np.arccos(cosine)))


def _summary(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "mean": float(np.mean(array)),
        "median": float(np.median(array)),
        "p95": float(np.percentile(array, 95)),
        "max": float(np.max(array)),
    }


def _failure_injection_codes() -> list[str]:
    scenarios = [
        ([[0, 0, 0], [1, 0, 0]], [[0, 0, 0], [1, 0, 0]]),
        ([[0, 0, 0], [1, 0, 0], [2, 0, 0]], [[1, 1, 1], [2, 1, 1], [3, 1, 1]]),
        (
            [[0, 0, 0], [1, 0, 0], [0, 1, float("nan")]],
            [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
        ),
    ]
    codes: list[str] = []
    for source, target in scenarios:
        try:
            register_rigid_points(
                source,
                target,
                source_space="d086_ios_proxy",
                target_space="simulated_camera_proxy",
            )
        except RigidRegistrationError as exc:
            codes.append(exc.code)
        else:
            codes.append("unsafe_input_unexpectedly_accepted")
    return codes


def run_benchmark(
    *,
    landmark_zip: Path,
    source_manifest: Path,
    output_dir: Path,
    seed: int,
    max_cases: int,
    registration_points: int,
    validation_points: int,
    noise_levels: tuple[float, ...],
) -> dict[str, Any]:
    if registration_points < 3 or validation_points < 1:
        raise ValueError("Registration requires at least 3 fit points and 1 independent TRE point.")
    if not noise_levels or any((not math.isfinite(value) or value < 0) for value in noise_levels):
        raise ValueError("Noise levels must be finite non-negative values.")
    minimum_points = registration_points + validation_points
    cases = _load_cases(landmark_zip, minimum_points=minimum_points, max_cases=max_cases)
    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []
    for case_index, case in enumerate(cases):
        points = np.asarray(case["points"], dtype=np.float64)
        selected = rng.permutation(points.shape[0])[:minimum_points]
        source_registration = points[selected[:registration_points]]
        source_validation = points[selected[registration_points:]]
        rotation = _rotation_xyz(rng.uniform(-25.0, 25.0, size=3))
        translation = rng.uniform(-40.0, 40.0, size=3)
        exact_registration = (rotation @ source_registration.T).T + translation
        exact_validation = (rotation @ source_validation.T).T + translation
        case_hash = hashlib.sha256(f"{seed}:{case['entry_name']}:{case['entry_sha256']}".encode("utf-8")).hexdigest()[
            :20
        ]
        for noise_mm in noise_levels:
            observed_registration = exact_registration + rng.normal(0.0, noise_mm, size=exact_registration.shape)
            result = register_rigid_points(
                source_registration,
                observed_registration,
                source_space="d086_ios_proxy_coordinate",
                target_space="simulated_camera_proxy_coordinate",
                validation_source_points=source_validation,
                validation_target_points=exact_validation,
            )
            rows.append(
                {
                    "case_hash": case_hash,
                    "case_index": case_index,
                    "landmark_count": int(points.shape[0]),
                    "registration_count": result.registration_count,
                    "validation_count": result.validation_count,
                    "noise_proxy_mm": noise_mm,
                    "fre_proxy_mm": result.fre_mm,
                    "tre_proxy_mm": result.tre_mm,
                    "rotation_error_degrees": _rotation_error_degrees(np.asarray(result.rotation), rotation),
                    "translation_error_proxy_mm": float(np.linalg.norm(np.asarray(result.translation) - translation)),
                }
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    rows_path = output_dir / "d086_registration_metrics.csv"
    with rows_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    aggregate: dict[str, Any] = {}
    for noise_mm in noise_levels:
        subset = [row for row in rows if row["noise_proxy_mm"] == noise_mm]
        aggregate[str(noise_mm)] = {
            "case_count": len(subset),
            "fre_proxy_mm": _summary([float(row["fre_proxy_mm"]) for row in subset]),
            "tre_proxy_mm": _summary([float(row["tre_proxy_mm"]) for row in subset]),
            "rotation_error_degrees": _summary([float(row["rotation_error_degrees"]) for row in subset]),
            "translation_error_proxy_mm": _summary([float(row["translation_error_proxy_mm"]) for row in subset]),
        }
    failure_codes = _failure_injection_codes()
    expected_failures = {
        "insufficient_correspondences",
        "degenerate_registration_geometry",
        "non_finite_points",
    }
    zero_noise = aggregate.get("0.0")
    numerical_recovery_passed = bool(
        zero_noise and zero_noise["tre_proxy_mm"]["max"] < 1e-8 and zero_noise["rotation_error_degrees"]["max"] < 1e-5
    )
    report = {
        "schema_version": "osteo-vision-d086-l1-landmark-benchmark-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": (
            "engineering_validation_passed"
            if numerical_recovery_passed and set(failure_codes) == expected_failures
            else "engineering_validation_failed"
        ),
        "source_dataset_id": "D086",
        "source_manifest": str(source_manifest.resolve()),
        "source_manifest_sha256": _sha256(source_manifest),
        "landmark_archive": {
            "path": str(landmark_zip.resolve()),
            "size_bytes": landmark_zip.stat().st_size,
            "sha256": _sha256(landmark_zip),
            "license": "CC BY-NC-ND 4.0",
        },
        "case_count": len(cases),
        "run_count": len(rows),
        "seed": seed,
        "registration_points_per_case": registration_points,
        "independent_tre_points_per_case": validation_points,
        "noise_levels_proxy_mm": list(noise_levels),
        "aggregate_metrics": aggregate,
        "failure_injection_codes": failure_codes,
        "numerical_recovery_passed": numerical_recovery_passed,
        "metrics_csv": str(rows_path.resolve()),
        "metrics_csv_sha256": _sha256(rows_path),
        "coordinate_scale_verified": False,
        "metric_unit": "proxy_mm_under_unverified_one_to_one_dataset_scale",
        "navigation_level": "L1_proxy_engineering_validation",
        "navigation_ready": False,
        "physical_accuracy_claim_allowed": False,
        "target_domain_flag": False,
        "training_eligible": False,
        "review_status": "review_required",
        "derivative_data_exported": False,
        "data_boundary": (
            "D086 provides IOS dental landmark coordinates without verified physical units, CBCT, "
            "jaw-bone surfaces, microscope calibration or real correspondence measurements. Only "
            "aggregate metrics and salted case hashes are exported; no source or transformed landmark "
            "coordinates are redistributed. Results validate software behavior under simulated transforms "
            "and cannot support clinical navigation accuracy claims."
        ),
    }
    report_path = output_dir / "d086_l1_landmark_benchmark.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {**report, "report_path": str(report_path.resolve())}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--landmark-zip", type=Path, default=DEFAULT_ZIP)
    parser.add_argument("--source-manifest", type=Path, default=DEFAULT_SOURCE_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=20260718)
    parser.add_argument("--max-cases", type=int, default=24)
    parser.add_argument("--registration-points", type=int, default=12)
    parser.add_argument("--validation-points", type=int, default=8)
    parser.add_argument("--noise-proxy-mm", type=float, action="append")
    args = parser.parse_args()
    noise_levels = tuple(args.noise_proxy_mm or [0.0, 0.5, 1.0, 2.0])
    result = run_benchmark(
        landmark_zip=args.landmark_zip,
        source_manifest=args.source_manifest,
        output_dir=args.output_dir,
        seed=args.seed,
        max_cases=args.max_cases,
        registration_points=args.registration_points,
        validation_points=args.validation_points,
        noise_levels=noise_levels,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "case_count": result["case_count"],
                "run_count": result["run_count"],
                "report_path": result["report_path"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["status"] == "engineering_validation_passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
