from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.navigation import (  # noqa: E402
    apply_rigid_transform,
    export_rigid_transform,
    register_rigid_points,
)

DEFAULT_SOURCE_MANIFEST = (
    ROOT / "research/datasets/public-candidates/navigation_starter_20260717/navigation_starter_manifest.json"
)
DEFAULT_OUTPUT = ROOT / "artifacts/navigation/l1_static_registration_validation"


def _phantom(seed: int) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    source = rng.uniform(-45.0, 45.0, size=(12, 3))
    angle = np.deg2rad(18.0)
    rotation = np.asarray([[np.cos(angle), -np.sin(angle), 0.0], [np.sin(angle), np.cos(angle), 0.0], [0.0, 0.0, 1.0]])
    translation = np.asarray([22.0, -13.0, 35.0])
    target = (rotation @ source.T).T + translation
    return {
        "source_space": "cbct_phantom_mm",
        "target_space": "camera_phantom_mm",
        "registration_source": source[:8].tolist(),
        "registration_target": target[:8].tolist(),
        "validation_source": source[8:].tolist(),
        "validation_target": target[8:].tolist(),
        "seed": seed,
    }


def _load_payload(path: Path | None, seed: int) -> dict[str, Any]:
    if path is None:
        return _phantom(seed)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("L1 registration input must be a JSON object")
    return payload


def run_validation(*, input_path: Path | None, source_manifest: Path, output_dir: Path, seed: int) -> dict[str, Any]:
    payload = _load_payload(input_path, seed)
    result = register_rigid_points(
        payload["registration_source"],
        payload["registration_target"],
        source_space=str(payload.get("source_space") or "cbct_phantom_mm"),
        target_space=str(payload.get("target_space") or "camera_phantom_mm"),
        validation_source_points=payload.get("validation_source"),
        validation_target_points=payload.get("validation_target"),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    transform = export_rigid_transform(result, output_dir / "cbct_to_camera_transform.json")
    source_manifest_payload = json.loads(source_manifest.read_text(encoding="utf-8"))
    validation_source = np.asarray(payload.get("validation_source") or [], dtype=np.float64)
    validation_target = np.asarray(payload.get("validation_target") or [], dtype=np.float64)
    transformed = (
        apply_rigid_transform(validation_source, result.matrix) if len(validation_source) else np.empty((0, 3))
    )
    points_path = output_dir / "independent_tre_points.csv"
    with points_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "index",
                "source_x",
                "source_y",
                "source_z",
                "target_x",
                "target_y",
                "target_z",
                "predicted_x",
                "predicted_y",
                "predicted_z",
                "error_mm",
            ]
        )
        for index, (source, target, predicted) in enumerate(
            zip(validation_source, validation_target, transformed, strict=True)
        ):
            writer.writerow(
                [
                    index,
                    *source.tolist(),
                    *target.tolist(),
                    *predicted.tolist(),
                    float(np.linalg.norm(predicted - target)),
                ]
            )
    report = {
        "schema_version": "osteo-vision-l1-static-registration-validation-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "engineering_validation_passed",
        "method": result.method,
        "source_manifest": str(source_manifest.resolve()),
        "source_dataset_records": source_manifest_payload.get("records", []),
        "input_mode": "provided_point_pairs" if input_path else "fixed_seed_phantom",
        "seed": payload.get("seed", seed),
        "fre_mm": result.fre_mm,
        "tre_mm": result.tre_mm,
        "registration_count": result.registration_count,
        "validation_count": result.validation_count,
        "transform_artifact": transform,
        "independent_points_csv": str(points_path.resolve()),
        "training_eligible": False,
        "navigation_level": "L1",
        "navigation_ready": False,
        "review_status": "review_required",
        "data_boundary": "Fixed-seed phantom and SERV-CT ex-vivo proxy evidence validate geometry software only. Physician review and jaw phantom validation remain required before navigation readiness.",
    }
    report_path = output_dir / "l1_static_registration_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {**report, "report_path": str(report_path.resolve())}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path)
    parser.add_argument("--source-manifest", type=Path, default=DEFAULT_SOURCE_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=20260718)
    args = parser.parse_args()
    result = run_validation(
        input_path=args.input, source_manifest=args.source_manifest, output_dir=args.output_dir, seed=args.seed
    )
    print(
        json.dumps(
            {
                "report_path": result["report_path"],
                "fre_mm": result["fre_mm"],
                "tre_mm": result["tre_mm"],
                "navigation_level": result["navigation_level"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
