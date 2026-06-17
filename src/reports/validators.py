from __future__ import annotations

from typing import Any

from src.core.warnings import DISCLAIMER_TEXT

REQUIRED_RESULT_FIELDS = {
    "status",
    "case_id",
    "input_type",
    "task_type",
    "model_version",
    "prediction",
    "warnings",
    "disclaimer_shown",
    "report_path",
}


def validate_prediction_result(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_RESULT_FIELDS - set(payload))
    if missing:
        errors.append(f"missing fields: {missing}")
    if payload.get("disclaimer") and payload.get("disclaimer") != DISCLAIMER_TEXT:
        errors.append("unexpected disclaimer text")
    if not isinstance(payload.get("warnings", []), list):
        errors.append("warnings must be a list")
    return errors

