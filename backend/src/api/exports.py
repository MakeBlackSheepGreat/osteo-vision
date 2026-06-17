from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.src.domains.cases.repository import CaseRepository
from backend.src.domains.cases.schemas import ExportRequest, ExportResponse
from backend.src.services.export_service import ExportService


def router(repo: CaseRepository, service: ExportService) -> APIRouter:
    api = APIRouter()

    @api.post("/cases/{case_id}/exports", response_model=ExportResponse)
    def export_case(case_id: str, request: ExportRequest) -> ExportResponse:
        case = repo.get(case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="Case not found")
        return service.export_case(case, request)

    return api
