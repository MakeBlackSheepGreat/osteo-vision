from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.src.domains.cases.repository import CaseRepository
from backend.src.domains.cases.schemas import CaseRecord, ReviewEventCreateRequest
from backend.src.services.review_service import ReviewService


def router(repo: CaseRepository, service: ReviewService) -> APIRouter:
    api = APIRouter()

    @api.post("/cases/{case_id}/review-events", response_model=CaseRecord)
    def add_review_event(case_id: str, request: ReviewEventCreateRequest) -> CaseRecord:
        case = repo.get(case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="Case not found")
        return service.add_review_event(case, request)

    return api
