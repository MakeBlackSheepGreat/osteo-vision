from __future__ import annotations

from typing import Any


class FixtureDetector:
    def detect(self, metadata: dict[str, Any] | None = None, max_candidates: int = 3) -> list[dict[str, Any]]:
        width = int((metadata or {}).get("width") or 128)
        height = int((metadata or {}).get("height") or 128)
        candidates = [
            {
                "candidate_id": "candidate_1",
                "bbox_xyxy": [width // 3, height // 3, width * 2 // 3, height * 2 // 3],
                "score": 0.75,
                "source": "fixture_detector",
            }
        ]
        return candidates[:max_candidates]
