from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_video_manifest_path(root: Path) -> Path:
    combined = root / "research" / "literature" / "inventory" / "video_library_manifest_20260704.csv"
    if combined.exists():
        return combined
    return root / "research" / "literature" / "inventory" / "video_download_manifest_20260703.csv"


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the local V1 platform service."""

    project_root: Path = _repo_root()
    backend_host: str = "127.0.0.1"
    backend_port: int = 8001
    frontend_host: str = "127.0.0.1"
    frontend_port: int = 5174
    artifact_root: Path = _repo_root() / "artifacts" / "platform"
    case_store_path: Path = _repo_root() / "artifacts" / "platform" / "cases.sqlite"
    case_store_backend: str = "sqlite"
    job_store_path: Path = _repo_root() / "artifacts" / "platform" / "jobs" / "jobs.json"
    job_execution_mode: str = "background"
    video_manifest_path: Path = _default_video_manifest_path(_repo_root())
    max_active_case_analysis_jobs: int = 1
    max_active_upload_keyframe_jobs: int = 1
    allowed_origins: tuple[str, ...] = ("http://localhost:5174", "http://127.0.0.1:5174")
    app_name: str = "Osteo Vision Platform API"


def load_settings() -> Settings:
    root = _repo_root()
    artifact_root = Path(os.environ.get("OSTEO_ARTIFACT_ROOT", root / "artifacts" / "platform"))
    case_store_path = Path(os.environ.get("OSTEO_CASE_STORE_PATH", artifact_root / "cases.sqlite"))
    job_store_path = Path(os.environ.get("OSTEO_JOB_STORE_PATH", artifact_root / "jobs" / "jobs.json"))
    job_execution_mode = os.environ.get("OSTEO_JOB_EXECUTION_MODE", "background").strip().lower()
    if job_execution_mode not in {"background", "worker"}:
        job_execution_mode = "background"
    case_store_backend = os.environ.get("OSTEO_CASE_STORE_BACKEND", "").strip().lower()
    if not case_store_backend:
        case_store_backend = "json" if case_store_path.suffix.lower() == ".json" else "sqlite"
    video_manifest_path = Path(
        os.environ.get(
            "OSTEO_VIDEO_MANIFEST_PATH",
            _default_video_manifest_path(root),
        )
    )
    backend_port = int(os.environ.get("OSTEO_BACKEND_PORT", "8001"))
    frontend_port = int(os.environ.get("OSTEO_FRONTEND_PORT", "5174"))
    max_active_case_analysis_jobs = int(os.environ.get("OSTEO_MAX_ACTIVE_CASE_ANALYSIS_JOBS", "1"))
    max_active_upload_keyframe_jobs = int(os.environ.get("OSTEO_MAX_ACTIVE_UPLOAD_KEYFRAME_JOBS", "1"))
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
        case_store_backend=case_store_backend,
        job_store_path=job_store_path,
        job_execution_mode=job_execution_mode,
        video_manifest_path=video_manifest_path,
        max_active_case_analysis_jobs=max_active_case_analysis_jobs,
        max_active_upload_keyframe_jobs=max_active_upload_keyframe_jobs,
        allowed_origins=tuple(origin.strip() for origin in origins.split(",") if origin.strip()),
    )
