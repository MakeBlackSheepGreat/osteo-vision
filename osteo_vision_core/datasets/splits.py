from __future__ import annotations

from collections import defaultdict
from typing import Any


def patient_leakage_report(
    rows: list[dict[str, Any]], patient_key: str = "patient_id", split_key: str = "split"
) -> dict[str, Any]:
    assignments: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        patient_id = str(row.get(patient_key) or "")
        split = str(row.get(split_key) or "")
        if patient_id and split:
            assignments[patient_id].add(split)
    leaked = {patient: sorted(splits) for patient, splits in assignments.items() if len(splits) > 1}
    return {"leakage_detected": bool(leaked), "leaked_patients": leaked}
