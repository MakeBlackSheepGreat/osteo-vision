from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.src.api.helpers import require_case
from backend.src.domains.cases.repository import CaseRepository
from backend.src.domains.cases.schemas import BoneGateMaskCreateRequest, CaseRecord, RegionUpdateRequest
from backend.src.services.review_service import ReviewService


def router(repo: CaseRepository, service: ReviewService) -> APIRouter:
    api = APIRouter()

    @api.patch("/cases/{case_id}/regions/{region_id}", response_model=CaseRecord)
    def update_region(case_id: str, region_id: str, request: RegionUpdateRequest) -> CaseRecord:
        case = require_case(repo, case_id)
        return service.update_region(case, region_id, request)

    @api.post("/cases/{case_id}/regions/from-candidate/{candidate_id}", response_model=CaseRecord)
    def add_region_from_candidate(case_id: str, candidate_id: str) -> CaseRecord:
        case = require_case(repo, case_id)
        try:
            return service.add_candidate_roi(case, candidate_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @api.patch("/cases/{case_id}/candidate-regions/{candidate_id}", response_model=CaseRecord)
    def update_candidate_region(case_id: str, candidate_id: str, request: RegionUpdateRequest) -> CaseRecord:
        case = require_case(repo, case_id)
        try:
            return service.update_candidate_region(case, candidate_id, request)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @api.post("/cases/{case_id}/candidate-regions/{candidate_id}/bone-gate-mask", response_model=CaseRecord)
    def generate_candidate_bone_gate_mask(
        case_id: str,
        candidate_id: str,
        request: BoneGateMaskCreateRequest,
    ) -> CaseRecord:
        case = require_case(repo, case_id)
        try:
            return service.generate_candidate_bone_gate_mask(case, candidate_id, request)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return api
