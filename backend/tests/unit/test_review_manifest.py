from __future__ import annotations

from backend.src.domains.cases.enums import RegionSource, ReviewState
from backend.src.domains.cases.schemas import (
    AnalysisRun,
    CandidateRegion,
    CaseRecord,
    RegionOfInterest,
    ReviewEvent,
)
from backend.src.services.review_manifest import build_review_manifest


def test_review_manifest_keeps_training_feedback_fields() -> None:
    candidate = CandidateRegion(
        candidate_id="cand_001",
        run_id="run_video",
        score=0.72,
        confidence=0.81,
        risk_type="video_keyframe_model_segmentation",
        status=ReviewState.ACCEPTED,
        explanation="physician review required",
        metadata={
            "frame_index": 12,
            "timestamp_sec": 2.0,
            "bbox_xyxy": [20, 10, 80, 64],
            "bbox_normalized": {"type": "rect", "x": 0.1, "y": 0.1, "width": 0.3, "height": 0.4},
            "mask_path": "mask.png",
            "overlay_path": "overlay.png",
            "source_path": "frame.jpg",
        },
    )
    case = CaseRecord(
        case_id="case_review_manifest",
        title="review manifest",
        analysis_runs=[
            AnalysisRun(
                run_id="run_video",
                case_id="case_review_manifest",
                method_id="mp4_keyframe_segmentation",
                status="completed",
                candidate_regions=[candidate],
            )
        ],
        rois=[
            RegionOfInterest(
                roi_id="roi_cand_001",
                case_id="case_review_manifest",
                source=RegionSource.AI,
                candidate_id="cand_001",
                review_state=ReviewState.ACCEPTED,
                label="doctor_confirmed_roi",
                geometry={"type": "rect", "x": 0.1, "y": 0.1, "width": 0.3, "height": 0.4},
                metrics={"frame_index": 12, "timestamp_sec": 2.0},
            )
        ],
        review_events=[
            ReviewEvent(
                event_id="event_001",
                case_id="case_review_manifest",
                actor="doctor",
                action="accept_candidate_and_create_roi",
                target_id="cand_001",
                before_state="review_required",
                after_state="accepted",
            )
        ],
    )

    manifest, rows = build_review_manifest(case)

    assert manifest["summary"]["accepted_candidate_count"] == 1
    assert manifest["training_use"]["requires_physician_review"] is True
    assert [row["record_type"] for row in rows] == ["candidate_region", "roi", "review_event"]
    assert rows[0]["bbox_normalized"] == '{"type":"rect","x":0.1,"y":0.1,"width":0.3,"height":0.4}'
    assert rows[1]["geometry"] == '{"type":"rect","x":0.1,"y":0.1,"width":0.3,"height":0.4}'
