from __future__ import annotations

from fastapi import APIRouter

from backend.src.api.helpers import require_case
from backend.src.domains.cases.repository import CaseRepository
from backend.src.domains.cases.schemas import ExportRequest, ExportResponse
from backend.src.services.export_service import ExportService


def router(repo: CaseRepository, service: ExportService) -> APIRouter:
    api = APIRouter()

    @api.post("/cases/{case_id}/exports", response_model=ExportResponse)
    def export_case(case_id: str, request: ExportRequest) -> ExportResponse:
        case = require_case(repo, case_id)
        return service.export_case(case, request)

    return api
