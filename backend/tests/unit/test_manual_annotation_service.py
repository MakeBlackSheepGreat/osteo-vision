from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

import backend.osteo_vision_api.services.manual_annotation_service as manual_annotation_service
from backend.osteo_vision_api.core.artifacts import checksum_for_file
from backend.osteo_vision_api.domains.annotations.enums import AnnotationReviewDecision
from backend.osteo_vision_api.domains.annotations.repository import AnnotationRepository
from backend.osteo_vision_api.domains.annotations.schemas import (
    AnnotationCreateRequest,
    AnnotationGeometry,
    AnnotationSourceRequest,
)
from backend.osteo_vision_api.domains.cases.enums import InputChannel, ReviewerRole
from backend.osteo_vision_api.domains.cases.repository import JsonCaseRepository
from backend.osteo_vision_api.domains.cases.schemas import (
    AnalysisRun,
    CandidateRegion,
    CaseInputAsset,
    CaseRecord,
    HospitalIntakeMetadata,
    ReviewActorIdentity,
)
from backend.osteo_vision_api.services.manual_annotation_service import ManualAnnotationService


def test_video_keyframe_and_model_candidate_sources_create_full_size_masks(tmp_path: Path) -> None:
    frame_path = tmp_path / "keyframe.jpg"
    Image.fromarray(np.full((48, 64, 3), 120, dtype=np.uint8)).save(frame_path)
    video_path = tmp_path / "source.mp4"
    video_path.write_bytes(b"test-only-video-reference")
    now = datetime.now(timezone.utc)
    run = AnalysisRun(
        run_id="run_1",
        case_id="case_1",
        fused_outputs={
            "source_path": str(video_path),
            "frame_details": [
                {
                    "frame_index": 12,
                    "timestamp_sec": 1.5,
                    "evidence_path": str(frame_path),
                }
            ],
        },
        candidate_regions=[
            CandidateRegion(
                candidate_id="candidate_1",
                run_id="run_1",
                risk_type="boundary_risk",
                metadata={"frame_index": 12, "evidence_path": str(frame_path)},
            )
        ],
    )
    case = CaseRecord(
        case_id="case_1",
        title="video annotation",
        created_at=now,
        updated_at=now,
        inputs=[
            CaseInputAsset(
                input_id="video_1",
                channel=InputChannel.VIDEO,
                path=str(video_path),
                mime_type="video/mp4",
            )
        ],
        analysis_runs=[run],
    )
    case_repo = JsonCaseRepository(tmp_path / "cases.json")
    case_repo.create(case)
    service = ManualAnnotationService(
        AnnotationRepository(tmp_path / "annotations.sqlite"),
        case_repo,
        tmp_path / "artifacts",
    )
    sources = service.list_sources(case).sources
    assert {source.source_type.value for source in sources} == {"video_keyframe", "model_candidate"}
    assert all(Path(source.preview_path).is_file() for source in sources)
    candidate = next(source for source in sources if source.source_type.value == "model_candidate")
    assert candidate.label_hint.value == "boundary_risk"

    actor = ReviewActorIdentity(
        actor_id="engineering-test",
        role=ReviewerRole.ENGINEERING_REVIEWER,
        institution="Osteo Vision Engineering",
        auth_source="local_unverified_session",
    )
    request = AnnotationCreateRequest(
        source=AnnotationSourceRequest(
            source_type="video_keyframe",
            input_id="video_1",
            run_id="run_1",
            frame_index=12,
        ),
        label="uncertain",
        geometry=AnnotationGeometry.model_validate(
            {
                "coordinate_space": "normalized",
                "operations": [
                    {
                        "tool": "polygon",
                        "points": [
                            {"x": 0.2, "y": 0.2},
                            {"x": 0.8, "y": 0.2},
                            {"x": 0.8, "y": 0.8},
                            {"x": 0.2, "y": 0.8},
                        ],
                    }
                ],
            }
        ),
    )
    annotation = service.create_annotation(case, request, actor)
    assert annotation.source.frame_index == 12
    assert annotation.original_width == 64
    assert annotation.original_height == 48
    with Image.open(annotation.mask_path) as mask:
        assert mask.size == (64, 48)
        assert np.count_nonzero(np.asarray(mask)) > 0

    ignore_annotation = service.create_annotation(
        case,
        AnnotationCreateRequest.model_validate({**request.model_dump(mode="json"), "label": "ignore"}),
        actor,
    )
    assert ignore_annotation.label.value == "ignore"
    assert Path(ignore_annotation.mask_path).is_file()


