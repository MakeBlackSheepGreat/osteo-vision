from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.warnings import DISCLAIMER_TEXT
from src.reports.writers import write_json, write_markdown


def write_single_case_report(result: dict[str, Any], output_dir: str | Path) -> str:
    case_id = str(result.get("case_id") or "case")
    root = Path(output_dir)
    json_path = root / f"single_case_{case_id}.json"
    payload = dict(result)
    payload["disclaimer"] = DISCLAIMER_TEXT
    payload["report_path"] = str(json_path)
    write_json(json_path, payload)
    write_markdown(
        json_path.with_suffix(".md"),
        "Single Case Report",
        {
            "Summary": {
                "case_id": payload.get("case_id"),
                "status": payload.get("status"),
                "task_type": payload.get("task_type"),
                "class_label": payload.get("class_label"),
                "risk_level": payload.get("risk_level"),
                "probability": payload.get("probability"),
            },
            "Warnings": payload.get("warnings", []),
            "Quantification": payload.get("quantification", {}),
            "Disclaimer": DISCLAIMER_TEXT,
        },
    )
    return str(json_path)

