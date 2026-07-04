from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

from backend.src.api.app import create_app
from backend.src.core.settings import load_settings
from backend.src.services.job_worker import LocalJobWorker


def test_case_input_and_analysis_contract(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    created = client.post("/cases", json={"title": "contract case"}).json()
    case_id = created["case_id"]
    white = Path("tests/fixtures/platform/white.png").resolve()
    fluorescence = Path("tests/fixtures/platform/fluorescence.png").resolve()

    response = client.post(
        f"/cases/{case_id}/inputs",
        json=[
            {"channel": "white_light", "path": str(white)},
            {"channel": "fluorescence", "path": str(fluorescence)},
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "loaded"
    assert len(payload["inputs"]) == 2

    loaded = client.get(f"/cases/{case_id}")
    assert loaded.status_code == 200
    assert loaded.json()["case_id"] == case_id

    analyzed = client.post(
        f"/cases/{case_id}/analysis-runs",
        json={"selected_input_ids": [], "parameters": {"threshold": 0.6, "colormap": "green"}, "roi_hints": []},
    )
    assert analyzed.status_code == 200
    analyzed_payload = analyzed.json()
    assert analyzed_payload["analysis_runs"]
    assert analyzed_payload["analysis_runs"][-1]["status"] == "completed"


def test_saved_roi_is_used_as_analysis_hint(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    case_id = client.post("/cases", json={"title": "roi constrained case"}).json()["case_id"]
    white = Path("tests/fixtures/platform/white.png").resolve()
    fluorescence = Path("tests/fixtures/platform/fluorescence.png").resolve()
    client.post(
        f"/cases/{case_id}/inputs",
        json=[
            {"channel": "white_light", "path": str(white)},
            {"channel": "fluorescence", "path": str(fluorescence)},
        ],
    )
    roi = {
        "review_state": "modified",
        "label": "manual_roi",
        "geometry": {"type": "rect", "coordinate_space": "normalized", "x": 0.15, "y": 0.15, "width": 0.7, "height": 0.7},
    }
    saved = client.patch(f"/cases/{case_id}/regions/manual_roi_1", json=roi)
    assert saved.status_code == 200

    analyzed = client.post(
        f"/cases/{case_id}/analysis-runs",
        json={"selected_input_ids": [], "parameters": {"threshold": 0.6, "colormap": "green"}, "roi_hints": []},
    )

    assert analyzed.status_code == 200
    latest = analyzed.json()["analysis_runs"][-1]
    assert latest["parameters"]["roi_hints"][0]["roi_id"] == "manual_roi_1"
    assert latest["quantitative_summary"]["roi_hint_count"] == 1
    assert latest["quantitative_summary"]["roi_quantification_count"] == 1
    assert latest["candidate_regions"][0]["explanation"].startswith("Derived from ROI-constrained")


def test_raw_upload_returns_backend_readable_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    source = Path("tests/fixtures/platform/white.png")

    response = client.post(
        "/uploads/raw",
        content=source.read_bytes(),
        headers={"content-type": "image/png", "x-filename": "white.png"},
    )

    assert response.status_code == 200
    payload = response.json()
    uploaded_path = Path(payload["path"])
    assert uploaded_path.exists()
    assert uploaded_path.read_bytes() == source.read_bytes()
    preview = client.get("/files/preview", params={"path": payload["path"]})
    assert preview.status_code == 200


def test_raw_upload_rejects_extension_content_mismatch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())

    response = client.post(
        "/uploads/raw",
        content=b"<html>captcha</html>",
        headers={"content-type": "image/jpeg", "x-filename": "captcha.jpg"},
    )

    assert response.status_code == 415
    assert "image content" in response.json()["detail"]


def test_raw_upload_rejects_corrupt_mp4_even_with_container_signature(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    corrupt_mp4_header = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"not-a-decodable-video"

    response = client.post(
        "/uploads/raw",
        content=corrupt_mp4_header,
        headers={"content-type": "video/mp4", "x-filename": "corrupt.mp4"},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "upload_content_unreadable"
    assert "video capture could not be opened" in detail["reason"]


def test_mp4_upload_returns_metadata_and_keyframes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    source = tmp_path / "official_sample.mp4"
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"mp4v"), 12.0, (96, 64))
    for index in range(8):
        writer.write(np.full((64, 96, 3), index * 20, dtype=np.uint8))
    writer.release()

    response = client.post(
        "/uploads/raw",
        content=source.read_bytes(),
        headers={"content-type": "video/mp4", "x-filename": "official_sample.mp4"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["input_type"] == "video_file"
    assert payload["metadata"]["width"] == 96
    assert payload["metadata"]["height"] == 64
    assert payload["metadata"]["upload_content_probe"]["mp4_ftyp_present"]
    assert payload["metadata"]["official_resolution_match"] is False
    assert payload["metadata"]["official_input_profile"]["target_resolution"] == [3840, 2160]
    assert payload["metadata"]["official_input_profile"]["resolution_match"] is False
    assert any(warning["code"] == "official_video_resolution_mismatch" for warning in payload["warnings"])
    assert payload["keyframe_job_id"]

    job_response = client.get(f"/uploads/jobs/{payload['keyframe_job_id']}")
    assert job_response.status_code == 200
    job = job_response.json()
    assert job["status"] == "completed"
    keyframes = job["result"]["keyframes"]
    assert len(keyframes) == 5
    assert Path(keyframes[0]["path"]).exists()
    preview = client.get("/files/preview", params={"path": keyframes[0]["path"]})
    assert preview.status_code == 200


def test_video_analysis_reuses_uploaded_keyframes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    source = tmp_path / "uploaded_reuse.mp4"
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (80, 60))
    for index in range(8):
        frame = np.full((60, 80, 3), 30 + index * 10, dtype=np.uint8)
        frame[22:38, 30:52, 1] = 255
        writer.write(frame)
    writer.release()
    uploaded = client.post(
        "/uploads/raw",
        content=source.read_bytes(),
        headers={"content-type": "video/mp4", "x-filename": "uploaded_reuse.mp4"},
    ).json()
    upload_job = client.get(f"/uploads/jobs/{uploaded['keyframe_job_id']}").json()
    assert upload_job["status"] == "completed"
    upload_manifest = Path(upload_job["result"]["keyframe_manifest_path"])
    assert upload_manifest.exists()
    upload_frame_index_manifest = Path(upload_job["result"]["frame_index_manifest_path"])
    assert upload_frame_index_manifest.exists()
    upload_timeline_manifest = Path(upload_job["result"]["timeline_manifest_path"])
    assert upload_timeline_manifest.exists()
    case_id = client.post("/cases", json={"title": "reuse uploaded keyframes"}).json()["case_id"]
    input_response = client.post(
        f"/cases/{case_id}/inputs",
        json=[{"channel": "video", "path": uploaded["path"], "mime_type": "video/mp4"}],
    )
    assert input_response.status_code == 200

    analyzed = client.post(
        f"/cases/{case_id}/analysis-runs",
        json={"selected_input_ids": [], "parameters": {"mode": "video_file", "keyframe_count": 3}, "roi_hints": []},
    )

    assert analyzed.status_code == 200
    latest = analyzed.json()["analysis_runs"][-1]
    assert latest["status"] == "completed"
    assert latest["fused_outputs"]["keyframe_report_source"] == "reused_upload_preextract"
    assert latest["fused_outputs"]["keyframe_manifest_path"] == str(upload_manifest)
    assert latest["fused_outputs"]["frame_index_manifest_path"] == str(upload_frame_index_manifest)
    assert latest["fused_outputs"]["timeline_manifest_path"] == str(upload_timeline_manifest)
    assert latest["fused_outputs"]["timeline_summary"]["timeline_manifest_path"] == str(upload_timeline_manifest)
    assert latest["fused_outputs"]["timeline_summary"]["candidate_frame_count"] >= 3
    assert Path(latest["fused_outputs"]["frame_details_manifest_path"]).exists()
    assert len(latest["fused_outputs"]["frame_details"]) == 3
    assert latest["quantitative_summary"]["keyframe_source"] == "reused_upload_preextract"
    assert latest["quantitative_summary"]["keyframes_extracted"] == 3
    assert "uploads" in latest["fused_outputs"]["keyframes"][0]["evidence_path"]
    assert latest["fused_outputs"]["quality_summary"]["reused_from_upload_preextract"] is True


def test_video_library_candidate_can_be_imported_as_case_input(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    source = tmp_path / "library_sample.mp4"
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (80, 60))
    for index in range(6):
        writer.write(np.full((60, 80, 3), 20 + index * 20, dtype=np.uint8))
    writer.release()
    manifest = tmp_path / "video_manifest.csv"
    _write_video_manifest(manifest, [{"record_id": "LIB001", "local_path": str(source), "download_status": "exists"}])
    monkeypatch.setenv("OSTEO_VIDEO_MANIFEST_PATH", str(manifest))
    client = TestClient(create_app())
    created = client.post("/cases", json={"title": "video library case"}).json()
    case_id = created["case_id"]

    listed = client.get("/video-library/candidates")
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["count"] == 1
    assert payload["items"][0]["record_id"] == "LIB001"
    preview = client.post("/video-library/candidates/LIB001/preview")
    assert preview.status_code == 200
    assert preview.json()["preview_path"]
    preview_file = client.get("/files/preview", params={"path": preview.json()["preview_path"]})
    assert preview_file.status_code == 200

    imported = client.post(f"/cases/{case_id}/video-library/LIB001/inputs")

    assert imported.status_code == 200
    case_payload = imported.json()
    video_input = case_payload["inputs"][-1]
    assert video_input["channel"] == "video"
    assert video_input["path"] == str(source)
    assert video_input["metadata"]["source"] == "public_video_library"
    assert video_input["metadata"]["input_type"] == "video_file"


def test_video_input_analysis_extracts_keyframes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    source = tmp_path / "video_case.mp4"
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (80, 60))
    for index in range(6):
        frame = np.full((60, 80, 3), 30 + index * 10, dtype=np.uint8)
        frame[20:38, 28:52, 1] = 255
        writer.write(frame)
    writer.release()

    created = client.post("/cases", json={"title": "video case"}).json()
    case_id = created["case_id"]
    input_response = client.post(
        f"/cases/{case_id}/inputs",
        json=[{"channel": "video", "path": str(source), "mime_type": "video/mp4"}],
    )
    assert input_response.status_code == 200
    video_asset = input_response.json()["inputs"][0]
    assert video_asset["metadata"]["input_type"] == "video_file"
    assert video_asset["metadata"]["official_input_profile"]["resolution_match"] is False
    assert any(flag["code"] == "official_profile_mismatch" for flag in video_asset["quality_flags"])

    analyzed = client.post(
        f"/cases/{case_id}/analysis-runs",
        json={"selected_input_ids": [], "parameters": {"mode": "video_file", "keyframe_count": 3}, "roi_hints": []},
    )
    assert analyzed.status_code == 200
    latest = analyzed.json()["analysis_runs"][-1]
    assert latest["status"] == "completed"
    assert latest["fused_outputs"]["mode"] == "video_file_keyframes"
    assert latest["quantitative_summary"]["keyframes_extracted"] == 3
    assert latest["quantitative_summary"]["hotspot_frame_count"] == 3
    assert latest["quantitative_summary"]["hotspot_candidate_count"] > 0
    assert latest["candidate_regions"]
    candidate = latest["candidate_regions"][0]
    assert candidate["metadata"]["bbox_xyxy"]
    assert candidate["metadata"]["bbox_normalized"]["type"] == "rect"
    assert latest["fused_outputs"]["hotspot_outputs"][0]["segmentation_mask"]["path"]
    assert latest["fused_outputs"]["keyframes"][0]["evidence_path"]
    assert Path(latest["fused_outputs"]["frame_index_manifest_path"]).exists()
    assert Path(latest["fused_outputs"]["timeline_manifest_path"]).exists()
    assert latest["fused_outputs"]["timeline_summary"]["selected_frame_count"] == 3
    assert Path(latest["fused_outputs"]["frame_details_manifest_path"]).exists()
    frame_details = latest["fused_outputs"]["frame_details"]
    assert len(frame_details) == 3
    assert frame_details[0]["frame_key"]
    assert frame_details[0]["overlay_path"]
    assert frame_details[0]["top_component_bbox_xyxy"]
    assert Path(latest["fused_outputs"]["keyframes"][0]["evidence_path"]).exists()
    assert Path(latest["fused_outputs"]["hotspot_outputs"][0]["segmentation_mask"]["path"]).exists()

    reviewed = client.patch(
        f"/cases/{case_id}/candidate-regions/{candidate['candidate_id']}",
        json={
            "review_state": "accepted",
            "geometry": {
                "type": "rect",
                "coordinate_space": "normalized",
                "x": 0.1,
                "y": 0.2,
                "width": 0.3,
                "height": 0.4,
            },
            "label": "edited_hotspot_bbox",
            "reviewer_notes": "accepted in contract test",
        },
    )

    assert reviewed.status_code == 200
    reviewed_payload = reviewed.json()
    reviewed_candidate = reviewed_payload["analysis_runs"][-1]["candidate_regions"][0]
    assert reviewed_candidate["status"] == "accepted"
    assert reviewed_candidate["metadata"]["reviewer_notes"] == "accepted in contract test"
    assert reviewed_candidate["metadata"]["review_label"] == "edited_hotspot_bbox"
    assert reviewed_candidate["metadata"]["bbox_normalized"]["x"] == 0.1
    assert reviewed_candidate["metadata"]["bbox_xyxy"] == [8, 12, 32, 36]
    assert reviewed_candidate["metadata"]["geometry_review_source"] == "physician_review"
    assert reviewed_payload["review_events"][-1]["action"] == "candidate_region_state_update"
    assert reviewed_payload["review_summary"]["accepted_candidates"] == 1

    promoted = client.post(f"/cases/{case_id}/regions/from-candidate/{candidate['candidate_id']}")

    assert promoted.status_code == 200
    roi = promoted.json()["rois"][-1]
    assert roi["candidate_id"] == candidate["candidate_id"]
    assert roi["source"] == "ai"
    assert roi["review_state"] == "accepted"
    assert roi["geometry"]["type"] == "rect"
    assert roi["geometry"]["x"] == 0.1
    assert roi["metrics"]["frame_index"] == candidate["metadata"]["frame_index"]


def test_video_analysis_uses_requested_timestamps(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    source = tmp_path / "manual_timestamps.mp4"
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (80, 60))
    for index in range(6):
        frame = np.full((60, 80, 3), 30 + index * 10, dtype=np.uint8)
        if index in {1, 3, 5}:
            frame[20:38, 28:52, 1] = 255
        writer.write(frame)
    writer.release()
    case_id = client.post("/cases", json={"title": "manual timestamp case"}).json()["case_id"]
    client.post(
        f"/cases/{case_id}/inputs",
        json=[{"channel": "video", "path": str(source), "mime_type": "video/mp4"}],
    )

    analyzed = client.post(
        f"/cases/{case_id}/analysis-runs",
        json={
            "selected_input_ids": [],
            "parameters": {
                "mode": "video_file",
                "keyframe_count": 3,
                "keyframe_timestamps_sec": [0.1, 0.3, 99.0],
            },
            "roi_hints": [],
        },
    )

    assert analyzed.status_code == 200
    latest = analyzed.json()["analysis_runs"][-1]
    assert [frame["frame_index"] for frame in latest["fused_outputs"]["keyframes"]] == [1, 3, 5]
    assert [detail["frame_index"] for detail in latest["fused_outputs"]["frame_details"]] == [1, 3, 5]
    manifest = json.loads(Path(latest["fused_outputs"]["frame_index_manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["sampling_strategy"] == "manual"
    assert manifest["selection_trace"]["manual_selection_applied"] is True
    assert manifest["selection_trace"]["requested_timestamps_sec"] == [0.1, 0.3, 99.0]


def _write_video_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "record_id",
        "group",
        "title",
        "source_page_original_link",
        "direct_download_link",
        "local_path",
        "fluorescence",
        "medical_scene",
        "usable_for_training",
        "notes",
        "download_status",
        "error_or_note",
        "size_bytes",
        "sha256",
        "downloaded_at_utc",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_analysis_rejects_unknown_selected_input_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    created = client.post("/cases", json={"title": "selected input"}).json()
    case_id = created["case_id"]
    white = Path("tests/fixtures/platform/white.png").resolve()
    client.post(f"/cases/{case_id}/inputs", json=[{"channel": "white_light", "path": str(white)}])

    analyzed = client.post(
        f"/cases/{case_id}/analysis-runs",
        json={"selected_input_ids": ["input_missing"], "parameters": {}, "roi_hints": []},
    )

    assert analyzed.status_code == 200
    latest = analyzed.json()["analysis_runs"][-1]
    assert latest["status"] == "failed"
    assert latest["warnings"][0]["code"] == "selected_input_not_found"


def test_video_analysis_job_extracts_keyframes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    source = tmp_path / "video_job_case.mp4"
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (80, 60))
    for index in range(6):
        writer.write(np.full((60, 80, 3), 30 + index * 10, dtype=np.uint8))
    writer.release()

    created = client.post("/cases", json={"title": "video job case"}).json()
    case_id = created["case_id"]
    input_response = client.post(
        f"/cases/{case_id}/inputs",
        json=[{"channel": "video", "path": str(source), "mime_type": "video/mp4"}],
    )
    assert input_response.status_code == 200

    started = client.post(
        f"/cases/{case_id}/analysis-jobs",
        json={"selected_input_ids": [], "parameters": {"mode": "video_file", "keyframe_count": 3}, "roi_hints": []},
    )
    assert started.status_code == 200
    job_id = started.json()["job_id"]
    job = client.get(f"/analysis-jobs/{job_id}")
    assert job.status_code == 200
    assert job.json()["status"] == "completed"
    assert job.json()["progress"]["percent"] == 100
    canceled = client.post(f"/analysis-jobs/{job_id}/cancel")
    assert canceled.status_code == 200
    assert canceled.json()["status"] == "completed"

    loaded = client.get(f"/cases/{case_id}").json()
    latest = loaded["analysis_runs"][-1]
    assert latest["status"] == "completed"
    assert latest["quantitative_summary"]["keyframes_extracted"] == 3


def test_analysis_job_worker_mode_waits_for_local_worker(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    monkeypatch.setenv("OSTEO_JOB_EXECUTION_MODE", "worker")
    client = TestClient(create_app())
    created = client.post("/cases", json={"title": "worker mode case"}).json()
    case_id = created["case_id"]
    white = Path("tests/fixtures/platform/white.png").resolve()
    fluorescence = Path("tests/fixtures/platform/fluorescence.png").resolve()
    client.post(
        f"/cases/{case_id}/inputs",
        json=[
            {"channel": "white_light", "path": str(white)},
            {"channel": "fluorescence", "path": str(fluorescence)},
        ],
    )

    started = client.post(
        f"/cases/{case_id}/analysis-jobs",
        json={"selected_input_ids": [], "parameters": {"threshold": 0.6}, "roi_hints": []},
    )

    assert started.status_code == 200
    job_id = started.json()["job_id"]
    assert client.get(f"/analysis-jobs/{job_id}").json()["status"] == "queued"

    worker_result = LocalJobWorker(load_settings()).run_once(limit=1)

    assert worker_result["processed_count"] == 1
    job = client.get(f"/analysis-jobs/{job_id}").json()
    loaded = client.get(f"/cases/{case_id}").json()
    assert job["status"] == "completed"
    assert loaded["analysis_runs"][-1]["status"] == "completed"


def test_analysis_job_capacity_limit_returns_429(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    monkeypatch.setenv("OSTEO_MAX_ACTIVE_CASE_ANALYSIS_JOBS", "0")
    client = TestClient(create_app())
    created = client.post("/cases", json={"title": "capacity case"}).json()
    case_id = created["case_id"]

    started = client.post(
        f"/cases/{case_id}/analysis-jobs",
        json={"selected_input_ids": [], "parameters": {"mode": "video_file"}, "roi_hints": []},
    )

    assert started.status_code == 429
    assert started.json()["detail"]["code"] == "case_analysis_job_capacity_exceeded"


def test_upload_keyframe_job_capacity_limit_returns_429(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    monkeypatch.setenv("OSTEO_MAX_ACTIVE_UPLOAD_KEYFRAME_JOBS", "0")
    client = TestClient(create_app())
    source = tmp_path / "queued_upload.mp4"
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (80, 60))
    for index in range(3):
        writer.write(np.full((60, 80, 3), 50 + index * 20, dtype=np.uint8))
    writer.release()

    response = client.post(
        "/uploads/raw",
        content=source.read_bytes(),
        headers={"content-type": "video/mp4", "x-filename": "queued_upload.mp4"},
    )

    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "upload_keyframe_job_capacity_exceeded"
