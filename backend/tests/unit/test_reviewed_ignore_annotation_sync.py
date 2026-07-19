from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from backend.src.domains.annotations.enums import AnnotationReviewDecision
from backend.src.domains.annotations.repository import AnnotationRepository
from backend.src.domains.annotations.schemas import AnnotationCreateRequest, AnnotationGeometry, AnnotationSourceRequest
from backend.src.domains.cases.enums import ReviewerRole, ReviewState
from backend.src.domains.cases.repository import JsonCaseRepository
from backend.src.domains.cases.schemas import AnalysisRun, CandidateRegion, CaseRecord, ReviewActorIdentity
from backend.src.services.manual_annotation_service import AnnotationValidationError, ManualAnnotationService
from backend.src.services.review_service import ReviewService


def _physician(actor_id: str = "doctor-ignore") -> ReviewActorIdentity:
    return ReviewActorIdentity(
        actor_id=actor_id,
        role=ReviewerRole.PHYSICIAN,
        institution="Test Stomatology Hospital",
        auth_source="institution_sso",
    )


def _engineering() -> ReviewActorIdentity:
    return ReviewActorIdentity(
        actor_id="engineering-ignore",
        role=ReviewerRole.ENGINEERING_REVIEWER,
        institution="Osteo Vision Engineering",
        auth_source="local_unverified_session",
    )


def _build_services(tmp_path: Path) -> tuple[JsonCaseRepository, AnnotationRepository, ManualAnnotationService]:
    source_path = tmp_path / "candidate.png"
    probability_path = tmp_path / "probability.png"
    gate_path = tmp_path / "gate.png"
    source = np.full((10, 10, 3), 90, dtype=np.uint8)
    source[:, :, 1] = np.arange(100, dtype=np.uint8).reshape(10, 10)
    Image.fromarray(source).save(source_path)
    Image.fromarray(np.arange(100, dtype=np.uint8).reshape(10, 10) * 2).save(probability_path)
    Image.fromarray(np.full((10, 10), 255, dtype=np.uint8)).save(gate_path)
    signal_masks = {
        "schema_version": "osteo-vision-video-signal-masks-v2",
        "bone_gate_mask": {
            "available": True,
            "path": str(gate_path),
            "review_state": "accepted",
            "status": "physician_accepted",
        },
        "fluorescence_signal_mask": {
            "available": True,
            "probability_path": str(probability_path),
            "threshold": 0.5,
        },
    }
    manifest_path = tmp_path / "video_segmentation_manifest.json"
    manifest_path.write_text(
        json.dumps({"frames": [{"frame_index": 0, "video_signal_segmentation": signal_masks}], "summary": {}}),
        encoding="utf-8",
    )
    candidate = CandidateRegion(
        candidate_id="candidate-ignore",
        run_id="run-ignore",
        risk_type="boundary_risk",
        status=ReviewState.ACCEPTED,
        metadata={
            "source_path": str(source_path),
            "frame_index": 0,
            "frame_order": 1,
            "image_width": 10,
            "image_height": 10,
            "video_signal_segmentation": signal_masks,
            "signal_masks": signal_masks,
        },
    )
    run = AnalysisRun(
        run_id="run-ignore",
        case_id="case-ignore",
        status="completed",
        candidate_regions=[candidate],
        fused_outputs={
            "frame_details": [
                {
                    "frame_index": 0,
                    "frame_order": 1,
                    "evidence_path": str(source_path),
                    "video_signal_segmentation": signal_masks,
                }
            ],
            "video_segmentation_manifest_path": str(manifest_path),
        },
    )
    now = datetime.now(timezone.utc)
    case = CaseRecord(
        case_id="case-ignore",
        title="reviewed ignore sync",
        created_at=now,
        updated_at=now,
        analysis_runs=[run],
    )
    case_repository = JsonCaseRepository(tmp_path / "cases.json")
    case_repository.create(case)
    annotation_repository = AnnotationRepository(tmp_path / "annotations.sqlite")
    review_service = ReviewService(
        case_repository,
        annotation_repository=annotation_repository,
        artifact_root=tmp_path / "artifacts",
    )
    annotation_service = ManualAnnotationService(
        annotation_repository,
        case_repository,
        tmp_path / "artifacts",
        ignore_annotation_synchronizer=review_service,
    )
    return case_repository, annotation_repository, annotation_service


def _geometry(points: list[tuple[int, int]]) -> AnnotationGeometry:
    return AnnotationGeometry.model_validate(
        {
            "coordinate_space": "image_pixels",
            "operations": [
                {
                    "tool": "polygon",
                    "mode": "add",
                    "points": [{"x": x, "y": y} for x, y in points],
                }
            ],
        }
    )


