from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.osteo_vision_api.core.settings import Settings
from backend.osteo_vision_api.domains.cases.repository import CaseRepository
from backend.osteo_vision_api.domains.cases.schemas import AnalysisRunCreateRequest
from backend.osteo_vision_api.services.analysis_service import AnalysisService
from backend.osteo_vision_api.services.cbct_modeling_service import build_cbct_surface_model
from backend.osteo_vision_api.services.job_service import JobRegistry
from backend.osteo_vision_api.services.offline_pose_replay_service import OfflinePoseReplayRequestError, OfflinePoseReplayService
from backend.osteo_vision_api.services.static_registration_service import StaticRegistrationRequestError, StaticRegistrationService
from backend.osteo_vision_api.services.three_d_case_evidence import (
    persist_l1_registration_result,
    persist_l2_pose_replay_result,
    persist_three_d_modeling_result,
)
from osteo_vision_core.navigation.camera_registration import CameraRegistrationError
from osteo_vision_core.navigation.offline_pose_replay import OfflinePoseReplayError
from osteo_vision_core.navigation.rigid_registration import RigidRegistrationError
from osteo_vision_core.preprocess.video import extract_keyframes


def run_case_analysis_job(
    jobs: JobRegistry,
    job_id: str,
    repo: CaseRepository,
    service: AnalysisService,
    case_id: str,
    request: AnalysisRunCreateRequest,
    *,
    mark_running: bool = True,
) -> dict[str, Any]:
    """执行病例分析任务，供 FastAPI BackgroundTasks 和本地 worker 共用。"""

    if mark_running:
        jobs.mark_running(job_id)
    if jobs.is_canceled(job_id):
        return _job_result(job_id, "case_analysis", "canceled")

    jobs.update_progress(job_id, phase="load_case", percent=15, message="Loading case inputs and analysis request.")
    case = repo.get(case_id)
    if case is None:
        jobs.mark_failed(job_id, "Case not found")
        return _job_result(job_id, "case_analysis", "failed", error="Case not found")

    try:
        jobs.update_progress(job_id, phase="analyze", percent=35, message="Running fluorescence and AI analysis.")
        updated = service.start_analysis(case, request.selected_input_ids, request.parameters, request.roi_hints)
    except Exception as exc:
        jobs.mark_failed(job_id, str(exc))
        return _job_result(job_id, "case_analysis", "failed", error=str(exc))
    if jobs.is_canceled(job_id):
        return _job_result(job_id, "case_analysis", "canceled")

    latest = updated.analysis_runs[-1] if updated.analysis_runs else None
    result = {
        "case_id": updated.case_id,
        "case_status": updated.status,
        "run_id": latest.run_id if latest else None,
        "run_status": latest.status if latest else None,
    }
    jobs.update_progress(
        job_id, phase="persist_results", percent=90, message="Persisting analysis results and artifacts."
    )
    if latest and latest.status == "failed":
        jobs.mark_failed(job_id, "Analysis run failed.", result)
    else:
        jobs.mark_completed(job_id, result)
    completed = jobs.get(job_id) or {}
    return {"job_id": job_id, "kind": "case_analysis", "status": completed.get("status"), "result": result}


def run_upload_keyframes_job(
    jobs: JobRegistry,
    job_id: str,
    source_path: Path,
    output_dir: Path,
    max_frames: int,
    *,
    mark_running: bool = True,
) -> dict[str, Any]:
    """执行 MP4 关键帧抽取任务，保证上传接口和本地 worker 使用同一套完成/失败语义。"""

    if mark_running:
        jobs.mark_running(job_id)
    if jobs.is_canceled(job_id):
        return _job_result(job_id, "upload_keyframe_extraction", "canceled")

    jobs.update_progress(
        job_id, phase="extract_keyframes", percent=20, message="Extracting representative MP4 keyframes."
    )
    try:
        report = extract_keyframes(source_path, output_dir, max_frames=max_frames)
    except Exception as exc:
        jobs.mark_failed(job_id, str(exc))
        return _job_result(job_id, "upload_keyframe_extraction", "failed", error=str(exc))

    jobs.update_progress(job_id, phase="write_keyframes", percent=90, message="Writing keyframe manifest and previews.")
    if report.get("keyframes"):
        jobs.mark_completed(job_id, report)
    else:
        warnings = report.get("warnings", [])
        message = str(warnings[0].get("message")) if warnings else "No keyframes were extracted."
        jobs.mark_failed(job_id, message, report)
    completed = jobs.get(job_id) or {}
    return {
        "job_id": job_id,
        "kind": "upload_keyframe_extraction",
        "status": completed.get("status"),
        "keyframes": len(report.get("keyframes") or []),
    }


