from __future__ import annotations

from pathlib import Path
from typing import Any


def is_dicom_path(path: str | Path) -> bool:
    p = Path(path)
    if p.is_dir():
        return any(child.suffix.lower() == ".dcm" for child in p.rglob("*"))
    return p.suffix.lower() == ".dcm"


def dicom_summary(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    files = list(p.rglob("*.dcm")) if p.is_dir() else ([p] if p.suffix.lower() == ".dcm" else [])
    return {"dicom_file_count": len(files), "metadata_status": "not_loaded"}

