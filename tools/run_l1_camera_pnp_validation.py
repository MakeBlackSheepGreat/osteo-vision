from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.navigation.camera_registration import (  # noqa: E402
    CameraRegistrationError,
    compose_transforms,
    export_camera_transform,
    register_camera_pnp,
)


def run_validation(
    *,
    output_dir: Path,
    seed: int = 20260718,
    reprojection_threshold_px: float = 1.0,
) -> dict[str, Any]:
    output = output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    objects = np.asarray(
        [
            [-35, -25, 0],
            [35, -25, 0],
            [35, 25, 0],
            [-35, 25, 0],
            [-25, -15, 22],
            [25, 15, 28],
            [-12, 20, 35],
            [18, -18, 32],
            [0, -30, 16],
            [0, 30, 20],
            [-28, 0, 12],
            [28, 0, 18],
        ],
        dtype=np.float64,
    )
    camera_matrix = np.asarray(
        [[1530.0, 0.0, 960.0], [0.0, 1525.0, 540.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    distortion = np.asarray([0.008, -0.004, 0.0004, -0.0003, 0.0])
    rotation_vector = np.asarray([0.06, -0.035, 0.025], dtype=np.float64)
    translation = np.asarray([4.0, -6.0, 480.0], dtype=np.float64)
    projected, _ = cv2.projectPoints(
        objects,
        rotation_vector,
        translation,
        camera_matrix,
        distortion,
    )
    pixels = projected.reshape(-1, 2)
    noisy_pixels = pixels + rng.normal(0.0, 0.18, size=pixels.shape)

    result = register_camera_pnp(
        objects[:8],
        noisy_pixels[:8],
        camera_matrix=camera_matrix,
        distortion_coefficients=distortion,
        image_size_px=(1920, 1080),
        object_space="phantom_reference_mm",
        camera_space="camera_optical",
        intrinsics_id="synthetic_scope_4x_250mm_v1",
        magnification=4.0,
        working_distance_mm=250.0,
        validation_object_points=objects[8:],
        validation_image_points=noisy_pixels[8:],
    )
    reference_from_cbct = np.eye(4, dtype=np.float64)
    reference_from_cbct[:3, 3] = [8.0, -3.0, 5.0]
    composed = compose_transforms(result.matrix, reference_from_cbct)
    transform = export_camera_transform(
        result,
        output / "cbct_to_camera_transform.json",
        composed_matrix=composed,
        composed_source_space="cbct_phantom_mm",
    )

    injected_failures: dict[str, str] = {}
    bad_pixels = noisy_pixels[:8].copy()
    bad_pixels[0, 0] = 2048.0
    try:
        register_camera_pnp(
            objects[:8],
            bad_pixels,
            camera_matrix=camera_matrix,
            distortion_coefficients=distortion,
            image_size_px=(1920, 1080),
            object_space="phantom_reference_mm",
            intrinsics_id="synthetic_scope_4x_250mm_v1",
            magnification=4.0,
            working_distance_mm=250.0,
        )
    except CameraRegistrationError as exc:
        injected_failures["out_of_frame_landmark"] = exc.code
    try:
        register_camera_pnp(
            objects[:8],
            noisy_pixels[:8],
            camera_matrix=camera_matrix,
            distortion_coefficients=distortion,
            image_size_px=(1920, 1080),
            object_space="phantom_reference_mm",
            intrinsics_id="synthetic_scope_4x_250mm_v1",
            magnification=4.0,
            working_distance_mm=250.0,
            validation_object_points=objects[8:],
        )
    except CameraRegistrationError as exc:
        injected_failures["incomplete_validation_pair"] = exc.code

    validation_error = result.validation_reprojection_rmse_px
    expected_failures = {
        "out_of_frame_landmark": "camera_image_point_out_of_bounds",
        "incomplete_validation_pair": "camera_validation_pair_incomplete",
    }
    passed = (
        validation_error is not None
        and validation_error <= reprojection_threshold_px
        and injected_failures == expected_failures
    )
    report = {
        "schema_version": "osteo-vision-l1-camera-pnp-validation-v1",
        "status": "engineering_validation_passed" if passed else "engineering_validation_failed",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "target_domain_flag": False,
        "training_eligible": False,
        "navigation_ready": False,
        "navigation_level": "L0",
        "requested_navigation_level": "L1",
        "review_status": "review_required",
        "validation_scope": "synthetic_static_phantom_known_camera_pose",
        "camera_registration": result.to_manifest(),
        "thresholds": {
            "validation_reprojection_rmse_px": reprojection_threshold_px,
            "source": "internal_synthetic_phantom_engineering_gate_pending_physical_validation",
        },
        "transform_artifact": transform,
        "failure_injections": injected_failures,
        "medical_boundary": (
            "Synthetic static-phantom camera registration evidence only. It does not establish physical "
            "navigation accuracy, patient registration accuracy, a resection boundary, or intraoperative readiness."
        ),
    }
    report_path = output / "l1_camera_pnp_validation.json"
    _write_json(report_path, report)
    report["report_path"] = str(report_path)
    report["report_sha256"] = _sha256(report_path)
    return report


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the safety-bounded L1 calibrated camera PnP validation.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/navigation/l1_camera_pnp_validation"),
    )
    parser.add_argument("--seed", type=int, default=20260718)
    parser.add_argument("--reprojection-threshold-px", type=float, default=1.0)
    args = parser.parse_args()
    report = run_validation(
        output_dir=args.output_dir,
        seed=args.seed,
        reprojection_threshold_px=args.reprojection_threshold_px,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "engineering_validation_passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
