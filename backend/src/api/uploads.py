from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request

from backend.src.core.settings import Settings
from src.core.paths import ensure_dir

MAX_UPLOAD_BYTES = 32 * 1024 * 1024
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


def router(settings: Settings) -> APIRouter:
    api = APIRouter()

    @api.post("/uploads/raw")
    async def upload_raw_image(
        request: Request,
        x_filename: str = Header(default="upload.png"),
        content_type: str | None = Header(default=None),
    ) -> dict[str, str | int | None]:
        """保存浏览器选择的本地图像，返回后端可读取的真实文件路径。"""

        body = await request.body()
        if not body:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
        if len(body) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Uploaded file is too large")

        suffix = _safe_suffix(x_filename)
        if suffix not in ALLOWED_SUFFIXES:
            raise HTTPException(status_code=415, detail="Unsupported image file type")

        upload_dir = ensure_dir(settings.artifact_root / "uploads")
        filename = f"upload_{uuid4().hex[:12]}{suffix}"
        path = upload_dir / filename
        path.write_bytes(body)
        return {
            "path": str(path),
            "filename": filename,
            "original_filename": _safe_name(x_filename),
            "content_type": content_type,
            "size_bytes": len(body),
        }

    return api


def _safe_suffix(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return suffix or ".png"


def _safe_name(filename: str) -> str:
    name = Path(filename).name
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name) or "upload.png"