def _create_and_review_ignore(
    service: ManualAnnotationService,
    case_repository: JsonCaseRepository,
    *,
    actor: ReviewActorIdentity,
    reviewer: ReviewActorIdentity,
    points: list[tuple[int, int]],
):
    case = case_repository.get("case-ignore")
    assert case is not None
    record = service.create_annotation(
        case,
        AnnotationCreateRequest(
            source=AnnotationSourceRequest(
                source_type="model_candidate",
                run_id="run-ignore",
                candidate_id="candidate-ignore",
            ),
            label="ignore",
            geometry=_geometry(points),
        ),
        actor,
    )
    service.submit(
        record.case_id,
        record.annotation_id,
        expected_version=record.current_version,
        notes="physician ignore review",
        actor=actor,
    )
    return service.review(
        record.case_id,
        record.annotation_id,
        expected_version=record.current_version,
        decision=AnnotationReviewDecision.ACCEPTED,
        notes="accepted ignore region",
        actor=reviewer,
    )


def _candidate(case_repository: JsonCaseRepository) -> CandidateRegion:
    case = case_repository.get("case-ignore")
    assert case is not None
    return case.analysis_runs[0].candidate_regions[0]


def test_trusted_physician_ignore_annotations_union_and_update_all_evidence(tmp_path: Path) -> None:
    case_repository, _, service = _build_services(tmp_path)
    physician = _physician()
    reviewer = _physician("doctor-ignore-reviewer")
    first = _create_and_review_ignore(
        service,
        case_repository,
        actor=physician,
        reviewer=reviewer,
        points=[(0, 0), (3, 0), (3, 3), (0, 3)],
    )
    second = _create_and_review_ignore(
        service,
        case_repository,
        actor=physician,
        reviewer=reviewer,
        points=[(6, 6), (9, 6), (9, 9), (6, 9)],
    )
    assert first.training_eligible is False
    assert second.training_eligible is False
    assert first.training_exclusion_reason == "case_intake_metadata_missing"
    assert second.training_exclusion_reason == "case_intake_metadata_missing"

    case = case_repository.get("case-ignore")
    assert case is not None
    candidate = case.analysis_runs[0].candidate_regions[0]
    signal_masks = candidate.metadata["video_signal_segmentation"]
    union = signal_masks["physician_ignore_mask"]
    assert union["available"] is True
    assert union["annotation_count"] == 2
    assert {item["annotation_id"] for item in union["annotations"]} == {
        first.annotation_id,
        second.annotation_id,
    }
    assert all(item["version"] == 1 and len(item["sha256"]) == 64 for item in union["annotations"])
    assert all(item["reviewer"]["role"] == "physician" for item in union["annotations"])
    with Image.open(union["path"]) as image:
        union_pixels = int(np.count_nonzero(np.asarray(image, dtype=np.uint8)))
    assert union_pixels == first.positive_pixel_count + second.positive_pixel_count

    spectrum = signal_masks["bone_activity_spectrum"]
    assert spectrum["schema_version"] == "osteo-vision-bone-activity-spectrum-v2"
    assert spectrum["partition_check"]["valid"] is True
    assert spectrum["partition_check"]["classified_px"] + spectrum["partition_check"]["ignore_px"] == 100
    physician_sources = [
        item for item in spectrum["ignore_region"]["sources"] if item["source_type"] == "physician_ignore_annotation"
    ]
    assert {item["annotation_id"] for item in physician_sources} == {first.annotation_id, second.annotation_id}

    frame_signal = case.analysis_runs[0].fused_outputs["frame_details"][0]["video_signal_segmentation"]
    assert frame_signal["physician_ignore_mask"]["sha256"] == union["sha256"]
    manifest = json.loads((tmp_path / "video_segmentation_manifest.json").read_text(encoding="utf-8"))
    assert manifest["frames"][0]["video_signal_segmentation"]["physician_ignore_mask"]["sha256"] == union["sha256"]
    evidence_paths = {str(Path(item.path).resolve()) for item in case.artifacts}
    assert str(Path(union["path"]).resolve()) in evidence_paths
    assert str(Path(first.mask_path).resolve()) in evidence_paths
    assert str(Path(second.mask_path).resolve()) in evidence_paths
    assert case.review_events[-1].action == "physician_ignore_annotations_synchronized"


def test_engineering_authored_ignore_annotation_never_changes_activity_space(tmp_path: Path) -> None:
    case_repository, _, service = _build_services(tmp_path)
    accepted = _create_and_review_ignore(
        service,
        case_repository,
        actor=_engineering(),
        reviewer=_physician(),
        points=[(0, 0), (4, 0), (4, 4), (0, 4)],
    )
    assert accepted.status == AnnotationReviewDecision.ACCEPTED.value
    assert accepted.training_eligible is False
    signal_masks = _candidate(case_repository).metadata["video_signal_segmentation"]
    assert "physician_ignore_mask" not in signal_masks
    assert "bone_activity_spectrum" not in signal_masks


