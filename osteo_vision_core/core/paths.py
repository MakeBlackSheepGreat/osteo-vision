from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def project_root() -> Path:
    configured_root = os.environ.get("OSTEO_PROJECT_ROOT", "").strip()
    if configured_root:
        return Path(configured_root).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def resolve_path(path: str | Path, *, base: str | Path | None = None) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    if base is None:
        redirected = _resolve_writable_artifact_path(p)
        if redirected is not None:
            return redirected
    return (Path(base) if base else project_root()) / p


def _resolve_writable_artifact_path(path: Path) -> Path | None:
    """Redirect generated reports and visual evidence to the user data root.

    Packaged desktop resources are read-only (and may live on optical media),
    while analysis output must remain writable. Model checkpoints and bundled
    three-dimensional references intentionally keep resolving from the project
    root and therefore are not included in this redirect.
    """

    configured_root = os.environ.get("OSTEO_ARTIFACT_ROOT", "").strip()
    if not configured_root:
        return None
    parts = tuple(part.lower() for part in path.parts)
    for namespace in (("artifacts", "reports"), ("artifacts", "visual_evidence")):
        if len(parts) < len(namespace) or parts[: len(namespace)] != namespace:
            continue
        suffix = path.parts[len(namespace) :]
        return Path(configured_root).expanduser().resolve() / namespace[1] / Path(*suffix)
    return None


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def artifact_dirs(config: dict[str, Any]) -> dict[str, Path]:
    reports = config.get("reports", {})
    return {
        "reports": ensure_dir(resolve_path(reports.get("output_dir", "artifacts/reports"))),
        "visual": ensure_dir(resolve_path(reports.get("visual_dir", "artifacts/visual_evidence"))),
        "release": ensure_dir(resolve_path("artifacts/release")),
    }
