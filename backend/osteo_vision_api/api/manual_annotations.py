from __future__ import annotations

from contextlib import contextmanager
from typing import Annotated, Iterator

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.osteo_vision_api.api.helpers import require_case
from backend.osteo_vision_api.api.review_identity import resolve_review_actor
from backend.osteo_vision_api.domains.annotations.enums import AnnotationLabel, AnnotationStatus
from backend.osteo_vision_api.domains.annotations.repository import (
    AnnotationNotFoundError,
    AnnotationStateConflictError,
    AnnotationVersionConflictError,
)
from backend.osteo_vision_api.domains.annotations.schemas import (
    AnnotationCreateRequest,
    AnnotationDeleteResponse,
    AnnotationReviewRequest,
    AnnotationSourceListResponse,
    AnnotationSubmitRequest,
    AnnotationTrainingManifestListResponse,
    AnnotationTrainingManifestRequest,
    AnnotationTrainingManifestResponse,
    AnnotationTrainingManifestSummary,
    AnnotationVersionCreateRequest,
    AnnotationVersionHistoryResponse,
    ManualAnnotationRecord,
)
from backend.osteo_vision_api.domains.cases.repository import CaseRepository
from backend.osteo_vision_api.domains.cases.schemas import ReviewActorIdentity
from backend.osteo_vision_api.services.manual_annotation_service import (
    AnnotationPermissionError,
    AnnotationValidationError,
    ManualAnnotationService,
)


