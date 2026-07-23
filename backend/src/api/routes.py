from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from backend.src.api import (
    analysis_runs,
    cases,
    dataset_review,
    exports,
    files,
    hospital_intake,
    inputs,
    live_frames,
    manual_annotations,
    promotion_approvals,
    regions,
    review_events,
    three_d_modeling,
    three_d_runtime,
    uploads,
    video_library,
)
from backend.src.core.settings import Settings
from backend.src.domains.annotations.repository import AnnotationRepository
from backend.src.domains.cases.repository import build_case_repository
from backend.src.services.analysis_service import AnalysisService
from backend.src.services.export_service import ExportService
from backend.src.services.hospital_intake_service import HospitalIntakeService
from backend.src.services.input_service import InputService
from backend.src.services.job_service import JobRegistry
from backend.src.services.live_frame_service import LiveFrameAnalysisService
from backend.src.services.manual_annotation_service import ManualAnnotationService
from backend.src.services.promotion_approval_service import (
    PromotionApprovalRepository,
    PromotionApprovalService,
    load_promotion_trust_store,
)
from backend.src.services.review_service import ReviewService
from backend.src.services.static_dataset_review import StaticDatasetReviewService
from backend.src.services.video_library_service import VideoLibraryService
from src.models.runtime_preflight import check_runtime_readiness


def build_router(settings: Settings) -> APIRouter:
    repo = build_case_repository(settings.case_store_path, settings.case_store_backend)
    jobs = JobRegistry(settings.job_store_path)
    input_service = InputService(
        allowed_roots=[settings.artifact_root, settings.project_root / "research" / "datasets", settings.project_root]
    )
    runtime_readiness = check_runtime_readiness(settings.inference_config_path)
    if runtime_readiness["strict_startup"] and not runtime_readiness["passed"]:
        raise RuntimeError(
            "Strict runtime readiness failed: "
            + ", ".join(str(item.get("code") or "unknown") for item in runtime_readiness["errors"])
        )
    annotation_repository = AnnotationRepository(settings.annotation_store_path)
    analysis_service = AnalysisService(
        repo,
        str(settings.inference_config_path),
        annotation_repository=annotation_repository,
    )
    live_frame_service = LiveFrameAnalysisService(str(settings.inference_config_path))
    review_service = ReviewService(
        repo,
        settings.inference_config_path,
        annotation_repository=annotation_repository,
        artifact_root=settings.artifact_root,
    )
    video_library_service = VideoLibraryService(
        settings.video_manifest_path,
        preview_root=settings.artifact_root / "video_library_previews",
    )
    static_dataset_review_service = StaticDatasetReviewService(settings.project_root)
    hospital_intake_service = HospitalIntakeService(
        artifact_root=settings.artifact_root,
        repo=repo,
        input_service=input_service,
    )
    manual_annotation_service = ManualAnnotationService(
        annotation_repository,
        repo,
        settings.artifact_root,
        ignore_annotation_synchronizer=review_service,
    )
    promotion_approval_service = PromotionApprovalService(
        PromotionApprovalRepository(settings.promotion_approval_store_path),
        load_promotion_trust_store(settings.promotion_trusted_keys_path),
    )
    export_service = ExportService(
        repo,
        settings.artifact_root / "exports",
        annotation_service=manual_annotation_service,
    )

    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/ready")
    def ready() -> dict[str, Any]:
        return {
            "status": "ok" if runtime_readiness["passed"] else "degraded",
            "storage": str(settings.case_store_path),
            "storage_backend": settings.case_store_backend,
            "job_store": str(settings.job_store_path),
            "job_execution_mode": settings.job_execution_mode,
            "annotation_store": str(settings.annotation_store_path),
            "promotion_approval_store": str(settings.promotion_approval_store_path),
            "promotion_trusted_keys": str(settings.promotion_trusted_keys_path),
            "inference_config": str(settings.inference_config_path),
            "runtime_readiness": runtime_readiness,
        }

    router.include_router(cases.router(repo), tags=["cases"])
    router.include_router(inputs.router(repo, input_service), tags=["inputs"])
    router.include_router(live_frames.router(repo, live_frame_service), tags=["live-frames"])
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
    router.include_router(
        manual_annotations.router(repo, manual_annotation_service),
        tags=["manual-annotations"],
    )
    router.include_router(
        promotion_approvals.router(promotion_approval_service),
        tags=["model-promotion"],
    )
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
    router.include_router(
        three_d_modeling.router(
            settings,
            jobs,
            repo,
            max_active_jobs=1,
            execution_mode=settings.job_execution_mode,
        ),
        tags=["three-d-modeling"],
    )
    router.include_router(three_d_runtime.router(settings, repo), tags=["three-d-runtime"])
    router.include_router(video_library.router(repo, input_service, video_library_service), tags=["video-library"])
    router.include_router(dataset_review.router(static_dataset_review_service), tags=["dataset-review"])
    router.include_router(hospital_intake.router(hospital_intake_service), tags=["hospital-intake"])
    router.include_router(files.router(settings), tags=["files"])
    return router
