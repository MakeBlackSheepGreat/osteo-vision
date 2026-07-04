from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from backend.src.core.settings import Settings

PREVIEW_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
DOWNLOAD_SUFFIXES = PREVIEW_SUFFIXES | {".zip", ".json", ".md", ".csv", ".dcm"}


def router(settings: Settings) -> APIRouter:
    api = APIRouter()

    @api.get("/files/preview")
    def preview_file(path: str = Query(..., min_length=1)) -> FileResponse:
        """Serve local visual evidence files produced under the project artifact roots."""

        resolved = _resolve_artifact_path(settings, path, not_found_detail="Preview file not found")
        if resolved.suffix.lower() not in PREVIEW_SUFFIXES:
            raise HTTPException(status_code=415, detail="Unsupported preview file type")

        return FileResponse(resolved)

    @api.get("/files/download")
    def download_file(path: str = Query(..., min_length=1)) -> FileResponse:
        """Download evidence bundle files produced under artifact roots."""

        resolved = _resolve_artifact_path(settings, path, not_found_detail="Download file not found")
        if resolved.suffix.lower() not in DOWNLOAD_SUFFIXES:
            raise HTTPException(status_code=415, detail="Unsupported download file type")
        return FileResponse(
            resolved,
            media_type="application/octet-stream",
            filename=resolved.name,
        )

    return api


def _resolve_artifact_path(settings: Settings, path: str, *, not_found_detail: str) -> Path:
    requested = Path(unquote(path))
    if not requested.is_absolute():
        requested = settings.project_root / requested
    try:
        resolved = requested.resolve(strict=True)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=not_found_detail) from exc

    allowed_roots = [
        settings.artifact_root.resolve(),
        (settings.project_root / "artifacts").resolve(),
    ]
    if not any(_is_relative_to(resolved, root) for root in allowed_roots):
        raise HTTPException(status_code=403, detail="Path is outside artifact roots")
    return resolved


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
