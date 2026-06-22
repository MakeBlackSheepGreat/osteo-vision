from __future__ import annotations

from fastapi import APIRouter

from backend.src.api import analysis_runs, cases, exports, inputs, regions, review_events, uploads
from backend.src.core.settings import Settings
from backend.src.domains.cases.repository import JsonCaseRepository
from backend.src.services.analysis_service import AnalysisService
from backend.src.services.export_service import ExportService
from backend.src.services.input_service import InputService
from backend.src.services.review_service import ReviewService


def build_router(settings: Settings) -> APIRouter:
    repo = JsonCaseRepository(settings.case_store_path)
    input_service = InputService()
    analysis_service = AnalysisService(repo)
    review_service = ReviewService(repo)
    export_service = ExportService(repo, settings.artifact_root / "exports")

    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/ready")
    def ready() -> dict[str, str]:
        return {"status": "ok", "storage": str(settings.case_store_path)}

    router.include_router(cases.router(repo), tags=["cases"])
    router.include_router(inputs.router(repo, input_service), tags=["inputs"])
    router.include_router(analysis_runs.router(repo, analysis_service), tags=["analysis"])
    router.include_router(regions.router(repo, review_service), tags=["review"])
    router.include_router(review_events.router(repo, review_service), tags=["review"])
    router.include_router(exports.router(repo, export_service), tags=["exports"])
    router.include_router(uploads.router(settings), tags=["uploads"])
    return router
