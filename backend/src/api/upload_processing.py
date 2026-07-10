from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from uuid import uuid4

from fastapi import BackgroundTasks, HTTPException, Request

from backend.src.api.helpers import capacity_exceeded, conflict_from_active_job
from backend.src.services.job_service import JobCapacityError, JobConflictError, JobRegistry
from backend.src.services.job_tasks import run_upload_keyframes_job
from src.core.schemas import InputSummary
from src.core.warnings import warning
from src.io.content_probe import signature_matches_upload_suffix
from src.preprocess.input_validation import validate_input
from src.preprocess.video import extract_keyframes

MAX_IMAGE_UPLOAD_BYTES = 64 * 1024 * 1024
MAX_VIDEO_UPLOAD_BYTES = 1024 * 1024 * 1024
MAX_MEDICAL_3D_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
VIDEO_SUFFIXES = {".mp4"}
MEDICAL_VOLUME_SUFFIXES = {".dcm", ".dicom", ".nii", ".nii.gz", ".nrrd", ".mha", ".mhd"}
SURFACE_MODEL_SUFFIXES = {".stl", ".glb", ".gltf"}
MEDICAL_3D_SUFFIXES = MEDICAL_VOLUME_SUFFIXES | SURFACE_MODEL_SUFFIXES
ALLOWED_SUFFIXES = IMAGE_SUFFIXES | VIDEO_SUFFIXES | MEDICAL_3D_SUFFIXES
DEFAULT_KEYFRAME_COUNT = 5


@dataclass(frozen=True)
class SavedUpload:
    path: Path
    filename: str
    original_filename: str
    suffix: str
    size_bytes: int


@dataclass(frozen=True)
class UploadValidation:
    summary: InputSummary
    content_probe: dict[str, Any]
    warnings: list[dict[str, Any]]


@dataclass(frozen=True)
class KeyframeDispatch:
    report: dict[str, Any] | None = None
    job: dict[str, Any] | None = None


async def save_upload_stream(
    request: Request,
    *,
    upload_dir: Path,
    original_filename: str,
    content_length: int | None,
) -> SavedUpload:
    suffix = _safe_suffix(original_filename)
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail="Unsupported file type")

    max_bytes = _max_upload_bytes(suffix)
    if content_length is not None and content_length > max_bytes:
        raise HTTPException(status_code=413, detail="Uploaded file is too large")

    filename = f"upload_{uuid4().hex[:12]}{suffix}"
    path = upload_dir / filename
    try:
        size = await _write_request_stream(path, request, max_bytes=max_bytes)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    if size == 0:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    return SavedUpload(
        path=path,
        filename=filename,
        original_filename=_safe_name(original_filename),
        suffix=suffix,
        size_bytes=size,
    )


async def _write_request_stream(path: Path, request: Request, *, max_bytes: int) -> int:
    # 流式写入避免 4K MP4 一次性进入内存，同时能在写入过程中及时拦截超限文件。
    size = 0
    with path.open("wb") as f:
        async for chunk in request.stream():
            if not chunk:
                continue
            size += len(chunk)
            if size > max_bytes:
                raise HTTPException(status_code=413, detail="Uploaded file is too large")
            f.write(chunk)
    return size


def validate_saved_upload(uploaded: SavedUpload, content_type: str | None) -> UploadValidation:
    signature_ok, signature_reason, content_probe = signature_matches_upload_suffix(uploaded.path, uploaded.suffix)
    if not signature_ok:
        uploaded.path.unlink(missing_ok=True)
        raise HTTPException(status_code=415, detail=signature_reason)

    summary = validate_input(uploaded.path)
    upload_warnings = _upload_content_type_warnings(uploaded.suffix, content_type)
    if not summary.accepted:
        uploaded.path.unlink(missing_ok=True)
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
    return UploadValidation(summary=summary, content_probe=content_probe, warnings=upload_warnings)


