from __future__ import annotations

from fastapi import APIRouter

from backend.osteo_vision_api.domains.cases.schemas import CaseRecord
from backend.osteo_vision_api.services.standard_demo_case import StandardDemoCaseService


def router(service: StandardDemoCaseService) -> APIRouter:
    api = APIRouter()

    @api.post("/platform/standard-demo-case", response_model=CaseRecord)
    def ensure_standard_demo_case() -> CaseRecord:
        return service.ensure_case()

    @api.post("/platform/demo-cases", response_model=list[CaseRecord])
    def ensure_demo_cases() -> list[CaseRecord]:
        return service.ensure_demo_catalog()

    return api
