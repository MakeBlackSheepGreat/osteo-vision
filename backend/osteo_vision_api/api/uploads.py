from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request

from backend.osteo_vision_api.api.upload_processing import (
    dispatch_video_keyframes,
    save_upload_stream,
    upload_response,
    validate_saved_upload,
)
from backend.osteo_vision_api.core.settings import Settings
from backend.osteo_vision_api.services.job_service import JobRegistry
from osteo_vision_core.core.paths import ensure_dir


def router(
    settings: Settings,
    jobs: JobRegistry,
    *,
    max_active_keyframe_jobs: int = 1,
    execution_mode: str = "background",
) -> APIRouter:
    api = APIRouter()

    @api.post("/uploads/raw")
    async def upload_raw_file(
        request: Request,
        background_tasks: BackgroundTasks,
        keyframe_mode: str = Query(default="async", pattern="^(async|sync|none)$"),
        x_filename: str = Header(default="upload.png"),
        content_type: str | None = Header(default=None),
        content_length: int | None = Header(default=None),
    ) -> dict[str, Any]:
        """保存浏览器选择的官方设备 MP4/JPEG 等文件，返回后端可读取路径和摘要。"""

        upload_dir = ensure_dir(settings.artifact_root / "uploads")
        uploaded = await save_upload_stream(
            request,
            upload_dir=upload_dir,
            original_filename=x_filename,
            content_length=content_length,
        )
        validation = validate_saved_upload(uploaded, content_type)
        keyframes = dispatch_video_keyframes(
            uploaded,
            upload_dir=upload_dir,
            jobs=jobs,
            background_tasks=background_tasks,
            keyframe_mode=keyframe_mode,
            max_active_keyframe_jobs=max_active_keyframe_jobs,
            execution_mode=execution_mode,
        )
        return upload_response(uploaded, validation, keyframes, content_type)

    @api.get("/uploads/jobs/{job_id}")
    def get_upload_job(job_id: str) -> dict[str, Any]:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Upload job not found")
        return job

    return api
