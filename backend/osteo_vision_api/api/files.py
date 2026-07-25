from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from backend.osteo_vision_api.core.settings import Settings

PREVIEW_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
VIDEO_SUFFIXES = {".mp4"}
MEDICAL_VOLUME_SUFFIXES = {".dcm", ".dicom", ".nii", ".nii.gz", ".nrrd", ".mha", ".mhd"}
SURFACE_MODEL_SUFFIXES = {".stl", ".glb", ".gltf"}
DOWNLOAD_SUFFIXES = (
    PREVIEW_SUFFIXES | MEDICAL_VOLUME_SUFFIXES | SURFACE_MODEL_SUFFIXES | {".zip", ".json", ".md", ".csv"}
)


def router(settings: Settings) -> APIRouter:
    api = APIRouter()

    @api.get("/files/preview")
    def preview_file(path: str = Query(..., min_length=1)) -> FileResponse:
        """读取平台生成的可视化证据图，只允许访问受信任的 artifact 根目录。"""

        resolved = _resolve_artifact_path(settings, path, not_found_detail="Preview file not found")
        if resolved.suffix.lower() not in PREVIEW_SUFFIXES:
            raise HTTPException(status_code=415, detail="Unsupported preview file type")

        return FileResponse(resolved)

    @api.get("/files/download")
    def download_file(path: str = Query(..., min_length=1)) -> FileResponse:
        """下载证据包和结构化报告文件，路径仍限制在 artifact 根目录内。"""

        resolved = _resolve_artifact_path(settings, path, not_found_detail="Download file not found")
        if _file_suffix(resolved) not in DOWNLOAD_SUFFIXES:
            raise HTTPException(status_code=415, detail="Unsupported download file type")
        return FileResponse(
            resolved,
            media_type="application/octet-stream",
            filename=resolved.name,
        )

    @api.get("/files/video")
    def video_file(path: str = Query(..., min_length=1)) -> FileResponse:
        """播放 MP4 视频流示例，允许 artifact、公开视频库和 manifest 所在目录。"""

        resolved = _resolve_video_path(settings, path, not_found_detail="Video file not found")
        if resolved.suffix.lower() not in VIDEO_SUFFIXES:
            raise HTTPException(status_code=415, detail="Unsupported video file type")
        return FileResponse(
            resolved,
            media_type="video/mp4",
        )

    return api


def _resolve_artifact_path(settings: Settings, path: str, *, not_found_detail: str) -> Path:
    return _resolve_local_path(
        settings,
        path,
        not_found_detail=not_found_detail,
        allowed_roots=_artifact_roots(settings),
        outside_detail="Path is outside artifact roots",
    )


def _resolve_video_path(settings: Settings, path: str, *, not_found_detail: str) -> Path:
    return _resolve_local_path(
        settings,
        path,
        not_found_detail=not_found_detail,
        allowed_roots=_video_roots(settings),
        outside_detail="Path is outside video playback roots",
    )


def _artifact_roots(settings: Settings) -> list[Path]:
    # artifact_root 可能由测试或部署环境覆盖；project_root/artifacts 是本仓库默认运行产物目录。
    return [
        settings.artifact_root.resolve(),
        (settings.project_root / "artifacts").resolve(),
    ]


def _video_roots(settings: Settings) -> list[Path]:
    # 视频播放比图片预览多开放公开候选数据目录，便于前端用真实公开视频做 MP4 视频流示例。
    return [
        *_artifact_roots(settings),
        (settings.project_root / "research" / "datasets" / "public-candidates").resolve(),
        _manifest_parent(settings.video_manifest_path),
        _manifest_parent(settings.ofdvd_manifest_path),
    ]


def _manifest_parent(path: Path) -> Path:
    try:
        return path.resolve(strict=True).parent
    except FileNotFoundError:
        return path.parent.resolve()


def _resolve_local_path(
    settings: Settings,
    path: str,
    *,
    not_found_detail: str,
    allowed_roots: list[Path],
    outside_detail: str,
) -> Path:
    requested = Path(unquote(path))
    if not requested.is_absolute():
        requested = settings.project_root / requested
    try:
        resolved = requested.resolve(strict=True)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=not_found_detail) from exc

    if not any(_is_relative_to(resolved, root) for root in allowed_roots):
        raise HTTPException(status_code=403, detail=outside_detail)
    return resolved


def _file_suffix(path: Path) -> str:
    name = path.name.lower()
    return ".nii.gz" if name.endswith(".nii.gz") else path.suffix.lower()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
