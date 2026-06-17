from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.src.domains.cases.repository import CaseRepository
from backend.src.domains.cases.schemas import CaseRecord, InputCreateRequest
from backend.src.services.input_service import InputService


def router(repo: CaseRepository, service: InputService) -> APIRouter:
    api = APIRouter()

    @api.post("/cases/{case_id}/inputs", response_model=CaseRecord)
    def add_inputs(case_id: str, request: list[InputCreateRequest]) -> CaseRecord:
        case = repo.get(case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="Case not found")
        updated = service.add_inputs(case, request)
        return repo.save(updated)

    return api