def run_cbct_surface_modeling_job(
    jobs: JobRegistry,
    job_id: str,
    settings: Settings,
    source_path: Path,
    *,
    repo: CaseRepository | None = None,
    source_paths: list[Path] | None = None,
    label_value: int,
    case_id: str,
    dataset_id: str,
    decimation_step: int,
    source_role: str = "volume",
    source_original_filename: str | None = None,
    mark_running: bool = True,
) -> dict[str, Any]:
    """生成或接入 CBCT/STL 三维表面证据，保持非导航边界。"""

    if mark_running:
        jobs.mark_running(job_id)
    if jobs.is_canceled(job_id):
        return _job_result(job_id, "cbct_surface_modeling", "canceled")

    jobs.update_progress(job_id, phase="inspect_source", percent=15, message="检查 CBCT/STL 输入与建模边界。")
    try:
        jobs.update_progress(job_id, phase="surface_modeling", percent=45, message="生成或接入上下颌骨表面模型。")
        modeling_source_paths: list[str | Path] | None = (
            [path for path in source_paths] if source_paths is not None else None
        )
        result = build_cbct_surface_model(
            settings=settings,
            source_path=source_path,
            source_paths=modeling_source_paths,
            label_value=label_value,
            case_id=case_id,
            dataset_id=dataset_id,
            decimation_step=decimation_step,
            source_role=source_role,
            source_original_filename=source_original_filename,
        )
        result = {
            **result,
            "source_path": str(source_path),
            "source_paths": [str(path) for path in (source_paths or [source_path])],
        }
        result = persist_three_d_modeling_result(repo, case_id=case_id, job_id=job_id, result=result)
    except Exception as exc:
        jobs.mark_failed(job_id, str(exc))
        return _job_result(job_id, "cbct_surface_modeling", "failed", error=str(exc))

    jobs.update_progress(job_id, phase="write_manifest", percent=90, message="写入三维证据 manifest。")
    if result.get("modeling_status") == "segmentation_required":
        jobs.mark_completed(job_id, result)
    elif result.get("model_path") or result.get("three_d_evidence"):
        jobs.mark_completed(job_id, result)
    else:
        jobs.mark_failed(job_id, "CBCT surface modeling did not produce a usable result.", result)
    completed = jobs.get(job_id) or {}
    return {
        "job_id": job_id,
        "kind": "cbct_surface_modeling",
        "status": completed.get("status"),
        "result": result,
    }


def run_l1_static_registration_job(
    jobs: JobRegistry,
    job_id: str,
    settings: Settings,
    repo: CaseRepository,
    payload: dict[str, Any],
    *,
    mark_running: bool = True,
) -> dict[str, Any]:
    if mark_running:
        jobs.mark_running(job_id)
    if jobs.is_canceled(job_id):
        return _job_result(job_id, "l1_static_registration", "canceled")
    service = StaticRegistrationService(settings, repo)
    jobs.update_progress(job_id, phase="validate_registration", percent=15, message="校验 L1 静态配准输入。")
    try:
        jobs.update_progress(job_id, phase="estimate_transform", percent=45, message="计算刚性点配准和 FRE/TRE。")
        result = service.register(payload, job_id=job_id)
        if jobs.is_canceled(job_id):
            return _job_result(job_id, "l1_static_registration", "canceled")
        result = persist_l1_registration_result(
            repo,
            case_id=str(payload.get("case_id") or ""),
            job_id=job_id,
            result=result,
        )
    except (
        CameraRegistrationError,
        StaticRegistrationRequestError,
        RigidRegistrationError,
    ) as exc:
        if jobs.is_canceled(job_id):
            return _job_result(job_id, "l1_static_registration", "canceled")
        code = str(getattr(exc, "code", "registration_failed"))
        result = service.failure_result(payload, job_id=job_id, code=code, message=str(exc))
        if jobs.is_canceled(job_id):
            return _job_result(job_id, "l1_static_registration", "canceled")
        result = persist_l1_registration_result(
            repo,
            case_id=str(payload.get("case_id") or ""),
            job_id=job_id,
            result=result,
        )
        jobs.mark_failed(job_id, str(exc), result)
        return {"job_id": job_id, "kind": "l1_static_registration", "status": "failed", "result": result}
    except Exception as exc:
        if jobs.is_canceled(job_id):
            return _job_result(job_id, "l1_static_registration", "canceled")
        result = service.failure_result(
            payload,
            job_id=job_id,
            code="registration_internal_failure",
            message="L1 registration failed during evidence generation.",
        )
        if jobs.is_canceled(job_id):
            return _job_result(job_id, "l1_static_registration", "canceled")
        result = persist_l1_registration_result(
            repo,
            case_id=str(payload.get("case_id") or ""),
            job_id=job_id,
            result=result,
        )
        jobs.mark_failed(job_id, str(exc), result)
        return {"job_id": job_id, "kind": "l1_static_registration", "status": "failed", "result": result}
    jobs.update_progress(job_id, phase="persist_registration", percent=90, message="写入 L1 配准证据。")
    jobs.mark_completed(job_id, result)
    return {"job_id": job_id, "kind": "l1_static_registration", "status": "completed", "result": result}


