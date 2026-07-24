from __future__ import annotations

import csv
from pathlib import Path

import cv2
import numpy as np

from backend.osteo_vision_api.services.video_library_service import VideoLibraryService


def test_video_library_filters_existing_mp4_candidates(tmp_path: Path) -> None:
    mp4 = tmp_path / "sample.mp4"
    mp4.write_bytes(b"not a real video but present for manifest filtering")
    flv = tmp_path / "sample.flv"
    flv.write_bytes(b"flv")
    manifest = tmp_path / "videos.csv"
    _write_manifest(
        manifest,
        [
            {"record_id": "v1", "local_path": str(mp4), "download_status": "exists", "fluorescence": "no"},
            {"record_id": "v2", "local_path": str(flv), "download_status": "exists", "fluorescence": "no"},
            {"record_id": "v3", "local_path": str(tmp_path / "missing.mp4"), "download_status": "not_downloaded"},
        ],
    )

    payload = VideoLibraryService(manifest).list_candidates()

    assert payload["count"] == 1
    assert payload["items"][0]["record_id"] == "v1"
    assert payload["items"][0]["system_readable"] is True


def test_video_library_can_return_unaccepted_candidates(tmp_path: Path) -> None:
    manifest = tmp_path / "videos.csv"
    _write_manifest(
        manifest,
        [{"record_id": "v1", "local_path": str(tmp_path / "missing.mp4"), "download_status": "not_downloaded"}],
    )

    payload = VideoLibraryService(manifest).list_candidates(accepted_only=False)

    assert payload["count"] == 1
    assert payload["items"][0]["system_readable"] is False


def test_video_library_generates_candidate_preview(tmp_path: Path) -> None:
    video = tmp_path / "preview.mp4"
    _write_mp4(video)
    manifest = tmp_path / "videos.csv"
    _write_manifest(
        manifest,
        [{"record_id": "v_preview", "local_path": str(video), "download_status": "exists", "fluorescence": "yes"}],
    )

    service = VideoLibraryService(manifest, preview_root=tmp_path / "previews")
    payload = service.ensure_preview("v_preview")
    listed_again = service.list_candidates()

    assert payload["preview_status"] == "generated"
    assert Path(payload["preview_path"]).exists()
    assert payload["width"] == 80
    assert payload["height"] == 60
    assert listed_again["items"][0]["preview_status"] == "cached"


def _write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
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


def _write_mp4(path: Path) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (80, 60))
    for index in range(5):
        frame = np.full((60, 80, 3), index * 30, dtype=np.uint8)
        frame[18:42, 28:52, 1] = 220
        writer.write(frame)
    writer.release()
