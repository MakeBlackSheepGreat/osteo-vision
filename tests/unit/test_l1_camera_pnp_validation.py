from __future__ import annotations

from pathlib import Path

from tools.run_l1_camera_pnp_validation import run_validation


def test_l1_camera_pnp_validation_records_thresholds_and_failure_injections(
    tmp_path: Path,
) -> None:
    report = run_validation(output_dir=tmp_path / "pnp", seed=7)

    assert report["status"] == "engineering_validation_passed"
    assert report["navigation_ready"] is False
    assert report["navigation_level"] == "L0"
    assert report["review_status"] == "review_required"
    assert report["camera_registration"]["validation_reprojection_rmse_px"] < 1.0
    assert report["failure_injections"] == {
        "out_of_frame_landmark": "camera_image_point_out_of_bounds",
        "incomplete_validation_pair": "camera_validation_pair_incomplete",
    }
    assert Path(report["transform_artifact"]["path"]).is_file()
    assert Path(report["transform_artifact"]["sha256_path"]).is_file()
    assert Path(report["report_path"]).is_file()
