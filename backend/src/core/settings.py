from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the local V1 platform service."""

    project_root: Path = _repo_root()
    backend_host: str = "127.0.0.1"
    backend_port: int = 8001
    frontend_host: str = "127.0.0.1"
    frontend_port: int = 5174
    artifact_root: Path = _repo_root() / "artifacts" / "platform"
    case_store_path: Path = _repo_root() / "artifacts" / "platform" / "cases.json"
    allowed_origins: tuple[str, ...] = ("http://localhost:5174", "http://127.0.0.1:5174")
    app_name: str = "Osteo Vision Platform API"


def load_settings() -> Settings:
    root = _repo_root()
    artifact_root = Path(os.environ.get("OSTEO_ARTIFACT_ROOT", root / "artifacts" / "platform"))
    case_store_path = Path(os.environ.get("OSTEO_CASE_STORE_PATH", artifact_root / "cases.json"))
    backend_port = int(os.environ.get("OSTEO_BACKEND_PORT", "8001"))
    frontend_port = int(os.environ.get("OSTEO_FRONTEND_PORT", "5174"))
    origins = os.environ.get(
        "OSTEO_ALLOWED_ORIGINS",
        f"http://localhost:{frontend_port},http://127.0.0.1:{frontend_port}",
    )
    return Settings(
        project_root=root,
        backend_port=backend_port,
        frontend_port=frontend_port,
        artifact_root=artifact_root,
        case_store_path=case_store_path,
        allowed_origins=tuple(origin.strip() for origin in origins.split(",") if origin.strip()),
    )
