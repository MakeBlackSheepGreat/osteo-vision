from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from backend.src.core.settings import Settings
from backend.src.domains.cases.repository import CaseRepository
from backend.src.services.job_service import JobCapacityError, JobConflictError, JobRegistry
from backend.src.api.helpers import capacity_exceeded, conflict_from_active_job
from backend.src.services.job_tasks import run_cbct_surface_modeling_job


class ThreeDModelingRequest(BaseModel):
    source_path: str = Field(..., min_length=1)
    source_paths: list[str] | None = None
    source_role: Literal["volume", "label", "surface", "auto"] = "volume"
    source_original_filename: str | None = None
    label_value: int = Field(default=1, ge=0)
    case_id: str = Field(default="local_cbct", min_length=1)
    dataset_id: str = Field(default="local_import", min_length=1)
    decimation_step: int = Field(default=1, ge=1)


def router(
    settings: Settings,
    jobs: JobRegistry,
    repo: CaseRepository | None = None,
    *,
    max_active_jobs: int = 1,
    execution_mode: str = "background",
) -> APIRouter:
    api = APIRouter()

    @api.post("/three-d/modeling-jobs")
    def start_three_d_modeling_job(
        request: ThreeDModelingRequest,
        background_tasks: BackgroundTasks,
    ) -> dict[str, Any]:
        payload = request.model_dump()
        try:
            job = jobs.create(
                kind="cbct_surface_modeling",
                payload=payload,
                max_active=max_active_jobs,
                singleton_keys=["source_path"],
            )
        except JobConflictError as exc:
            raise conflict_from_active_job(
                exc,
                code="cbct_modeling_job_already_active",
                message="A CBCT/STL modeling job is already queued or running for this source.",
            ) from exc
        except JobCapacityError as exc:
            raise capacity_exceeded(
                exc,
                code="cbct_modeling_job_capacity_exceeded",
                message="Too many CBCT/STL modeling jobs are queued or running. Try again later.",
            ) from exc

        if execution_mode != "worker":
            background_tasks.add_task(
                _run_modeling_job,
                jobs,
                job["job_id"],
                settings,
                request,
                repo,
            )
        return job

    @api.get("/three-d/modeling-jobs/{job_id}")
    def get_three_d_modeling_job(job_id: str) -> dict[str, Any]:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="3D modeling job not found")
        if job.get("kind") != "cbct_surface_modeling":
            raise HTTPException(status_code=400, detail="Job is not a CBCT/STL modeling job")
        return job

    @api.post("/three-d/modeling-jobs/{job_id}/cancel")
    def cancel_three_d_modeling_job(job_id: str) -> dict[str, Any]:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="3D modeling job not found")
        if job.get("kind") != "cbct_surface_modeling":
            raise HTTPException(status_code=400, detail="Job is not a CBCT/STL modeling job")
        canceled = jobs.cancel(job_id)
        if canceled is None:
            raise HTTPException(status_code=404, detail="3D modeling job not found")
        return canceled

    return api


def _run_modeling_job(
    jobs: JobRegistry,
    job_id: str,
    settings: Settings,
    request: ThreeDModelingRequest,
    repo: CaseRepository | None,
) -> None:
    run_cbct_surface_modeling_job(
        jobs,
        job_id,
        settings,
        Path(request.source_path),
        repo=repo,
        source_paths=[Path(path) for path in request.source_paths] if request.source_paths else None,
        label_value=request.label_value,
        case_id=request.case_id,
        dataset_id=request.dataset_id,
        decimation_step=request.decimation_step,
        source_role=request.source_role,
        source_original_filename=request.source_original_filename,
        mark_running=True,
    )
