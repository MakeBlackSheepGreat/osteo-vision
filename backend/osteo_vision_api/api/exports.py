from __future__ import annotations

from fastapi import APIRouter

from backend.osteo_vision_api.api.helpers import require_case
from backend.osteo_vision_api.domains.cases.repository import CaseRepository
from backend.osteo_vision_api.domains.cases.schemas import ExportRequest, ExportResponse
from backend.osteo_vision_api.services.export_service import ExportService


def router(repo: CaseRepository, service: ExportService) -> APIRouter:
    api = APIRouter()

    @api.post("/cases/{case_id}/exports", response_model=ExportResponse)
    def export_case(case_id: str, request: ExportRequest) -> ExportResponse:
        case = require_case(repo, case_id)
        return service.export_case(case, request)

    return api
