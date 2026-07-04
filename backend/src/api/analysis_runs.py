from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from backend.src.domains.cases.repository import CaseRepository
from backend.src.domains.cases.schemas import AnalysisRun, AnalysisRunCreateRequest, CaseRecord
from backend.src.services.analysis_service import AnalysisService
from backend.src.services.job_service import JobCapacityError, JobConflictError, JobRegistry


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
        case = repo.get(case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="Case not found")
        return service.start_analysis(case, request.selected_input_ids, request.parameters, request.roi_hints)

    @api.post("/cases/{case_id}/analysis-jobs")
    def start_analysis_job(
        case_id: str,
        request: AnalysisRunCreateRequest,
        background_tasks: BackgroundTasks,
    ) -> dict[str, object]:
        case = repo.get(case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="Case not found")
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
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "case_analysis_job_already_active",
                    "message": "An analysis job is already queued or running for this case.",
                    "active_job_id": exc.active_job.get("job_id"),
                },
            ) from exc
        except JobCapacityError as exc:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "case_analysis_job_capacity_exceeded",
                    "message": "Too many analysis jobs are queued or running. Try again after the active job completes.",
                    "active_count": exc.active_count,
                    "max_active": exc.max_active,
                },
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
    jobs.mark_running(job_id)
    if jobs.is_canceled(job_id):
        return
    jobs.update_progress(job_id, phase="load_case", percent=15, message="Loading case inputs and analysis request.")
    case = repo.get(case_id)
    if case is None:
        jobs.mark_failed(job_id, "Case not found")
        return
    try:
        jobs.update_progress(job_id, phase="analyze", percent=35, message="Running fluorescence and AI analysis.")
        updated = service.start_analysis(case, request.selected_input_ids, request.parameters, request.roi_hints)
    except Exception as exc:
        jobs.mark_failed(job_id, str(exc))
        return
    if jobs.is_canceled(job_id):
        return
    jobs.update_progress(job_id, phase="persist_results", percent=90, message="Persisting analysis results and artifacts.")
    latest = updated.analysis_runs[-1] if updated.analysis_runs else None
    result = {
        "case_id": updated.case_id,
        "case_status": updated.status,
        "run_id": latest.run_id if latest else None,
        "run_status": latest.status if latest else None,
    }
    if latest and latest.status == "failed":
        jobs.mark_failed(job_id, "Analysis run failed.", result)
    else:
        jobs.mark_completed(job_id, result)
