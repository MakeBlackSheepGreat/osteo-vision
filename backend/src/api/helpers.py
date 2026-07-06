from __future__ import annotations

from fastapi import HTTPException

from backend.src.domains.cases.repository import CaseRepository
from backend.src.domains.cases.schemas import CaseRecord
from backend.src.services.job_service import JobCapacityError, JobConflictError


def require_case(repo: CaseRepository, case_id: str) -> CaseRecord:
    case = repo.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


def conflict_from_active_job(exc: JobConflictError, *, code: str, message: str) -> HTTPException:
    # API 层统一把队列冲突转换成结构化 detail，前端可以稳定读取 active_job_id。
    return HTTPException(
        status_code=409,
        detail={
            "code": code,
            "message": message,
            "active_job_id": exc.active_job.get("job_id"),
        },
    )


def capacity_exceeded(exc: JobCapacityError, *, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail={
            "code": code,
            "message": message,
            "active_count": exc.active_count,
            "max_active": exc.max_active,
        },
    )
