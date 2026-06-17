from __future__ import annotations

from pathlib import Path
from typing import Any

from src.reports.writers import write_csv


QUANTIFICATION_FIELDS = [
    "case_id",
    "run_id",
    "roi_id",
    "threshold",
    "mean_intensity",
    "max_intensity",
    "p95_intensity",
    "positive_area_px",
    "positive_area_fraction",
    "review_state",
]


def write_quantification_csv(path: str | Path, rows: list[dict[str, Any]]) -> str:
    return write_csv(path, rows, QUANTIFICATION_FIELDS)
