from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.src.api.helpers import require_case
from backend.src.api.review_identity import resolve_review_actor
from backend.src.domains.cases.repository import CaseRepository
from backend.src.domains.cases.schemas import (
    BoneGateMaskCreateRequest,
    BoneGateMaskEditRequest,
    CaseRecord,
    RegionUpdateRequest,
    ReviewActorIdentity,
)
from backend.src.services.review_service import PromptFallbackSafetyError, ReviewService


def router(repo: CaseRepository, service: ReviewService) -> APIRouter:
    api = APIRouter()

    @api.patch("/cases/{case_id}/regions/{region_id}", response_model=CaseRecord)
    def update_region(
        case_id: str,
        region_id: str,
        request: RegionUpdateRequest,
        actor: Annotated[ReviewActorIdentity, Depends(resolve_review_actor)],
    ) -> CaseRecord:
        case = require_case(repo, case_id)
        return service.update_region(case, region_id, request, actor)

    @api.post("/cases/{case_id}/regions/from-candidate/{candidate_id}", response_model=CaseRecord)
    def add_region_from_candidate(
        case_id: str,
        candidate_id: str,
        actor: Annotated[ReviewActorIdentity, Depends(resolve_review_actor)],
    ) -> CaseRecord:
        case = require_case(repo, case_id)
        try:
            return service.add_candidate_roi(case, candidate_id, actor)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @api.patch("/cases/{case_id}/candidate-regions/{candidate_id}", response_model=CaseRecord)
    def update_candidate_region(
        case_id: str,
        candidate_id: str,
        request: RegionUpdateRequest,
        actor: Annotated[ReviewActorIdentity, Depends(resolve_review_actor)],
    ) -> CaseRecord:
        case = require_case(repo, case_id)
        try:
            return service.update_candidate_region(case, candidate_id, request, actor)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @api.post("/cases/{case_id}/candidate-regions/{candidate_id}/bone-gate-mask", response_model=CaseRecord)
    def generate_candidate_bone_gate_mask(
        case_id: str,
        candidate_id: str,
        request: BoneGateMaskCreateRequest,
        actor: Annotated[ReviewActorIdentity, Depends(resolve_review_actor)],
    ) -> CaseRecord:
        case = require_case(repo, case_id)
        try:
            return service.generate_candidate_bone_gate_mask(case, candidate_id, request, actor)
        except PromptFallbackSafetyError as exc:
            raise HTTPException(status_code=409, detail=exc.detail()) from exc
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @api.post("/cases/{case_id}/candidate-regions/{candidate_id}/bone-gate-mask/edits", response_model=CaseRecord)
    def save_candidate_bone_gate_mask_edit(
        case_id: str,
        candidate_id: str,
        request: BoneGateMaskEditRequest,
        actor: Annotated[ReviewActorIdentity, Depends(resolve_review_actor)],
    ) -> CaseRecord:
        case = require_case(repo, case_id)
        try:
            return service.save_candidate_bone_gate_mask_edit(case, candidate_id, request, actor)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return api
