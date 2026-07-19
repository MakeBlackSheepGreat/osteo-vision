from __future__ import annotations

from typing import Any


def postprocess_mask_summary(mask: dict[str, Any], threshold: float = 0.5) -> dict[str, Any]:
    return {"threshold": threshold, "largest_component": False, "source": mask.get("source", "fixture")}
