from __future__ import annotations

from pathlib import Path
from typing import Any

from osteo_vision_core.core.paths import ensure_dir
from osteo_vision_core.reports.writers import write_json


def write_gradcam_placeholder(case_id: str, output_dir: str | Path = "artifacts/visual_evidence") -> dict[str, Any]:
    path = ensure_dir(output_dir) / f"{case_id}_gradcam_placeholder.json"
    payload = {"case_id": case_id, "type": "gradcam_placeholder", "available": False}
    write_json(path, payload)
    return {"path": str(path), **payload}
