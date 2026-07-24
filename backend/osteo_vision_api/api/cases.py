from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from backend.osteo_vision_api.api.helpers import require_case
from backend.osteo_vision_api.api.review_identity import can_verify_clinical_context, resolve_review_actor
from backend.osteo_vision_api.core.disclaimers import PLATFORM_SAFETY_DISCLAIMER
from backend.osteo_vision_api.domains.cases.repository import CaseRepository
from backend.osteo_vision_api.domains.cases.schemas import (
    CaseCreateRequest,
    CaseRecord,
    ClinicalContext,
    ClinicalContextUpdateRequest,
    ReviewActorIdentity,
)


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
            disclaimer=PLATFORM_SAFETY_DISCLAIMER,
            review_summary={"metadata": request.metadata},
        )
        return repo.create(case)

    @api.get("/cases/{case_id}", response_model=CaseRecord)
    def get_case(case_id: str) -> CaseRecord:
        return require_case(repo, case_id)

    @api.get("/cases", response_model=list[CaseRecord])
    def list_cases() -> list[CaseRecord]:
        return repo.list()

    @api.put("/cases/{case_id}/clinical-context", response_model=CaseRecord)
    def update_clinical_context(
        case_id: str,
        request: ClinicalContextUpdateRequest,
        actor: Annotated[ReviewActorIdentity, Depends(resolve_review_actor)],
    ) -> CaseRecord:
        case = require_case(repo, case_id)
        verification_requested = request.review_status == "verified"
        if verification_requested and not can_verify_clinical_context(actor):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "clinical_context_verification_forbidden",
                    "message": (
                        "Clinical context verification requires an authenticated physician "
                        "or project reviewer with an approved authentication source"
                    ),
                },
            )
        clinical_context = ClinicalContext.model_validate(
            {
                **request.model_dump(),
                "verified_by": actor if verification_requested else None,
                "verified_at": datetime.now(timezone.utc) if verification_requested else None,
            }
        )
        updated = case.model_copy(update={"clinical_context": clinical_context})
        return repo.save(updated)

    return api