def router(repo: CaseRepository, service: ManualAnnotationService) -> APIRouter:
    api = APIRouter()

    @api.get(
        "/cases/{case_id}/annotation-sources",
        response_model=AnnotationSourceListResponse,
    )
    def list_annotation_sources(case_id: str) -> AnnotationSourceListResponse:
        case = require_case(repo, case_id)
        with _translate_annotation_errors():
            return service.list_sources(case)
        raise AssertionError("unreachable")

    @api.get(
        "/cases/{case_id}/annotations",
        response_model=list[ManualAnnotationRecord],
    )
    def list_annotations(
        case_id: str,
        annotation_status: AnnotationStatus | None = Query(default=None, alias="status"),
        label: AnnotationLabel | None = None,
    ) -> list[ManualAnnotationRecord]:
        require_case(repo, case_id)
        records = service.list_annotations(case_id)
        if annotation_status is not None:
            records = [record for record in records if record.status == annotation_status]
        if label is not None:
            records = [record for record in records if record.label == label]
        return records

    @api.post(
        "/cases/{case_id}/annotations",
        response_model=ManualAnnotationRecord,
        status_code=status.HTTP_201_CREATED,
    )
    def create_annotation(
        case_id: str,
        request: AnnotationCreateRequest,
        actor: Annotated[ReviewActorIdentity, Depends(resolve_review_actor)],
    ) -> ManualAnnotationRecord:
        case = require_case(repo, case_id)
        with _translate_annotation_errors():
            return service.create_annotation(case, request, actor)
        raise AssertionError("unreachable")

    @api.get(
        "/cases/{case_id}/annotations/{annotation_id}",
        response_model=ManualAnnotationRecord,
    )
    def get_annotation(case_id: str, annotation_id: str) -> ManualAnnotationRecord:
        require_case(repo, case_id)
        with _translate_annotation_errors():
            return service.get_annotation(case_id, annotation_id)
        raise AssertionError("unreachable")

    @api.put(
        "/cases/{case_id}/annotations/{annotation_id}/versions",
        response_model=ManualAnnotationRecord,
    )
    def save_annotation_version(
        case_id: str,
        annotation_id: str,
        request: AnnotationVersionCreateRequest,
        actor: Annotated[ReviewActorIdentity, Depends(resolve_review_actor)],
    ) -> ManualAnnotationRecord:
        require_case(repo, case_id)
        with _translate_annotation_errors():
            return service.save_version(case_id, annotation_id, request, actor)
        raise AssertionError("unreachable")

    @api.get(
        "/cases/{case_id}/annotations/{annotation_id}/versions",
        response_model=AnnotationVersionHistoryResponse,
    )
    def annotation_version_history(case_id: str, annotation_id: str) -> AnnotationVersionHistoryResponse:
        require_case(repo, case_id)
        with _translate_annotation_errors():
            return service.version_history(case_id, annotation_id)
        raise AssertionError("unreachable")

    @api.post(
        "/cases/{case_id}/annotations/{annotation_id}/submit",
        response_model=ManualAnnotationRecord,
    )
    def submit_annotation(
        case_id: str,
        annotation_id: str,
        request: AnnotationSubmitRequest,
        actor: Annotated[ReviewActorIdentity, Depends(resolve_review_actor)],
    ) -> ManualAnnotationRecord:
        require_case(repo, case_id)
        with _translate_annotation_errors():
            return service.submit(
                case_id,
                annotation_id,
                expected_version=request.expected_version,
                notes=request.notes,
                actor=actor,
            )
        raise AssertionError("unreachable")

    @api.post(
        "/cases/{case_id}/annotations/{annotation_id}/review",
        response_model=ManualAnnotationRecord,
    )
    def review_annotation(
        case_id: str,
        annotation_id: str,
        request: AnnotationReviewRequest,
        actor: Annotated[ReviewActorIdentity, Depends(resolve_review_actor)],
    ) -> ManualAnnotationRecord:
        require_case(repo, case_id)
        with _translate_annotation_errors():
            return service.review(
                case_id,
                annotation_id,
                expected_version=request.expected_version,
                decision=request.decision,
                notes=request.notes,
                actor=actor,
            )
        raise AssertionError("unreachable")

    @api.delete(
        "/cases/{case_id}/annotations/{annotation_id}",
        response_model=AnnotationDeleteResponse,
    )
    def delete_annotation_draft(
        case_id: str,
        annotation_id: str,
        actor: Annotated[ReviewActorIdentity, Depends(resolve_review_actor)],
    ) -> AnnotationDeleteResponse:
        require_case(repo, case_id)
        with _translate_annotation_errors():
            service.delete_draft(case_id, annotation_id, actor)
        return AnnotationDeleteResponse(deleted=True, annotation_id=annotation_id)

    @api.post(
        "/annotation-training-manifests",
        response_model=AnnotationTrainingManifestResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_annotation_training_manifest(
        request: AnnotationTrainingManifestRequest,
        actor: Annotated[ReviewActorIdentity, Depends(resolve_review_actor)],
    ) -> AnnotationTrainingManifestResponse:
        with _translate_annotation_errors():
            _require_trusted_manifest_actor(actor)
            return service.export_training_manifest(
                case_ids=request.case_ids or None,
                include_ineligible=request.include_ineligible,
                actor=actor,
            )
        raise AssertionError("unreachable")

    @api.get("/annotation-training-manifests", response_model=AnnotationTrainingManifestListResponse)
    def list_annotation_training_manifests(
        actor: Annotated[ReviewActorIdentity, Depends(resolve_review_actor)],
    ) -> AnnotationTrainingManifestListResponse:
        with _translate_annotation_errors():
            _require_trusted_manifest_actor(actor)
            return service.list_training_manifests()
        raise AssertionError("unreachable")

    @api.get("/annotation-training-manifests/{manifest_id}", response_model=AnnotationTrainingManifestSummary)
    def get_annotation_training_manifest(
        manifest_id: str,
        actor: Annotated[ReviewActorIdentity, Depends(resolve_review_actor)],
    ) -> AnnotationTrainingManifestSummary:
        with _translate_annotation_errors():
            _require_trusted_manifest_actor(actor)
            return service.get_training_manifest(manifest_id)
        raise AssertionError("unreachable")

    return api


def _require_trusted_manifest_actor(actor: ReviewActorIdentity) -> None:
    if actor.auth_source == "local_unverified_session" or actor.role.value not in {"physician", "project_reviewer"}:
        raise AnnotationPermissionError(
            "training manifest access requires an authenticated physician or project reviewer"
        )


@contextmanager
def _translate_annotation_errors() -> Iterator[None]:
    try:
        yield
    except AnnotationNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "annotation_not_found", "message": str(exc)},
        ) from exc
    except AnnotationPermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail={"code": "annotation_permission_denied", "message": str(exc)},
        ) from exc
    except AnnotationVersionConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "annotation_version_conflict",
                "message": str(exc),
                "annotation_id": exc.annotation_id,
                "expected_version": exc.expected_version,
                "actual_version": exc.actual_version,
            },
        ) from exc
    except AnnotationStateConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "annotation_state_conflict",
                "message": str(exc),
                "annotation_id": exc.annotation_id,
                "expected_status": exc.expected_status,
                "actual_status": exc.actual_status,
            },
        ) from exc
    except AnnotationValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "annotation_validation_failed", "message": str(exc)},
        ) from exc