def test_list_sources_reuses_run_video_lookup_and_indexes_candidate_frames(tmp_path: Path) -> None:
    frame_path = tmp_path / "keyframe.jpg"
    Image.fromarray(np.full((24, 32, 3), 120, dtype=np.uint8)).save(frame_path)
    video_path = tmp_path / "source.mp4"
    video_path.write_bytes(b"test-only-video-reference")
    now = datetime.now(timezone.utc)
    run = AnalysisRun(
        run_id="run-indexed",
        case_id="case-indexed",
        fused_outputs={
            "source_path": str(video_path),
            "frame_details": [{"frame_index": index, "evidence_path": str(frame_path)} for index in range(3)],
        },
        candidate_regions=[
            CandidateRegion(
                candidate_id="candidate-indexed",
                run_id="run-indexed",
                risk_type="boundary_risk",
                metadata={"frame_index": 2},
            )
        ],
    )
    case = CaseRecord(
        case_id="case-indexed",
        title="indexed annotation sources",
        created_at=now,
        updated_at=now,
        inputs=[
            CaseInputAsset(
                input_id="video-indexed",
                channel=InputChannel.VIDEO,
                path=str(video_path),
                mime_type="video/mp4",
            )
        ],
        analysis_runs=[run],
    )
    case_repo = JsonCaseRepository(tmp_path / "cases.json")
    case_repo.create(case)
    service = ManualAnnotationService(
        AnnotationRepository(tmp_path / "annotations.sqlite"),
        case_repo,
        tmp_path / "artifacts",
    )

    with (
        patch.object(
            manual_annotation_service, "_run_video_asset", wraps=manual_annotation_service._run_video_asset
        ) as lookup,
        patch.object(manual_annotation_service, "_find_frame", side_effect=AssertionError("linear frame lookup used")),
    ):
        sources = service.list_sources(case).sources

    assert len(sources) == 4
    assert lookup.call_count == 1
    candidate = next(source for source in sources if source.source_type.value == "model_candidate")
    assert candidate.source_path == str(frame_path.resolve())


