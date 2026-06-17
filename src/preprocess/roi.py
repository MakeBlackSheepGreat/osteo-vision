from __future__ import annotations

from typing import Any


def roi_summary(metadata: dict[str, Any]) -> dict[str, Any]:
    width = metadata.get("width")
    height = metadata.get("height")
    return {"roi_available": bool(width and height), "width": width, "height": height}

