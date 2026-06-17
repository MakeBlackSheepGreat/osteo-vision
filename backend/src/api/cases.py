from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from backend.src.core.disclaimers import RESEARCH_PROTOTYPE_DISCLAIMER
from backend.src.domains.cases.repository import CaseRepository
from backend.src.domains.cases.schemas import CaseCreateRequest, CaseRecord


def router(repo: CaseRepository) -> APIRouter:
    api = APIRouter()

    @api.post("/cases", response_model=CaseRecord)
    def create_case(request: CaseCreateRequest) -> CaseRecord:
        now = datetime.now(timezone.utc)
        case = CaseRecord(
            case_id=f"case_{uuid4().hex[:10]}",
            title=request.title,
            created_at=now,
            updated_at=now,
            disclaimer_version=request.disclaimer_version,
            disclaimer=RESEARCH_PROTOTYPE_DISCLAIMER,
            review_summary={"metadata": request.metadata},
        )
        return repo.create(case)

    @api.get("/cases/{case_id}", response_model=CaseRecord)
    def get_case(case_id: str) -> CaseRecord:
        case = repo.get(case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="Case not found")
        return case

    @api.get("/cases", response_model=list[CaseRecord])
    def list_cases() -> list[CaseRecord]:
        return repo.list()

    return api
