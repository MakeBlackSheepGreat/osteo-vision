from __future__ import annotations

import json
from pathlib import Path

from tools.run_l1_static_registration_validation import run_validation


def test_l1_static_registration_validation_writes_traceable_proxy_evidence(tmp_path: Path) -> None:
    source_manifest = tmp_path / "navigation.json"
    source_manifest.write_text(
        json.dumps({"records": [{"candidate_id": "D076", "training_eligible": False}]}), encoding="utf-8"
    )

    report = run_validation(input_path=None, source_manifest=source_manifest, output_dir=tmp_path / "output", seed=7)

    assert report["status"] == "engineering_validation_passed"
    assert report["fre_mm"] < 1e-10
    assert report["tre_mm"] is not None and report["tre_mm"] < 1e-10
    assert report["navigation_level"] == "L1"
    assert report["navigation_ready"] is False
    assert report["review_status"] == "review_required"
    assert report["training_eligible"] is False
    assert Path(report["transform_artifact"]["path"]).is_file()
    assert Path(report["transform_artifact"]["sha256_path"]).is_file()
    assert Path(report["independent_points_csv"]).is_file()
    assert Path(report["report_path"]).is_file()
