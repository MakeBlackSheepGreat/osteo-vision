from __future__ import annotations

from pathlib import Path


def is_nifti_path(path: str | Path) -> bool:
    name = Path(path).name.lower()
    return name.endswith(".nii") or name.endswith(".nii.gz")
