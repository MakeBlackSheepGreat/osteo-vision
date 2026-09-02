from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.osteo_vision_api.core.settings import Settings
from backend.osteo_vision_api.domains.annotations.repository import AnnotationRepository
from backend.osteo_vision_api.domains.cases.repository import build_case_repository
from backend.osteo_vision_api.domains.cases.schemas import AnalysisRunCreateRequest
from backend.osteo_vision_api.services.analysis_service import AnalysisService
from backend.osteo_vision_api.services.job_service import JobRegistry
from backend.osteo_vision_api.services.job_tasks import (
    run_case_analysis_job,
    run_cbct_surface_modeling_job,
    run_l1_static_registration_job,
    run_l2_offline_pose_replay_job,
    run_upload_keyframes_job,
)
from osteo_vision_core.core.paths import ensure_dir


class LocalJobWorker:
    """Single-process durable queue worker for the local platform workflow.

    This is intentionally small: it drains jobs from the same persistent
    registry used by the FastAPI app, so interrupted queued jobs can be resumed
    without introducing Redis/Celery during the platform software stage.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.jobs = JobRegistry(settings.job_store_path)
        self.repo = build_case_repository(settings.case_store_path, settings.case_store_backend)
        self.annotation_repository = AnnotationRepository(settings.annotation_store_path)
        self.analysis_service = AnalysisService(
            self.repo,
            str(settings.inference_config_path),
            annotation_repository=self.annotation_repository,
        )

    def run_once(self, *, limit: int = 1, kinds: list[str] | None = None) -> dict[str, Any]:
        processed: list[dict[str, Any]] = []
        for _ in range(max(1, limit)):
            job = self._claim_next(kinds)
            if job is None:
                break
            processed.append(self._process(job))
        return {
            "processed_count": len(processed),
            "processed": processed,
            "remaining_queued": len(self.jobs.list_jobs(status="queued")),
        }

    def _claim_next(self, kinds: list[str] | None) -> dict[str, Any] | None:
        if not kinds:
            return self.jobs.claim_next_queued()
        for kind in kinds:
            job = self.jobs.claim_next_queued(kind=kind)
            if job is not None:
                return job
        return None

    def _process(self, job: dict[str, Any]) -> dict[str, Any]:
        kind = str(job.get("kind") or "")
        if kind == "case_analysis":
            return self._process_case_analysis(job)
        if kind == "upload_keyframe_extraction":
            return self._process_upload_keyframes(job)
        if kind == "cbct_surface_modeling":
            return self._process_cbct_surface_modeling(job)
        if kind == "l1_static_registration":
            return self._process_l1_static_registration(job)
        if kind == "l2_offline_pose_replay":
            return self._process_l2_offline_pose_replay(job)
        self.jobs.mark_failed(str(job["job_id"]), f"Unsupported job kind: {kind}")
        return {"job_id": job["job_id"], "kind": kind, "status": "failed", "error": "unsupported kind"}

    def _process_case_analysis(self, job: dict[str, Any]) -> dict[str, Any]:
        job_id = str(job["job_id"])
        payload = _payload(job)
        case_id = str(payload.get("case_id") or "")
        request = AnalysisRunCreateRequest(
            selected_input_ids=list(payload.get("selected_input_ids") or []),
            parameters=dict(payload.get("parameters") or {}),
            roi_hints=list(payload.get("roi_hints") or []),
        )
        # 本地 worker 领取任务时已标记为 running；这里只复用统一任务体，避免后台模式和 worker 模式分叉。
        return run_case_analysis_job(
            self.jobs,
            job_id,
            self.repo,
            self.analysis_service,
            case_id,
            request,
            mark_running=False,
        )

    def _process_upload_keyframes(self, job: dict[str, Any]) -> dict[str, Any]:
        job_id = str(job["job_id"])
        payload = _payload(job)
        source_path = Path(str(payload.get("source_path") or ""))
        output_dir = ensure_dir(
            str(payload.get("output_dir") or self.settings.artifact_root / "uploads" / "keyframes" / source_path.stem)
        )
        max_frames = int(payload.get("max_frames") or 5)
        return run_upload_keyframes_job(
            self.jobs,
            job_id,
            source_path,
            output_dir,
            max_frames,
            mark_running=False,
        )

    def _process_cbct_surface_modeling(self, job: dict[str, Any]) -> dict[str, Any]:
        job_id = str(job["job_id"])
        payload = _payload(job)
        return run_cbct_surface_modeling_job(
            self.jobs,
            job_id,
            self.settings,
            Path(str(payload.get("source_path") or "")),
            repo=self.repo,
            source_paths=[Path(str(path)) for path in payload.get("source_paths") or []],
            label_value=int(payload.get("label_value") or 1),
            case_id=str(payload.get("case_id") or "local_cbct"),
            dataset_id=str(payload.get("dataset_id") or "local_import"),
            decimation_step=int(payload.get("decimation_step") or 1),
            source_role=str(payload.get("source_role") or "volume"),
            source_original_filename=(
                str(payload.get("source_original_filename")) if payload.get("source_original_filename") else None
            ),
            mark_running=False,
        )

    def _process_l1_static_registration(self, job: dict[str, Any]) -> dict[str, Any]:
        return run_l1_static_registration_job(
            self.jobs,
            str(job["job_id"]),
            self.settings,
            self.repo,
            _payload(job),
            mark_running=False,
        )

    def _process_l2_offline_pose_replay(self, job: dict[str, Any]) -> dict[str, Any]:
        return run_l2_offline_pose_replay_job(
            self.jobs,
            str(job["job_id"]),
            self.settings,
            self.repo,
            _payload(job),
            mark_running=False,
        )


def _payload(job: dict[str, Any]) -> dict[str, Any]:
    payload = job.get("payload")
    return payload if isinstance(payload, dict) else {}