def test_training_eligibility_requires_a_distinct_physician_reviewer(tmp_path: Path) -> None:
    image_path = tmp_path / "artifacts" / "uploads" / "source.jpg"
    image_path.parent.mkdir(parents=True)
    Image.fromarray(np.full((32, 48, 3), 120, dtype=np.uint8)).save(image_path)
    now = datetime.now(timezone.utc)
    case = CaseRecord(
        case_id="case-independent-review",
        title="independent physician review",
        created_at=now,
        updated_at=now,
        intake_metadata=HospitalIntakeMetadata(
            source_organization="Example Stomatology Hospital",
            external_case_id="HOSP_CASE_REVIEW",
            batch_ids=["batch-training-review"],
            handover_ids=["handover-training-review"],
            authorization_status="approved",
            usage_scope="research_training",
            deidentification_confirmed=True,
            deidentification_method="institutional export review",
            mapping_held_by_institution=True,
            target_condition_confirmed=True,
            admission_status="target_registry_ready",
        ),
        inputs=[
            CaseInputAsset(
                input_id="input-review",
                channel=InputChannel.WHITE_LIGHT,
                path=str(image_path),
                mime_type="image/jpeg",
                metadata={
                    "source_type": "institutional_handover",
                    "source_organization": "Example Stomatology Hospital",
                    "external_case_id": "HOSP_CASE_REVIEW",
                    "admission_status": "admitted",
                    "authorization_status": "approved",
                    "usage_scope": "research_training",
                    "deidentification_confirmed": True,
                    "batch_id": "batch-training-review",
                    "intake_record_id": "batch-training-review_0001",
                    "sha256": checksum_for_file(image_path),
                },
            )
        ],
    )
    case_repo = JsonCaseRepository(tmp_path / "cases.json")
    case_repo.create(case)
    service = ManualAnnotationService(
        AnnotationRepository(tmp_path / "annotations.sqlite"),
        case_repo,
        tmp_path / "artifacts",
    )
    author = _physician("doctor-author")
    reviewer = _physician("doctor-reviewer")
    request = AnnotationCreateRequest(
        source=AnnotationSourceRequest(source_type="case_jpeg", input_id="input-review"),
        label="lesion",
        geometry=AnnotationGeometry.model_validate(
            {
                "coordinate_space": "image_pixels",
                "operations": [
                    {
                        "tool": "polygon",
                        "points": [
                            {"x": 5, "y": 5},
                            {"x": 30, "y": 5},
                            {"x": 30, "y": 25},
                            {"x": 5, "y": 25},
                        ],
                    }
                ],
            }
        ),
    )

    same_reviewer_record = service.create_annotation(case, request, author)
    service.submit(
        case.case_id,
        same_reviewer_record.annotation_id,
        expected_version=1,
        notes=None,
        actor=author,
    )
    same_reviewer_result = service.review(
        case.case_id,
        same_reviewer_record.annotation_id,
        expected_version=1,
        decision=AnnotationReviewDecision.ACCEPTED,
        notes=None,
        actor=author,
    )
    assert same_reviewer_result.status.value == "accepted"
    assert same_reviewer_result.training_eligible is False
    assert same_reviewer_result.sample_weight == 0.0
    assert same_reviewer_result.training_exclusion_reason == "independent_physician_review_required"

    independently_reviewed_record = service.create_annotation(case, request, author)
    service.submit(
        case.case_id,
        independently_reviewed_record.annotation_id,
        expected_version=1,
        notes=None,
        actor=author,
    )
    independently_reviewed_result = service.review(
        case.case_id,
        independently_reviewed_record.annotation_id,
        expected_version=1,
        decision=AnnotationReviewDecision.MODIFIED,
        notes=None,
        actor=reviewer,
    )
    assert independently_reviewed_result.status.value == "modified"
    assert independently_reviewed_result.training_eligible is True
    assert independently_reviewed_result.sample_weight == 4.0
    assert independently_reviewed_result.training_exclusion_reason is None

    unsafe_legacy_record = same_reviewer_result.model_copy(
        update={
            "training_eligible": True,
            "sample_weight": 4.0,
            "training_exclusion_reason": None,
        }
    )
    service.repository.update(
        unsafe_legacy_record,
        expected_version=unsafe_legacy_record.current_version,
        expected_status=unsafe_legacy_record.status,
    )
    manifest = service.export_training_manifest(
        case_ids=[case.case_id],
        include_ineligible=True,
        actor=reviewer,
    )
    legacy_row = next(row for row in manifest.records if row["annotation_id"] == unsafe_legacy_record.annotation_id)
    admitted_row = next(
        row for row in manifest.records if row["annotation_id"] == independently_reviewed_record.annotation_id
    )
    assert admitted_row["training_eligible"] is True
    assert admitted_row["source_input_checksum_verified"] is True
    assert admitted_row["source_input_admission_status"] == "admitted"
    assert legacy_row["training_eligible"] is False
    assert legacy_row["sample_weight"] == 0.0
    assert "independent_physician_review_required" in legacy_row["exclusion_reason"]

    stored_case = case_repo.get(case.case_id)
    assert stored_case is not None
    case_repo.save(stored_case.model_copy(update={"intake_metadata": None}))
    withheld = service.export_training_manifest(
        case_ids=[case.case_id],
        include_ineligible=True,
        actor=reviewer,
    )
    withheld_row = next(
        row for row in withheld.records if row["annotation_id"] == independently_reviewed_record.annotation_id
    )
    assert withheld_row["training_eligible"] is False
    assert withheld_row["sample_weight"] == 0.0
    assert "case_intake_metadata_missing" in withheld_row["exclusion_reason"]

    stored_case = case_repo.get(case.case_id)
    assert stored_case is not None
    assert case.intake_metadata is not None
    denied_intake = case.intake_metadata.model_copy(update={"usage_scope": "research_no_training"})
    case_repo.save(stored_case.model_copy(update={"intake_metadata": denied_intake}))
    denied_scope = service.export_training_manifest(
        case_ids=[case.case_id],
        include_ineligible=True,
        actor=reviewer,
    )
    denied_row = next(
        row for row in denied_scope.records if row["annotation_id"] == independently_reviewed_record.annotation_id
    )
    assert denied_row["training_eligible"] is False
    assert "case_training_usage_not_authorized" in denied_row["exclusion_reason"]


def _physician(actor_id: str) -> ReviewActorIdentity:
    return ReviewActorIdentity(
        actor_id=actor_id,
        role=ReviewerRole.PHYSICIAN,
        institution="Example Stomatology Hospital",
        auth_source="institution_sso",
    )
