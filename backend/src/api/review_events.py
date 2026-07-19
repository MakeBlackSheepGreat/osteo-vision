from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.src.api.helpers import require_case
from backend.src.api.review_identity import identity_status, resolve_review_actor
from backend.src.domains.cases.repository import CaseRepository
from backend.src.domains.cases.schemas import (
    CaseRecord,
    ReviewActorIdentity,
    ReviewEventCreateRequest,
    ReviewIdentityStatus,
)
from backend.src.services.review_service import ReviewService


def router(repo: CaseRepository, service: ReviewService) -> APIRouter:
    api = APIRouter()

    @api.get("/review-identity", response_model=ReviewIdentityStatus)
    def get_review_identity(
        actor: Annotated[ReviewActorIdentity, Depends(resolve_review_actor)],
    ) -> ReviewIdentityStatus:
        return identity_status(actor)

    @api.post("/cases/{case_id}/review-events", response_model=CaseRecord)
    def add_review_event(
        case_id: str,
        request: ReviewEventCreateRequest,
        actor: Annotated[ReviewActorIdentity, Depends(resolve_review_actor)],
    ) -> CaseRecord:
        case = require_case(repo, case_id)
        return service.add_review_event(case, request, actor)

    return api
