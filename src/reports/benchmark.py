from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.schemas import BenchmarkReport
from src.core.warnings import DISCLAIMER_TEXT
from src.reports.writers import write_json, write_markdown


def write_benchmark_report(report: BenchmarkReport, output_dir: str | Path, threshold_analysis: dict[str, Any]) -> str:
    root = Path(output_dir)
    report_path = root / "benchmark_report.json"
    payload = report.to_dict()
    payload["disclaimer"] = DISCLAIMER_TEXT
    write_json(report_path, payload)
    write_markdown(
        root / "threshold_analysis.md",
        "Threshold Analysis",
        {
            "Analysis": threshold_analysis,
            "Disclaimer": DISCLAIMER_TEXT,
        },
    )
    return str(report_path)

