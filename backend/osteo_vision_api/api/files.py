from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

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
    # These roots are fixed by the immutable runtime settings. Resolving them once
    # avoids repeated filesystem work for every preview/download request.
    artifact_roots = _artifact_roots(settings)
    video_roots = _video_roots(settings, artifact_roots=artifact_roots)

    @api.get("/files/preview")
    def preview_file(path: str = Query(..., min_length=1)) -> FileResponse:
        """读取平台生成的可视化证据图，只允许访问受信任的 artifact 根目录。"""

        resolved = _resolve_local_path(
            settings,
            path,
            not_found_detail="Preview file not found",
            allowed_roots=artifact_roots,
            outside_detail="Path is outside artifact roots",
        )
        if resolved.suffix.lower() not in PREVIEW_SUFFIXES:
            raise HTTPException(status_code=415, detail="Unsupported preview file type")

        return FileResponse(resolved)

    @api.get("/files/download")
    def download_file(path: str = Query(..., min_length=1)) -> FileResponse:
        """下载证据包和结构化报告文件，路径仍限制在 artifact 根目录内。"""

        resolved = _resolve_local_path(
            settings,
            path,
            not_found_detail="Download file not found",
            allowed_roots=artifact_roots,
            outside_detail="Path is outside artifact roots",
        )
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

        resolved = _resolve_local_path(
            settings,
            path,
            not_found_detail="Video file not found",
            allowed_roots=video_roots,
            outside_detail="Path is outside video playback roots",
        )
        if resolved.suffix.lower() not in VIDEO_SUFFIXES:
            raise HTTPException(status_code=415, detail="Unsupported video file type")
        return FileResponse(
            resolved,
            media_type="video/mp4",
        )

    return api


def _artifact_roots(settings: Settings) -> tuple[Path, ...]:
    # artifact_root 可能由测试或部署环境覆盖；运行包的只读 demo_data 也属于受控预览根。
    return tuple(
        dict.fromkeys(
            (
                settings.artifact_root.resolve(strict=False),
                (settings.project_root / "artifacts").resolve(strict=False),
                (settings.project_root / "demo_data").resolve(strict=False),
            )
        )
    )


def _video_roots(
    settings: Settings,
    *,
    artifact_roots: tuple[Path, ...] | None = None,
) -> tuple[Path, ...]:
    # 视频播放比图片预览多开放公开候选数据目录，便于前端用真实公开视频做 MP4 视频流示例。
    roots = artifact_roots if artifact_roots is not None else _artifact_roots(settings)
    return tuple(
        dict.fromkeys(
            (
                *roots,
                (settings.project_root / "research" / "datasets" / "public-candidates").resolve(strict=False),
                _manifest_parent(settings.video_manifest_path),
                _manifest_parent(settings.ofdvd_manifest_path),
            )
        )
    )


def _manifest_parent(path: Path) -> Path:
    try:
        return path.expanduser().resolve(strict=False).parent
    except (OSError, RuntimeError):
        # Broken symlink or an invalid manifest path must degrade to a safe,
        # non-resolved parent instead of preventing the API from starting.
        return path.expanduser().absolute().parent


def _resolve_local_path(
    settings: Settings,
    path: str,
    *,
    not_found_detail: str,
    allowed_roots: Sequence[Path],
    outside_detail: str,
) -> Path:
    try:
        requested = Path(path)
        if not requested.is_absolute():
            requested = settings.project_root / requested
        resolved = requested.resolve(strict=True)
    except (FileNotFoundError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=not_found_detail) from exc

    if not any(_is_relative_to(resolved, root) for root in allowed_roots):
        raise HTTPException(status_code=403, detail=outside_detail)
    if not resolved.is_file():
        raise HTTPException(status_code=404, detail=not_found_detail)
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
