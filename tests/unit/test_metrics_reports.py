from __future__ import annotations

import json

from osteo_vision_core.metrics.classification import classification_metrics, threshold_sweep
from osteo_vision_core.reports.single_case import write_single_case_report


def test_classification_metrics_and_threshold_sweep() -> None:
    metrics = classification_metrics([0, 1], [0.2, 0.8], threshold=0.5)
    assert metrics["accuracy"] == 1.0
    sweep = threshold_sweep([0, 1], [0.2, 0.8])
    assert sweep["available"]


def test_single_case_report_contains_disclaimer(tmp_path) -> None:
    path = write_single_case_report({"case_id": "x", "status": "completed", "warnings": []}, tmp_path)
    payload = json.loads((tmp_path / "single_case_x.json").read_text(encoding="utf-8"))
    assert payload["report_path"] == path
    assert "clinical diagnosis" in payload["disclaimer"]
