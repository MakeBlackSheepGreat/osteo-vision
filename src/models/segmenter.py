from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.paths import ensure_dir


class FixtureSegmenter:
    def __init__(self, visual_dir: str | Path = "artifacts/visual_evidence") -> None:
        self.visual_dir = Path(visual_dir)

    def predict_mask(self, case_id: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        out_dir = ensure_dir(self.visual_dir)
        path = out_dir / f"{case_id}_fixture_mask.json"
        width = int((metadata or {}).get("width") or 128)
        height = int((metadata or {}).get("height") or 128)
        payload = {
            "case_id": case_id,
            "source": "fixture_segmenter",
            "format": "json_mask_summary",
            "bbox_xyxy": [width // 4, height // 4, width * 3 // 4, height * 3 // 4],
            "area_px": max(1, (width // 2) * (height // 2)),
        }
        path.write_text(__import__("json").dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"path": str(path), **payload}
