from __future__ import annotations

from osteo_vision_core.datasets.manifests import read_manifest
from osteo_vision_core.datasets.splits import patient_leakage_report


def test_v2_manifest_reads_optional_columns() -> None:
    rows, info = read_manifest("tests/fixtures/benchmark_manifest_v2.csv")
    assert len(rows) == 3
    assert info["manifest_version"] == "v2"
    assert "patient_id" in info["optional_columns_present"]


def test_patient_leakage_report_detects_cross_split_patient() -> None:
    report = patient_leakage_report(
        [
            {"patient_id": "p1", "split": "train"},
            {"patient_id": "p1", "split": "val"},
        ]
    )
    assert report["leakage_detected"]
