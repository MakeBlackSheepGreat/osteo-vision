from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

from backend.src.api.app import create_app


def test_review_api_records_region_and_event(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    case_id = client.post("/cases", json={"title": "review"}).json()["case_id"]

    region = client.patch(f"/cases/{case_id}/regions/roi_1", json={"review_state": "accepted", "geometry": {"type": "box"}})
    assert region.status_code == 200
    assert region.json()["rois"][0]["review_state"] == "accepted"

    event = client.post(
        f"/cases/{case_id}/review-events",
        json={"action": "accept", "target_id": "roi_1", "after_state": "accepted"},
    )
    assert event.status_code == 200
    assert event.json()["review_events"][0]["target_id"] == "roi_1"


def test_review_api_generates_prompt_assisted_bone_gate_mask(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    source = tmp_path / "bone_gate_video.mp4"
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"mp4v"), 8.0, (80, 60))
    for index in range(5):
        frame = np.full((60, 80, 3), 30 + index * 10, dtype=np.uint8)
        frame[18:42, 25:55, 1] = 255
        writer.write(frame)
    writer.release()
    case_id = client.post("/cases", json={"title": "bone gate"}).json()["case_id"]
    client.post(f"/cases/{case_id}/inputs", json=[{"channel": "video", "path": str(source), "mime_type": "video/mp4"}])
    analyzed = client.post(
        f"/cases/{case_id}/analysis-runs",
        json={"selected_input_ids": [], "parameters": {"mode": "video_file", "keyframe_count": 2}, "roi_hints": []},
    )
    assert analyzed.status_code == 200
    candidate = analyzed.json()["analysis_runs"][-1]["candidate_regions"][0]

    response = client.post(
        f"/cases/{case_id}/candidate-regions/{candidate['candidate_id']}/bone-gate-mask",
        json={"geometry": candidate["metadata"]["bbox_normalized"], "review_state": "review_required"},
    )

    assert response.status_code == 200
    payload = response.json()
    updated_candidate = payload["analysis_runs"][-1]["candidate_regions"][0]
    metadata = updated_candidate["metadata"]
    assert metadata["mask_type"] == "exposed_bone"
    assert metadata["label_source"] == "prompt_assisted_review"
    assert metadata["prompt_contract_fallback"] is True
    assert Path(metadata["bone_gate_mask_path"]).exists()
    assert Path(metadata["bone_gate_overlay_path"]).exists()
    assert metadata["video_signal_segmentation"]["bone_gate_mask"]["available"] is True
    assert metadata["video_signal_segmentation"]["bone_gate_mask"]["status"] == "prompt_assisted_review"
    assert payload["analysis_runs"][-1]["fused_outputs"]["video_segmentation_summary"]["bone_gate_frame_count"] == 1
    assert payload["review_events"][-1]["action"] == "bone_gate_mask_generated"

    repeated = client.post(
        f"/cases/{case_id}/candidate-regions/{candidate['candidate_id']}/bone-gate-mask",
        json={"geometry": candidate["metadata"]["bbox_normalized"], "review_state": "review_required"},
    )

    assert repeated.status_code == 200
    assert repeated.json()["analysis_runs"][-1]["fused_outputs"]["video_segmentation_summary"]["bone_gate_frame_count"] == 1
