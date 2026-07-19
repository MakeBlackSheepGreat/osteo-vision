from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

REQUIRED_MANIFEST_COLUMNS = ["case_id", "input_path", "label", "task_type", "input_type"]
OPTIONAL_MANIFEST_COLUMNS = [
    "patient_id",
    "split",
    "fold",
    "label_source",
    "modality",
    "metadata_path",
    "mask_path",
    "bbox",
    "model_hint",
]


def read_manifest(path: str | Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Manifest not found: {p}")
    with p.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [dict(row) for row in reader]
        columns = reader.fieldnames or []
    missing = [column for column in REQUIRED_MANIFEST_COLUMNS if column not in columns]
    info = {
        "manifest_path": str(p),
        "row_count": len(rows),
        "columns": columns,
        "missing_columns": missing,
        "optional_columns_present": [column for column in OPTIONAL_MANIFEST_COLUMNS if column in columns],
        "manifest_version": "v2" if any(column in columns for column in OPTIONAL_MANIFEST_COLUMNS) else "v1",
        "label_availability": "binary" if any(str(row.get("label", "")).strip() for row in rows) else "none",
    }
    if missing:
        raise ValueError(f"Manifest missing required columns: {missing}")
    return rows, info
