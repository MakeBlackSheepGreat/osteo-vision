from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from backend.osteo_vision_api.api.helpers import capacity_exceeded, conflict_from_active_job, require_case
from backend.osteo_vision_api.domains.cases.repository import CaseRepository
from backend.osteo_vision_api.domains.cases.schemas import AnalysisRun, AnalysisRunCreateRequest, CaseRecord
from backend.osteo_vision_api.services.analysis_service import AnalysisService
from backend.osteo_vision_api.services.job_service import JobCapacityError, JobConflictError, JobRegistry
from backend.osteo_vision_api.services.job_tasks import run_case_analysis_job


def router(
    repo: CaseRepository,
    service: AnalysisService,
    jobs: JobRegistry,
    *,
    max_active_jobs: int = 1,
    execution_mode: str = "background",
) -> APIRouter:
    api = APIRouter()

    @api.post("/cases/{case_id}/analysis-runs", response_model=CaseRecord)
    def start_analysis(case_id: str, request: AnalysisRunCreateRequest) -> CaseRecord:
        case = require_case(repo, case_id)
        return service.start_analysis(case, request.selected_input_ids, request.parameters, request.roi_hints)

    @api.post("/cases/{case_id}/analysis-jobs")
    def start_analysis_job(
        case_id: str,
        request: AnalysisRunCreateRequest,
        background_tasks: BackgroundTasks,
    ) -> dict[str, object]:
        require_case(repo, case_id)
        payload = {
            "case_id": case_id,
            "selected_input_ids": request.selected_input_ids,
            "parameters": request.parameters,
            "roi_hints": request.roi_hints,
            "roi_hint_count": len(request.roi_hints),
        }
        try:
            job = jobs.create(
                kind="case_analysis",
                payload=payload,
                max_active=max_active_jobs,
                singleton_keys=["case_id"],
            )
        except JobConflictError as exc:
            raise conflict_from_active_job(
                exc,
                code="case_analysis_job_already_active",
                message="An analysis job is already queued or running for this case.",
            ) from exc
        except JobCapacityError as exc:
            raise capacity_exceeded(
                exc,
                code="case_analysis_job_capacity_exceeded",
                message="Too many analysis jobs are queued or running. Try again after the active job completes.",
            ) from exc
        if execution_mode != "worker":
            background_tasks.add_task(_run_analysis_job, jobs, job["job_id"], repo, service, case_id, request)
        return job

    @api.get("/analysis-jobs/{job_id}")
    def get_analysis_job(job_id: str) -> dict[str, object]:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Analysis job not found")
        return job

    @api.post("/analysis-jobs/{job_id}/cancel")
    def cancel_analysis_job(job_id: str) -> dict[str, object]:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Analysis job not found")
        if job.get("kind") != "case_analysis":
            raise HTTPException(status_code=400, detail="Only case analysis jobs can be canceled here")
        canceled = jobs.cancel(job_id)
        if canceled is None:
            raise HTTPException(status_code=404, detail="Analysis job not found")
        return canceled

    @api.get("/analysis-runs/{run_id}", response_model=AnalysisRun)
    def get_analysis_run(run_id: str) -> AnalysisRun:
        for case in repo.list():
            for run in case.analysis_runs:
                if run.run_id == run_id:
                    return run
        raise HTTPException(status_code=404, detail="Analysis run not found")

    return api


def _run_analysis_job(
    jobs: JobRegistry,
    job_id: str,
    repo: CaseRepository,
    service: AnalysisService,
    case_id: str,
    request: AnalysisRunCreateRequest,
) -> None:
    # FastAPI BackgroundTasks 与 LocalJobWorker 共用同一任务体，避免同一状态机维护两份实现。
    run_case_analysis_job(jobs, job_id, repo, service, case_id, request, mark_running=True)
