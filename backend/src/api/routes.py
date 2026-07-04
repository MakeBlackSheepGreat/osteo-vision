from __future__ import annotations

from fastapi import APIRouter

from backend.src.api import analysis_runs, cases, exports, files, inputs, regions, review_events, uploads, video_library
from backend.src.core.settings import Settings
from backend.src.domains.cases.repository import build_case_repository
from backend.src.services.analysis_service import AnalysisService
from backend.src.services.export_service import ExportService
from backend.src.services.input_service import InputService
from backend.src.services.job_service import JobRegistry
from backend.src.services.review_service import ReviewService
from backend.src.services.video_library_service import VideoLibraryService


def build_router(settings: Settings) -> APIRouter:
    repo = build_case_repository(settings.case_store_path, settings.case_store_backend)
    jobs = JobRegistry(settings.job_store_path)
    input_service = InputService()
    analysis_service = AnalysisService(repo)
    review_service = ReviewService(repo)
    export_service = ExportService(repo, settings.artifact_root / "exports")
    video_library_service = VideoLibraryService(
        settings.video_manifest_path,
        preview_root=settings.artifact_root / "video_library_previews",
    )

    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/ready")
    def ready() -> dict[str, str]:
        return {
            "status": "ok",
            "storage": str(settings.case_store_path),
            "storage_backend": settings.case_store_backend,
            "job_store": str(settings.job_store_path),
            "job_execution_mode": settings.job_execution_mode,
        }

    router.include_router(cases.router(repo), tags=["cases"])
    router.include_router(inputs.router(repo, input_service), tags=["inputs"])
    router.include_router(
        analysis_runs.router(
            repo,
            analysis_service,
            jobs,
            max_active_jobs=settings.max_active_case_analysis_jobs,
            execution_mode=settings.job_execution_mode,
        ),
        tags=["analysis"],
    )
    router.include_router(regions.router(repo, review_service), tags=["review"])
    router.include_router(review_events.router(repo, review_service), tags=["review"])
    router.include_router(exports.router(repo, export_service), tags=["exports"])
    router.include_router(
        uploads.router(
            settings,
            jobs,
            max_active_keyframe_jobs=settings.max_active_upload_keyframe_jobs,
            execution_mode=settings.job_execution_mode,
        ),
        tags=["uploads"],
    )
    router.include_router(video_library.router(repo, input_service, video_library_service), tags=["video-library"])
    router.include_router(files.router(settings), tags=["files"])
    return router
