from __future__ import annotations

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