def dispatch_video_keyframes(
    uploaded: SavedUpload,
    *,
    upload_dir: Path,
    jobs: JobRegistry,
    background_tasks: BackgroundTasks,
    keyframe_mode: str,
    max_active_keyframe_jobs: int,
    execution_mode: str,
) -> KeyframeDispatch:
    if uploaded.suffix not in VIDEO_SUFFIXES:
        return KeyframeDispatch()

    keyframe_dir = upload_dir / "keyframes" / uploaded.path.stem
    keyframe_dir.mkdir(parents=True, exist_ok=True)
    if keyframe_mode == "sync":
        report = extract_keyframes(uploaded.path, keyframe_dir, max_frames=DEFAULT_KEYFRAME_COUNT)
        return KeyframeDispatch(report=report)
    if keyframe_mode != "async":
        return KeyframeDispatch()

    job_payload = {
        "source_path": str(uploaded.path),
        "output_dir": str(keyframe_dir),
        "max_frames": DEFAULT_KEYFRAME_COUNT,
    }
    try:
        job = jobs.create(
            kind="upload_keyframe_extraction",
            payload=job_payload,
            max_active=max_active_keyframe_jobs,
            singleton_keys=["source_path"],
        )
    except JobConflictError as exc:
        uploaded.path.unlink(missing_ok=True)
        raise conflict_from_active_job(
            exc,
            code="upload_keyframe_job_already_active",
            message="A keyframe extraction job is already queued or running for this video.",
        ) from exc
    except JobCapacityError as exc:
        uploaded.path.unlink(missing_ok=True)
        raise capacity_exceeded(
            exc,
            code="upload_keyframe_job_capacity_exceeded",
            message="Too many keyframe extraction jobs are queued or running. Try again later.",
        ) from exc

    if execution_mode != "worker":
        background_tasks.add_task(
            _run_keyframe_job,
            jobs,
            job["job_id"],
            uploaded.path,
            keyframe_dir,
            DEFAULT_KEYFRAME_COUNT,
        )
    return KeyframeDispatch(job=job)


def upload_response(
    uploaded: SavedUpload,
    validation: UploadValidation,
    keyframes: KeyframeDispatch,
    content_type: str | None,
) -> dict[str, Any]:
    report = keyframes.report or {}
    job = keyframes.job
    summary = validation.summary
    return {
        "path": str(uploaded.path),
        "filename": uploaded.filename,
        "original_filename": uploaded.original_filename,
        "content_type": content_type,
        "size_bytes": uploaded.size_bytes,
        "input_type": summary.input_type,
        "metadata": {**summary.metadata, "upload_content_probe": validation.content_probe},
        "keyframes": report.get("keyframes", []),
        "keyframe_job_id": job["job_id"] if job else None,
        "keyframe_job_status": job["status"] if job else ("completed" if report else None),
        "warnings": [*summary.warnings, *validation.warnings, *(report.get("warnings", []))],
    }


def _run_keyframe_job(jobs: JobRegistry, job_id: str, source_path: Path, keyframe_dir: Path, max_frames: int) -> None:
    # 上传接口的异步抽帧复用统一任务体，保证后台模式和 worker 模式的状态语义一致。
    run_upload_keyframes_job(jobs, job_id, source_path, keyframe_dir, max_frames, mark_running=True)


def _max_upload_bytes(suffix: str) -> int:
    if suffix in VIDEO_SUFFIXES:
        return MAX_VIDEO_UPLOAD_BYTES
    if suffix in MEDICAL_3D_SUFFIXES:
        return MAX_MEDICAL_3D_UPLOAD_BYTES
    return MAX_IMAGE_UPLOAD_BYTES


def _safe_suffix(filename: str) -> str:
    name = Path(unquote(filename)).name.lower()
    suffix = ".nii.gz" if name.endswith(".nii.gz") else Path(name).suffix.lower()
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
    elif suffix in MEDICAL_VOLUME_SUFFIXES:
        expected = (
            normalized if normalized in {"application/dicom", "application/octet-stream", "application/gzip"} else None
        )
    elif suffix in SURFACE_MODEL_SUFFIXES:
        expected = (
            normalized
            if normalized in {"model/stl", "model/gltf-binary", "model/gltf+json", "application/octet-stream"}
            else None
        )
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