def test_draft_submitted_and_rejected_ignore_annotations_never_change_activity_space(tmp_path: Path) -> None:
    case_repository, _, service = _build_services(tmp_path)
    physician = _physician()
    case = case_repository.get("case-ignore")
    assert case is not None
    record = service.create_annotation(
        case,
        AnnotationCreateRequest(
            source=AnnotationSourceRequest(
                source_type="model_candidate",
                run_id="run-ignore",
                candidate_id="candidate-ignore",
            ),
            label="ignore",
            geometry=_geometry([(0, 0), (4, 0), (4, 4), (0, 4)]),
        ),
        physician,
    )
    assert "physician_ignore_mask" not in _candidate(case_repository).metadata["video_signal_segmentation"]
    submitted = service.submit(
        record.case_id,
        record.annotation_id,
        expected_version=record.current_version,
        notes=None,
        actor=physician,
    )
    assert submitted.status.value == "submitted"
    assert "physician_ignore_mask" not in _candidate(case_repository).metadata["video_signal_segmentation"]
    rejected = service.review(
        record.case_id,
        record.annotation_id,
        expected_version=record.current_version,
        decision=AnnotationReviewDecision.REJECTED,
        notes="not an ignore region",
        actor=physician,
    )
    assert rejected.status.value == "rejected"
    assert "physician_ignore_mask" not in _candidate(case_repository).metadata["video_signal_segmentation"]


def test_candidate_source_change_blocks_acceptance_before_annotation_state_transition(tmp_path: Path) -> None:
    case_repository, annotation_repository, service = _build_services(tmp_path)
    physician = _physician()
    reviewer = _physician("doctor-ignore-reviewer")
    case = case_repository.get("case-ignore")
    assert case is not None
    record = service.create_annotation(
        case,
        AnnotationCreateRequest(
            source=AnnotationSourceRequest(
                source_type="model_candidate",
                run_id="run-ignore",
                candidate_id="candidate-ignore",
            ),
            label="ignore",
            geometry=_geometry([(0, 0), (4, 0), (4, 4), (0, 4)]),
        ),
        physician,
    )
    service.submit(
        record.case_id,
        record.annotation_id,
        expected_version=record.current_version,
        notes=None,
        actor=physician,
    )
    candidate_source = Path(_candidate(case_repository).metadata["source_path"])
    Image.fromarray(np.zeros((10, 10, 3), dtype=np.uint8)).save(candidate_source)

    try:
        service.review(
            record.case_id,
            record.annotation_id,
            expected_version=record.current_version,
            decision=AnnotationReviewDecision.ACCEPTED,
            notes=None,
            actor=reviewer,
        )
    except AnnotationValidationError as exc:
        assert "source checksum changed" in str(exc)
    else:
        raise AssertionError("changed candidate source must block ignore acceptance")
    stored = annotation_repository.get(record.annotation_id)
    assert stored is not None
    assert stored.status.value == "submitted"
    assert "physician_ignore_mask" not in _candidate(case_repository).metadata["video_signal_segmentation"]


def test_corrupt_prior_qualified_ignore_mask_fails_closed_and_clears_stale_evidence(tmp_path: Path) -> None:
    case_repository, _, service = _build_services(tmp_path)
    physician = _physician()
    reviewer = _physician("doctor-ignore-reviewer")
    first = _create_and_review_ignore(
        service,
        case_repository,
        actor=physician,
        reviewer=reviewer,
        points=[(0, 0), (3, 0), (3, 3), (0, 3)],
    )
    before = _candidate(case_repository).metadata["video_signal_segmentation"]
    stale_paths = {
        str(Path(before["bone_activity_spectrum"][key]["path"]).resolve())
        for key in ("low_activity_candidate", "transition_candidate", "high_activity_candidate", "ignore_region")
    }
    Path(first.mask_path).write_bytes(b"tampered-mask")

    _create_and_review_ignore(
        service,
        case_repository,
        actor=physician,
        reviewer=reviewer,
        points=[(6, 6), (9, 6), (9, 9), (6, 9)],
    )

    case = case_repository.get("case-ignore")
    assert case is not None
    candidate = case.analysis_runs[0].candidate_regions[0]
    signal_masks = candidate.metadata["video_signal_segmentation"]
    assert candidate.metadata["physician_ignore_sync_status"] == "failed_closed"
    assert candidate.metadata["physician_ignore_sync_failure_code"] == "ignore_annotation_mask_checksum_mismatch"
    assert signal_masks["physician_ignore_mask"]["available"] is False
    assert len(signal_masks["physician_ignore_mask"]["attempted_annotations"]) == 2
    spectrum = signal_masks["bone_activity_spectrum"]
    assert spectrum["available"] is False
    assert spectrum["activity_class_map_path"] is None
    assert spectrum["ignore_region"]["path"] is None
    assert spectrum["partition_check"]["valid"] is False
    current_evidence = {str(Path(item.path).resolve()) for item in case.artifacts}
    assert stale_paths.isdisjoint(current_evidence)
    assert case.review_events[-1].action == "physician_ignore_annotations_failed_closed"
