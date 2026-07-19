from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.paths import ensure_dir
from src.reports.writers import write_json


def write_gradcam_placeholder(case_id: str, output_dir: str | Path = "artifacts/visual_evidence") -> dict[str, Any]:
    path = ensure_dir(output_dir) / f"{case_id}_gradcam_placeholder.json"
    payload = {"case_id": case_id, "type": "gradcam_placeholder", "available": False}
    write_json(path, payload)
    return {"path": str(path), **payload}
