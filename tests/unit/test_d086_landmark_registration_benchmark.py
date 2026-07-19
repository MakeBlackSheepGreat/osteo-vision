from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

from tools.run_d086_landmark_registration_benchmark import run_benchmark


def _landmark_archive(path: Path) -> None:
    with ZipFile(path, "w") as archive:
        for case_index in range(3):
            objects = []
            for point_index in range(24):
                objects.append(
                    {
                        "class": "Cusp",
                        "coord": [
                            float(point_index),
                            float((point_index * point_index + case_index) % 17),
                            float((point_index * 5 + case_index) % 13),
                        ],
                    }
                )
            archive.writestr(
                f"lower/case_{case_index}/case_{case_index}.json",
                json.dumps({"objects": objects}),
            )


def test_d086_benchmark_uses_real_shape_landmarks_without_exporting_coordinates(
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "landmarks.zip"
    _landmark_archive(archive_path)
    source_manifest = tmp_path / "manifest.json"
    source_manifest.write_text(json.dumps({"records": [{"candidate_id": "D086"}]}), encoding="utf-8")

    report = run_benchmark(
        landmark_zip=archive_path,
        source_manifest=source_manifest,
        output_dir=tmp_path / "output",
        seed=17,
        max_cases=3,
        registration_points=12,
        validation_points=8,
        noise_levels=(0.0, 0.5),
    )

    assert report["status"] == "engineering_validation_passed"
    assert report["case_count"] == 3
    assert report["run_count"] == 6
    assert report["aggregate_metrics"]["0.0"]["tre_proxy_mm"]["max"] < 1e-8
    assert report["navigation_ready"] is False
    assert report["physical_accuracy_claim_allowed"] is False
    assert report["coordinate_scale_verified"] is False
    assert report["derivative_data_exported"] is False
    assert set(report["failure_injection_codes"]) == {
        "insufficient_correspondences",
        "degenerate_registration_geometry",
        "non_finite_points",
    }
    assert Path(report["metrics_csv"]).is_file()
    assert Path(report["report_path"]).is_file()
    assert "coord" not in Path(report["metrics_csv"]).read_text(encoding="utf-8")
