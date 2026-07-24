from __future__ import annotations

from fastapi import APIRouter

from backend.osteo_vision_api.api.helpers import require_case
from backend.osteo_vision_api.domains.cases.repository import CaseRepository
from backend.osteo_vision_api.domains.cases.schemas import CaseRecord, InputCreateRequest
from backend.osteo_vision_api.services.input_service import InputService


def router(repo: CaseRepository, service: InputService) -> APIRouter:
    api = APIRouter()

    @api.post("/cases/{case_id}/inputs", response_model=CaseRecord)
    def add_inputs(case_id: str, request: list[InputCreateRequest]) -> CaseRecord:
        case = require_case(repo, case_id)
        updated = service.add_inputs(case, request)
        return repo.save(updated)

    return api
