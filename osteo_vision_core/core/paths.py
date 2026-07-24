from __future__ import annotations

from pathlib import Path
from typing import Any


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_path(path: str | Path, *, base: str | Path | None = None) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    return (Path(base) if base else project_root()) / p


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
