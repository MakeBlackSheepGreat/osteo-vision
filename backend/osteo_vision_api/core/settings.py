from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_video_manifest_path(root: Path) -> Path:
    inventory = root / "research" / "literature" / "inventory"
    combined_manifests = sorted(inventory.glob("video_library_manifest_*.csv"), key=lambda path: path.name)
    if combined_manifests:
        return combined_manifests[-1]
    download_manifests = sorted(inventory.glob("video_download_manifest_*.csv"), key=lambda path: path.name)
    if download_manifests:
        return download_manifests[-1]
    return inventory / "video_library_manifest.csv"


def _default_ofdvd_manifest_path(root: Path) -> Path:
    inventory = root / "research" / "literature" / "inventory"
    manifests = sorted(inventory.glob("ofdvdnet_video_manifest_*.csv"), key=lambda path: path.name)
    if manifests:
        return manifests[-1]
    return inventory / "ofdvdnet_video_manifest.csv"


def _resolve_project_path(value: str | os.PathLike[str], project_root: Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the Osteo Vision platform API."""

    project_root: Path = _repo_root()
    backend_host: str = "127.0.0.1"
    backend_port: int = 8001
    frontend_host: str = "127.0.0.1"
    frontend_port: int = 5174
    artifact_root: Path = _repo_root() / "artifacts" / "platform"
    case_store_path: Path = _repo_root() / "artifacts" / "platform" / "cases.sqlite"
    annotation_store_path: Path = _repo_root() / "artifacts" / "platform" / "manual_annotations" / "annotations.sqlite"
    promotion_approval_store_path: Path = (
        _repo_root() / "artifacts" / "platform" / "promotion_approvals" / "approvals.sqlite"
    )
    promotion_trusted_keys_path: Path = _repo_root() / "configs" / "security" / "promotion_trusted_keys.json"
    case_store_backend: str = "sqlite"
    job_store_path: Path = _repo_root() / "artifacts" / "platform" / "jobs" / "jobs.json"
    job_execution_mode: str = "background"
    video_manifest_path: Path = _default_video_manifest_path(_repo_root())
    ofdvd_manifest_path: Path = _default_ofdvd_manifest_path(_repo_root())
    inference_config_path: Path = _repo_root() / "configs" / "inference" / "osteo_vision.yml"
    max_active_case_analysis_jobs: int = 1
    max_active_upload_keyframe_jobs: int = 1
    allowed_origins: tuple[str, ...] = (
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
    )
    app_name: str = "Osteo Vision Platform API"


def load_settings() -> Settings:
    root = _repo_root()
    artifact_root = Path(os.environ.get("OSTEO_ARTIFACT_ROOT", root / "artifacts" / "platform"))
    case_store_path = Path(os.environ.get("OSTEO_CASE_STORE_PATH", artifact_root / "cases.sqlite"))
    annotation_store_path = Path(
        os.environ.get(
            "OSTEO_ANNOTATION_STORE_PATH",
            artifact_root / "manual_annotations" / "annotations.sqlite",
        )
    )
    promotion_approval_store_path = Path(
        os.environ.get(
            "OSTEO_PROMOTION_APPROVAL_STORE_PATH",
            artifact_root / "promotion_approvals" / "approvals.sqlite",
        )
    )
    promotion_trusted_keys_path = _resolve_project_path(
        os.environ.get(
            "OSTEO_PROMOTION_TRUSTED_KEYS_PATH",
            root / "configs" / "security" / "promotion_trusted_keys.json",
        ),
        root,
    )
    job_store_path = Path(os.environ.get("OSTEO_JOB_STORE_PATH", artifact_root / "jobs" / "jobs.json"))
    job_execution_mode = os.environ.get("OSTEO_JOB_EXECUTION_MODE", "background").strip().lower()
    if job_execution_mode not in {"background", "worker"}:
        job_execution_mode = "background"
    case_store_backend = os.environ.get("OSTEO_CASE_STORE_BACKEND", "").strip().lower()
    if not case_store_backend:
        case_store_backend = "json" if case_store_path.suffix.lower() == ".json" else "sqlite"
    video_manifest_path = _resolve_project_path(
        os.environ.get("OSTEO_VIDEO_MANIFEST_PATH", _default_video_manifest_path(root)),
        root,
    )
    ofdvd_manifest_path = _resolve_project_path(
        os.environ.get("OSTEO_OFDVD_MANIFEST_PATH", _default_ofdvd_manifest_path(root)),
        root,
    )
    inference_config_path = _resolve_project_path(
        os.environ.get(
            "OSTEO_INFERENCE_CONFIG",
            root / "configs" / "inference" / "osteo_vision.yml",
        ),
        root,
    )
    backend_port = int(os.environ.get("OSTEO_BACKEND_PORT", "8001"))
    frontend_port = int(os.environ.get("OSTEO_FRONTEND_PORT", "5174"))
    max_active_case_analysis_jobs = int(os.environ.get("OSTEO_MAX_ACTIVE_CASE_ANALYSIS_JOBS", "1"))
    max_active_upload_keyframe_jobs = int(os.environ.get("OSTEO_MAX_ACTIVE_UPLOAD_KEYFRAME_JOBS", "1"))
    three_d_runtime_port = int(os.environ.get("OSTEO_THREE_D_RUNTIME_PORT", "5175"))
    origins = os.environ.get(
        "OSTEO_ALLOWED_ORIGINS",
        (
            f"http://localhost:{frontend_port},http://127.0.0.1:{frontend_port},"
            f"http://localhost:{three_d_runtime_port},http://127.0.0.1:{three_d_runtime_port}"
        ),
    )
    return Settings(
        project_root=root,
        backend_port=backend_port,
        frontend_port=frontend_port,
        artifact_root=artifact_root,
        case_store_path=case_store_path,
        annotation_store_path=annotation_store_path,
        promotion_approval_store_path=promotion_approval_store_path,
        promotion_trusted_keys_path=promotion_trusted_keys_path,
        case_store_backend=case_store_backend,
        job_store_path=job_store_path,
        job_execution_mode=job_execution_mode,
        video_manifest_path=video_manifest_path,
        ofdvd_manifest_path=ofdvd_manifest_path,
        inference_config_path=inference_config_path,
        max_active_case_analysis_jobs=max_active_case_analysis_jobs,
        max_active_upload_keyframe_jobs=max_active_upload_keyframe_jobs,
        allowed_origins=tuple(origin.strip() for origin in origins.split(",") if origin.strip()),
    )
