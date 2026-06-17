from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.paths import ensure_dir
from src.reports.writers import write_json


def write_training_template_report(task: str, output_dir: str | Path = "artifacts/reports") -> dict[str, Any]:
    report = {
        "task": task,
        "status": "template_only",
        "message": "Training template executed. Replace fixture model logic with task-specific training code.",
    }
    write_json(ensure_dir(output_dir) / f"train_{task}_template.json", report)
    return report

