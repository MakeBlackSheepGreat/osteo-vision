from __future__ import annotations

from backend.src.domains.cases.enums import ReviewState
from backend.src.domains.cases.repository import JsonCaseRepository
from backend.src.domains.cases.schemas import CaseRecord, RegionUpdateRequest
from backend.src.services.review_service import ReviewService


def test_review_state_transition_is_saved(tmp_path) -> None:
    repo = JsonCaseRepository(tmp_path / "cases.json")
    case = repo.create(CaseRecord(case_id="case_review", title="review"))
    updated = ReviewService(repo).update_region(
        case,
        "roi_1",
        RegionUpdateRequest(review_state=ReviewState.MODIFIED, geometry={"type": "polygon"}),
    )

    assert updated.rois[0].review_state == ReviewState.MODIFIED
    assert repo.get("case_review").rois[0].review_state == ReviewState.MODIFIED
