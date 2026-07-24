from __future__ import annotations

from typing import Any


def ct_preprocess_summary(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "hu_conversion": "not_performed_in_fixture",
        "spacing": metadata.get("spacing", "unknown"),
        "windowing": "not_performed_in_fixture",
    }
