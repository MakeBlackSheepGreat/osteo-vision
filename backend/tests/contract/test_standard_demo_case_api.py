from __future__ import annotations

import csv

import cv2
import numpy as np
from fastapi.testclient import TestClient

from backend.osteo_vision_api.api.app import create_app


def test_standard_demo_case_is_reused_and_keeps_safe_fallback_when_local_assets_are_missing(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.sqlite"))
    monkeypatch.setenv("OSTEO_VIDEO_MANIFEST_PATH", str(tmp_path / "missing-video-library.csv"))
    monkeypatch.setenv("OSTEO_OFDVD_MANIFEST_PATH", str(tmp_path / "missing-ofdvdnet.csv"))
    client = TestClient(create_app())

    created = client.post("/platform/standard-demo-case")
    repeated = client.post("/platform/standard-demo-case")

    assert created.status_code == 200
    assert repeated.status_code == 200
    payload = created.json()
    assert payload["case_id"] == "case_standard_demo"
    assert repeated.json()["version"] == payload["version"]
    assert payload["inputs"] == []
    assert payload["three_d_evidence"]["navigation_level"] == "L0"
    assert payload["three_d_evidence"]["navigation_ready"] is False
    assert payload["three_d_evidence"]["display_orientation_status"] == (
        "axis_mapping_inferred_not_physician_reviewed"
    )
    assert payload["three_d_evidence"]["view_space_mapping"]["display_up_axis"] == "-physical_z"
    assert payload["three_d_evidence"]["view_space_mapping"]["frontend_rotation_x_degrees"] == 90
    assert payload["three_d_evidence"]["view_space_mapping"]["frontend_rotation_z_degrees"] == 180
    assert payload["three_d_evidence"]["view_space_mapping"]["frontend_rotation_order"] == "ZXY"
    assert any(item["code"] == "standard_demo_video_unavailable" for item in payload["warnings"])


def test_standard_demo_case_uses_the_selected_readable_public_video_proxy(tmp_path, monkeypatch) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    source = artifact_root / "standard-demo.mp4"
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"mp4v"), 8.0, (64, 48))
    writer.write(np.full((48, 64, 3), 96, dtype=np.uint8))
    writer.release()
    manifest = tmp_path / "video-library.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "record_id",
                "local_path",
                "download_status",
                "source_page_original_link",
                "direct_download_link",
                "fluorescence",
                "medical_scene",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "record_id": "PMC10807896_S004",
                "local_path": str(source),
                "download_status": "exists",
                "source_page_original_link": "https://example.test/source",
                "direct_download_link": "https://example.test/video.mp4",
                "fluorescence": "no",
                "medical_scene": "public osteomyelitis surgery proxy",
            }
        )
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.sqlite"))
    monkeypatch.setenv("OSTEO_VIDEO_MANIFEST_PATH", str(manifest))
    monkeypatch.setenv("OSTEO_OFDVD_MANIFEST_PATH", str(tmp_path / "missing-ofdvdnet.csv"))
    client = TestClient(create_app())

    response = client.post("/platform/standard-demo-case")

    assert response.status_code == 200
    inputs = response.json()["inputs"]
    assert len(inputs) == 1
    assert inputs[0]["channel"] == "video"
    assert inputs[0]["metadata"]["record_id"] == "PMC10807896_S004"
    assert inputs[0]["metadata"]["standard_demo"] is True