def run_l2_offline_pose_replay_job(
    jobs: JobRegistry,
    job_id: str,
    settings: Settings,
    repo: CaseRepository,
    payload: dict[str, Any],
    *,
    mark_running: bool = True,
) -> dict[str, Any]:
    if mark_running:
        jobs.mark_running(job_id)
    if jobs.is_canceled(job_id):
        return _job_result(job_id, "l2_offline_pose_replay", "canceled")
    service = OfflinePoseReplayService(settings, repo)
    jobs.update_progress(job_id, phase="validate_l1_evidence", percent=15, message="校验病例 L1 变换与位姿输入。")
    try:
        jobs.update_progress(job_id, phase="replay_poses", percent=45, message="执行 L2 离线位姿同步和失效门控。")
        result = service.replay(payload, job_id=job_id)
        if jobs.is_canceled(job_id):
            return _job_result(job_id, "l2_offline_pose_replay", "canceled")
        result = persist_l2_pose_replay_result(
            repo,
            case_id=str(payload.get("case_id") or ""),
            job_id=job_id,
            result=result,
        )
    except (OfflinePoseReplayRequestError, OfflinePoseReplayError) as exc:
        if jobs.is_canceled(job_id):
            return _job_result(job_id, "l2_offline_pose_replay", "canceled")
        code = str(getattr(exc, "code", "pose_replay_failed"))
        result = service.failure_result(payload, job_id=job_id, code=code, message=str(exc))
        if jobs.is_canceled(job_id):
            return _job_result(job_id, "l2_offline_pose_replay", "canceled")
        result = persist_l2_pose_replay_result(
            repo,
            case_id=str(payload.get("case_id") or ""),
            job_id=job_id,
            result=result,
        )
        jobs.mark_failed(job_id, str(exc), result)
        return {"job_id": job_id, "kind": "l2_offline_pose_replay", "status": "failed", "result": result}
    except Exception as exc:
        if jobs.is_canceled(job_id):
            return _job_result(job_id, "l2_offline_pose_replay", "canceled")
        result = service.failure_result(
            payload,
            job_id=job_id,
            code="pose_replay_internal_failure",
            message="L2 pose replay failed during evidence generation.",
        )
        if jobs.is_canceled(job_id):
            return _job_result(job_id, "l2_offline_pose_replay", "canceled")
        result = persist_l2_pose_replay_result(
            repo,
            case_id=str(payload.get("case_id") or ""),
            job_id=job_id,
            result=result,
        )
        jobs.mark_failed(job_id, str(exc), result)
        return {"job_id": job_id, "kind": "l2_offline_pose_replay", "status": "failed", "result": result}
    jobs.update_progress(job_id, phase="persist_pose_replay", percent=90, message="写入 L2 回放 manifest 与逐帧证据。")
    jobs.mark_completed(job_id, result)
    return {"job_id": job_id, "kind": "l2_offline_pose_replay", "status": "completed", "result": result}


def _job_result(job_id: str, kind: str, status: str, *, error: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"job_id": job_id, "kind": kind, "status": status}
    if error:
        payload["error"] = error
    return payload
