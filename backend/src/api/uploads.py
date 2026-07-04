from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request

from backend.src.core.settings import Settings
from backend.src.services.job_service import JobCapacityError, JobConflictError, JobRegistry
from src.core.paths import ensure_dir
from src.core.warnings import warning
from src.io.content_probe import signature_matches_upload_suffix
from src.preprocess.input_validation import validate_input
from src.preprocess.video import extract_keyframes

MAX_IMAGE_UPLOAD_BYTES = 64 * 1024 * 1024
MAX_VIDEO_UPLOAD_BYTES = 1024 * 1024 * 1024
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
VIDEO_SUFFIXES = {".mp4"}
ALLOWED_SUFFIXES = IMAGE_SUFFIXES | VIDEO_SUFFIXES


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

        suffix = _safe_suffix(x_filename)
        if suffix not in ALLOWED_SUFFIXES:
            raise HTTPException(status_code=415, detail="Unsupported file type")
        max_bytes = MAX_VIDEO_UPLOAD_BYTES if suffix in VIDEO_SUFFIXES else MAX_IMAGE_UPLOAD_BYTES
        if content_length is not None and content_length > max_bytes:
            raise HTTPException(status_code=413, detail="Uploaded file is too large")

        upload_dir = ensure_dir(settings.artifact_root / "uploads")
        filename = f"upload_{uuid4().hex[:12]}{suffix}"
        path = upload_dir / filename
        size = 0
        try:
            with path.open("wb") as f:
                async for chunk in request.stream():
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > max_bytes:
                        raise HTTPException(status_code=413, detail="Uploaded file is too large")
                    f.write(chunk)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        if size == 0:
            path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        signature_ok, signature_reason, content_probe = signature_matches_upload_suffix(path, suffix)
        if not signature_ok:
            path.unlink(missing_ok=True)
            raise HTTPException(status_code=415, detail=signature_reason)

        summary = validate_input(path)
        upload_warnings = _upload_content_type_warnings(suffix, content_type)
        if not summary.accepted:
            path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "upload_content_unreadable",
                    "message": "Uploaded file could not be decoded or validated.",
                    "reason": summary.reason,
                    "input_type": summary.input_type,
                    "warnings": summary.warnings,
                },
            )
        keyframe_report: dict[str, Any] | None = None
        keyframe_job: dict[str, Any] | None = None
        if suffix in VIDEO_SUFFIXES and summary.accepted:
            keyframe_dir = ensure_dir(upload_dir / "keyframes" / path.stem)
            if keyframe_mode == "sync":
                keyframe_report = extract_keyframes(path, keyframe_dir, max_frames=5)
            elif keyframe_mode == "async":
                job_payload = {"source_path": str(path), "output_dir": str(keyframe_dir), "max_frames": 5}
                try:
                    keyframe_job = jobs.create(
                        kind="upload_keyframe_extraction",
                        payload=job_payload,
                        max_active=max_active_keyframe_jobs,
                        singleton_keys=["source_path"],
                    )
                except JobConflictError as exc:
                    path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "code": "upload_keyframe_job_already_active",
                            "message": "A keyframe extraction job is already queued or running for this video.",
                            "active_job_id": exc.active_job.get("job_id"),
                        },
                    ) from exc
                except JobCapacityError as exc:
                    path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=429,
                        detail={
                            "code": "upload_keyframe_job_capacity_exceeded",
                            "message": "Too many keyframe extraction jobs are queued or running. Try again later.",
                            "active_count": exc.active_count,
                            "max_active": exc.max_active,
                        },
                    ) from exc
                if execution_mode != "worker":
                    background_tasks.add_task(_run_keyframe_job, jobs, keyframe_job["job_id"], path, keyframe_dir, 5)
        return {
            "path": str(path),
            "filename": filename,
            "original_filename": _safe_name(x_filename),
            "content_type": content_type,
            "size_bytes": size,
            "input_type": summary.input_type,
            "metadata": {**summary.metadata, "upload_content_probe": content_probe},
            "keyframes": (keyframe_report or {}).get("keyframes", []),
            "keyframe_job_id": keyframe_job["job_id"] if keyframe_job else None,
            "keyframe_job_status": (
                keyframe_job["status"] if keyframe_job else ("completed" if keyframe_report else None)
            ),
            "warnings": [*summary.warnings, *upload_warnings, *((keyframe_report or {}).get("warnings", []))],
        }

    @api.get("/uploads/jobs/{job_id}")
    def get_upload_job(job_id: str) -> dict[str, Any]:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Upload job not found")
        return job

    return api


def _run_keyframe_job(jobs: JobRegistry, job_id: str, source_path: Path, keyframe_dir: Path, max_frames: int) -> None:
    jobs.mark_running(job_id)
    jobs.update_progress(job_id, phase="extract_keyframes", percent=20, message="Extracting representative MP4 keyframes.")
    try:
        report = extract_keyframes(source_path, keyframe_dir, max_frames=max_frames)
    except Exception as exc:
        jobs.mark_failed(job_id, str(exc))
        return
    jobs.update_progress(job_id, phase="write_keyframes", percent=90, message="Writing keyframe manifest and previews.")
    if report.get("keyframes"):
        jobs.mark_completed(job_id, report)
    else:
        warnings = report.get("warnings", [])
        message = str(warnings[0].get("message")) if warnings else "No keyframes were extracted."
        jobs.mark_failed(job_id, message, report)


def _safe_suffix(filename: str) -> str:
    suffix = Path(unquote(filename)).suffix.lower()
    return suffix or ".png"


def _safe_name(filename: str) -> str:
    name = Path(unquote(filename)).name
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name) or "upload.png"


def _upload_content_type_warnings(suffix: str, content_type: str | None) -> list[dict[str, Any]]:
    if not content_type:
        return []
    normalized = content_type.split(";", 1)[0].strip().lower()
    expected = "video/mp4" if suffix in VIDEO_SUFFIXES else None
    if suffix in {".jpg", ".jpeg"}:
        expected = "image/jpeg"
    elif suffix == ".png":
        expected = "image/png"
    elif suffix == ".bmp":
        expected = "image/bmp"
    elif suffix in {".tif", ".tiff"}:
        expected = "image/tiff"
    if expected is None or normalized == expected:
        return []
    return [
        warning(
            "upload_content_type_mismatch",
            f"Upload header content-type {normalized} does not match expected {expected}.",
            False,
            expected_content_type=expected,
            received_content_type=normalized,
        )
    ]
