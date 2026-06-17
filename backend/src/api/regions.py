from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.src.domains.cases.repository import CaseRepository
from backend.src.domains.cases.schemas import CaseRecord, RegionUpdateRequest
from backend.src.services.review_service import ReviewService


def router(repo: CaseRepository, service: ReviewService) -> APIRouter:
    api = APIRouter()

    @api.patch("/cases/{case_id}/regions/{region_id}", response_model=CaseRecord)
    def update_region(case_id: str, region_id: str, request: RegionUpdateRequest) -> CaseRecord:
        case = repo.get(case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="Case not found")
        return service.update_region(case, region_id, request)

    return api
