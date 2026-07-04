from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
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
        geometry = _candidate_geometry(candidate)
        return RegionOfInterest(
            roi_id=f"roi_{candidate.candidate_id}",
            case_id=case.case_id,
            source=RegionSource.AI,
            geometry=geometry,
            label=candidate.risk_type,
            metrics={
                "score": candidate.score,
                "confidence": candidate.confidence,
                "frame_index": candidate.metadata.get("frame_index"),
                "timestamp_sec": candidate.metadata.get("timestamp_sec"),
                "positive_area_fraction": candidate.metadata.get("positive_area_fraction"),
            },
            review_state=candidate.status,
            candidate_id=candidate.candidate_id,
        )

    def add_candidate_roi(self, case: CaseRecord, candidate_id: str) -> CaseRecord:
        candidate = _find_candidate(case, candidate_id)
        if candidate is None:
            raise ValueError(f"Candidate not found: {candidate_id}")
        roi = self.candidate_to_roi(case, candidate)
        rois = [existing for existing in case.rois if existing.roi_id != roi.roi_id]
        updated = case.model_copy(update={"rois": [*rois, roi], "status": CaseStatus.REVIEWING})
        updated = updated.model_copy(update={"review_summary": self._review_summary(updated)})
        self.repo.save(updated)
        return updated

    def update_candidate_region(self, case: CaseRecord, candidate_id: str, request: RegionUpdateRequest) -> CaseRecord:
        runs = []
        found = False
        before_state: str | None = None
        for run in case.analysis_runs:
            candidates = []
            for candidate in run.candidate_regions:
                if candidate.candidate_id != candidate_id:
                    candidates.append(candidate)
                    continue
                found = True
                before_state = candidate.status.value
                metadata = dict(candidate.metadata)
                if request.reviewer_notes:
                    metadata["reviewer_notes"] = request.reviewer_notes
                if request.label is not None:
                    metadata["review_label"] = request.label
                if request.geometry is not None:
                    geometry = _normalized_rect_geometry(request.geometry)
                    metadata["bbox_normalized"] = geometry
                    metadata["review_geometry"] = geometry
                    metadata["geometry_reviewed_at"] = datetime.now(timezone.utc).isoformat()
                    metadata["geometry_review_source"] = "physician_review"
                    bbox_xyxy = _bbox_xyxy_from_geometry(
                        geometry,
                        image_width=metadata.get("image_width"),
                        image_height=metadata.get("image_height"),
                    )
                    if bbox_xyxy is not None:
                        metadata["bbox_xyxy"] = bbox_xyxy
                candidates.append(candidate.model_copy(update={"status": request.review_state, "metadata": metadata}))
            runs.append(run.model_copy(update={"candidate_regions": candidates}))
        if not found:
            raise ValueError(f"Candidate not found: {candidate_id}")
        event = ReviewEvent(
            event_id=f"event_{uuid4().hex[:10]}",
            case_id=case.case_id,
            actor="physician",
            action="candidate_region_state_update",
            target_id=candidate_id,
            before_state=before_state,
            after_state=request.review_state.value,
            timestamp=datetime.now(timezone.utc),
            notes=request.reviewer_notes,
        )
        updated = case.model_copy(
            update={
                "analysis_runs": runs,
                "review_events": [*case.review_events, event],
                "status": CaseStatus.REVIEWING,
            }
        )
        updated = updated.model_copy(update={"review_summary": self._review_summary(updated)})
        self.repo.save(updated)
        return updated

    def _review_summary(self, case: CaseRecord) -> dict[str, object]:
        accepted = sum(1 for roi in case.rois if roi.review_state == ReviewState.ACCEPTED)
        modified = sum(1 for roi in case.rois if roi.review_state == ReviewState.MODIFIED)
        rejected = sum(1 for roi in case.rois if roi.review_state == ReviewState.REJECTED)
        candidates = [candidate for run in case.analysis_runs for candidate in run.candidate_regions]
        candidate_accepted = sum(1 for candidate in candidates if candidate.status == ReviewState.ACCEPTED)
        candidate_modified = sum(1 for candidate in candidates if candidate.status == ReviewState.MODIFIED)
        candidate_rejected = sum(1 for candidate in candidates if candidate.status == ReviewState.REJECTED)
        return {
            "accepted_regions": accepted,
            "modified_regions": modified,
            "rejected_regions": rejected,
            "accepted_candidates": candidate_accepted,
            "modified_candidates": candidate_modified,
            "rejected_candidates": candidate_rejected,
            "total_review_events": len(case.review_events),
            "status": case.status,
        }


def _find_candidate(case: CaseRecord, candidate_id: str) -> CandidateRegion | None:
    for run in reversed(case.analysis_runs):
        for candidate in run.candidate_regions:
            if candidate.candidate_id == candidate_id:
                return candidate
    return None


def _candidate_geometry(candidate: CandidateRegion) -> dict[str, Any]:
    geometry = candidate.metadata.get("bbox_normalized")
    if isinstance(geometry, dict) and geometry.get("type") == "rect":
        return {
            **geometry,
            "source": "candidate_region",
            "candidate_id": candidate.candidate_id,
        }
    return {"source": "candidate_region", "candidate_id": candidate.candidate_id}


def _normalized_rect_geometry(geometry: dict[str, Any]) -> dict[str, Any]:
    if geometry.get("type") != "rect":
        return dict(geometry)
    x = _clamp_unit(geometry.get("x"))
    y = _clamp_unit(geometry.get("y"))
    width = min(_clamp_unit(geometry.get("width")), max(0.0, 1.0 - x))
    height = min(_clamp_unit(geometry.get("height")), max(0.0, 1.0 - y))
    return {
        **geometry,
        "type": "rect",
        "coordinate_space": "normalized",
        "x": round(x, 6),
        "y": round(y, 6),
        "width": round(width, 6),
        "height": round(height, 6),
    }


def _bbox_xyxy_from_geometry(
    geometry: dict[str, Any],
    *,
    image_width: Any,
    image_height: Any,
) -> list[int] | None:
    if geometry.get("type") != "rect":
        return None
    width = _positive_int(image_width)
    height = _positive_int(image_height)
    if width is None or height is None:
        return None
    x = _clamp_unit(geometry.get("x"))
    y = _clamp_unit(geometry.get("y"))
    rect_width = _clamp_unit(geometry.get("width"))
    rect_height = _clamp_unit(geometry.get("height"))
    x0 = int(round(x * width))
    y0 = int(round(y * height))
    x1 = int(round(min(1.0, x + rect_width) * width))
    y1 = int(round(min(1.0, y + rect_height) * height))
    if x1 <= x0 or y1 <= y0:
        return None
    return [x0, y0, x1, y1]


def _clamp_unit(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, parsed))


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None
