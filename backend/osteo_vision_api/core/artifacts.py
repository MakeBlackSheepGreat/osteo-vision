from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from osteo_vision_core.core.paths import ensure_dir


def artifact_root(base_dir: str | Path) -> Path:
    return ensure_dir(base_dir)


def case_artifact_dir(base_dir: str | Path, case_id: str) -> Path:
    return ensure_dir(Path(base_dir) / case_id)


def manifest_dir(base_dir: str | Path) -> Path:
    return ensure_dir(Path(base_dir) / "manifests")


def preview_dir(base_dir: str | Path) -> Path:
    return ensure_dir(Path(base_dir) / "previews")


def checksum_for_file(path: str | Path) -> str:
    p = Path(path)
    digest = hashlib.sha256()
    with p.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_record(
    kind: str, path: str | Path, *, checksum: str | None = None, extra: dict[str, Any] | None = None
) -> dict[str, Any]:
    p = Path(path)
    return {
        "kind": kind,
        "path": str(p),
        "checksum": checksum or (checksum_for_file(p) if p.exists() and p.is_file() else None),
        "exists": p.exists(),
        "size_bytes": p.stat().st_size if p.exists() and p.is_file() else None,
        "extra": extra or {},
    }
