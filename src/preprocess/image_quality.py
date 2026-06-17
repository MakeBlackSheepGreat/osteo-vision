from __future__ import annotations

from pathlib import Path


def assess_basic_quality(path: str | Path, input_type: str) -> tuple[bool, str]:
    p = Path(path)
    if not p.exists():
        return False, "path does not exist"
    if p.is_file() and p.stat().st_size == 0:
        return False, "file is empty"
    if input_type == "unknown":
        return False, "unsupported input type"
    return True, ""

