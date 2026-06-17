from __future__ import annotations

from pathlib import Path
from typing import Any

from src.reports.writers import write_json


def write_overlay_placeholder(path: str | Path, payload: dict[str, Any]) -> str:
    return write_json(path, {"type": "overlay_placeholder", **payload})

