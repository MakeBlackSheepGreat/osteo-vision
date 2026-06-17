from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from backend.src.domains.cases.enums import CaseStatus, RegionSource, ReviewState
from backend.src.domains.cases.repository import CaseRepository
from backend.src.domains.cases.schemas import CandidateRegion, CaseRecord, RegionOfInterest, ReviewEvent, ReviewEventCreateRequest, RegionUpdateRequest


class ReviewService:
    def __init__(self, repo: CaseRepository) -> None:
        self.repo = repo

    def update_region(self, case: CaseRecord, region_id: str, request: RegionUpdateRequest) -> CaseRecord:
        rois: list[RegionOfInterest] = []
        found = False
        for roi in case.rois:
            if roi.roi_id != region_id:
                rois.append(roi)
                continue
            found = True
            rois.append(
                roi.model_copy(
                    update={
                        "review_state": request.review_state,
                        "geometry": request.geometry if request.geometry is not None else roi.geometry,
                        "label": request.label if request.label is not None else roi.label,
                    }
                )
            )
        if not found:
            rois.append(
                RegionOfInterest(
                    roi_id=region_id,
                    case_id=case.case_id,
                    source=RegionSource.MANUAL,
                    geometry=request.geometry or {},
                    label=request.label,
                    review_state=request.review_state,
                )
            )
        updated = case.model_copy(update={"rois": rois, "status": CaseStatus.REVIEWING})
        updated = updated.model_copy(update={"review_summary": self._review_summary(updated)})
        self.repo.save(updated)
        return updated

    def add_review_event(self, case: CaseRecord, request: ReviewEventCreateRequest) -> CaseRecord:
        event = ReviewEvent(
            event_id=f"event_{uuid4().hex[:10]}",
            case_id=case.case_id,
            actor="physician",
            action=request.action,
            target_id=request.target_id,
            before_state=request.before_state,
            after_state=request.after_state,
            timestamp=datetime.now(timezone.utc),
            notes=request.notes,
        )
        updated = case.model_copy(update={"review_events": [*case.review_events, event], "status": CaseStatus.REVIEWING})
        updated = updated.model_copy(update={"review_summary": self._review_summary(updated)})
        self.repo.save(updated)
        return updated

    def candidate_to_roi(self, case: CaseRecord, candidate: CandidateRegion) -> RegionOfInterest:
        return RegionOfInterest(
            roi_id=f"roi_{candidate.candidate_id}",
            case_id=case.case_id,
            source=RegionSource.AI,
            geometry={"source": "candidate_region", "candidate_id": candidate.candidate_id},
            label=candidate.risk_type,
            metrics={"score": candidate.score, "confidence": candidate.confidence},
            review_state=candidate.status,
            candidate_id=candidate.candidate_id,
        )

    def _review_summary(self, case: CaseRecord) -> dict[str, object]:
        accepted = sum(1 for roi in case.rois if roi.review_state == ReviewState.ACCEPTED)
        modified = sum(1 for roi in case.rois if roi.review_state == ReviewState.MODIFIED)
        rejected = sum(1 for roi in case.rois if roi.review_state == ReviewState.REJECTED)
        return {
            "accepted_regions": accepted,
            "modified_regions": modified,
            "rejected_regions": rejected,
            "total_review_events": len(case.review_events),
            "status": case.status,
        }
