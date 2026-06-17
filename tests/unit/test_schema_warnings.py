from __future__ import annotations

from src.core.schemas import PredictionResult
from src.core.warnings import DISCLAIMER_TEXT, KNOWN_STATUSES, STATUS_COMPLETED, warning


def test_prediction_result_has_required_fields() -> None:
    payload = PredictionResult(case_id="case").to_dict()
    for field in [
        "status",
        "case_id",
        "input_type",
        "task_type",
        "model_version",
        "prediction",
        "probability",
        "score",
        "class_label",
        "risk_level",
        "segmentation_mask",
        "lesion_evidence",
        "quantification",
        "explanation_evidence",
        "warnings",
        "timing_ms",
        "resource_summary",
        "disclaimer_shown",
        "report_path",
        "model_id",
        "model_family",
        "model_provenance",
        "adapter_status",
        "adapter_warnings",
    ]:
        assert field in payload


def test_warning_constants_include_required_statuses() -> None:
    assert STATUS_COMPLETED in KNOWN_STATUSES
    item = warning("low_confidence")
    assert item["code"] == "low_confidence"
    assert "clinical diagnosis" in DISCLAIMER_TEXT
