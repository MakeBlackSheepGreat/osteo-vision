from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from backend.osteo_vision_api.domains.cases.enums import ReviewerRole, ReviewState
from backend.osteo_vision_api.domains.cases.repository import JsonCaseRepository
from backend.osteo_vision_api.domains.cases.schemas import (
    AnalysisRun,
    BoneGateMaskCreateRequest,
    CandidateRegion,
    CaseRecord,
    RegionOfInterest,
    RegionUpdateRequest,
    ReviewActorIdentity,
    ReviewEvent,
)
from backend.osteo_vision_api.services.review_service import PromptFallbackSafetyError, ReviewService


def test_review_state_transition_is_saved(tmp_path) -> None:
    repo = JsonCaseRepository(tmp_path / "cases.json")
    case = repo.create(CaseRecord(case_id="case_review", title="review"))
    updated = ReviewService(repo).update_region(
        case,
        "roi_1",
        RegionUpdateRequest(review_state=ReviewState.MODIFIED, geometry={"type": "polygon"}),
        ReviewActorIdentity(
            actor_id="engineering-test",
            role=ReviewerRole.ENGINEERING_REVIEWER,
            institution="Osteo Vision Engineering",
            auth_source="test_identity",
        ),
    )

    assert updated.rois[0].review_state == ReviewState.MODIFIED
    assert repo.get("case_review").rois[0].review_state == ReviewState.MODIFIED
    assert updated.review_events[-1].role == ReviewerRole.ENGINEERING_REVIEWER


def test_review_summary_counts_regions_and_candidates_in_single_pass(tmp_path: Path) -> None:
    case = CaseRecord(
        case_id="case_review_summary",
        title="review summary",
        rois=[
            RegionOfInterest(roi_id="roi-a", case_id="case_review_summary", review_state=ReviewState.ACCEPTED),
            RegionOfInterest(roi_id="roi-b", case_id="case_review_summary", review_state=ReviewState.MODIFIED),
            RegionOfInterest(roi_id="roi-c", case_id="case_review_summary", review_state=ReviewState.REJECTED),
        ],
        analysis_runs=[
            AnalysisRun(
                run_id="run-summary",
                case_id="case_review_summary",
                candidate_regions=[
                    CandidateRegion(candidate_id="candidate-a", run_id="run-summary", status=ReviewState.ACCEPTED),
                    CandidateRegion(candidate_id="candidate-b", run_id="run-summary", status=ReviewState.MODIFIED),
                    CandidateRegion(candidate_id="candidate-c", run_id="run-summary", status=ReviewState.REJECTED),
                    CandidateRegion(candidate_id="candidate-d", run_id="run-summary"),
                ],
            )
        ],
    )
    repo = JsonCaseRepository(tmp_path / "cases.json")
    service = ReviewService(repo)

    summary = service._review_summary(case)

    assert summary["accepted_regions"] == 1
    assert summary["modified_regions"] == 1
    assert summary["rejected_regions"] == 1
    assert summary["accepted_candidates"] == 1
    assert summary["modified_candidates"] == 1
    assert summary["rejected_candidates"] == 1
    assert summary["total_review_events"] == 0


def test_legacy_review_event_is_loaded_as_unverified() -> None:
    event = ReviewEvent.model_validate(
        {
            "event_id": "event_legacy",
            "case_id": "case_review",
            "actor": "doctor",
            "action": "accept",
            "target_id": "roi_1",
        }
    )

    assert event.actor_id == "doctor"
    assert event.role == ReviewerRole.LEGACY_UNVERIFIED
    assert event.institution == "unrecorded"
    assert event.auth_source == "legacy_event"


def test_strict_runtime_disables_prompt_fallback_before_adapter_execution(
    tmp_path: Path,
) -> None:
    config = tmp_path / "strict.yml"
    config.write_text(
        yaml.safe_dump(
            {
                "runtime": {
                    "runtime_profile": "strict_runtime",
                    "strict_startup": True,
                    "allow_prompt_fallback": False,
                    "models": [
                        {
                            "model_id": "medsam2_osteo_promptable",
                            "family": "fixture",
                            "enabled": True,
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    source = tmp_path / "source.png"
    source.write_bytes(b"adapter must not read this file")
    candidate = CandidateRegion(
        candidate_id="candidate_1",
        run_id="run_1",
        metadata={
            "source_path": str(source),
            "bbox_normalized": {
                "type": "rect",
                "coordinate_space": "normalized",
                "x": 0.1,
                "y": 0.1,
                "width": 0.5,
                "height": 0.5,
            },
        },
    )
    case = CaseRecord(
        case_id="case_prompt_gate",
        title="prompt gate",
        analysis_runs=[
            AnalysisRun(
                run_id="run_1",
                case_id="case_prompt_gate",
                candidate_regions=[candidate],
            )
        ],
    )
    repo = JsonCaseRepository(tmp_path / "cases.json")
    repo.create(case)
    actor = ReviewActorIdentity(
        actor_id="engineering-test",
        role=ReviewerRole.ENGINEERING_REVIEWER,
        institution="Osteo Vision Engineering",
        auth_source="test_identity",
    )

    with pytest.raises(PromptFallbackSafetyError) as exc_info:
        ReviewService(repo, inference_config_path=config).generate_candidate_bone_gate_mask(
            case,
            candidate.candidate_id,
            BoneGateMaskCreateRequest(geometry=candidate.metadata["bbox_normalized"]),
            actor,
        )

    assert exc_info.value.code == "prompt_fallback_disabled_by_runtime_policy"
    assert exc_info.value.runtime_profile == "strict_runtime"
