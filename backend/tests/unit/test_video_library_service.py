from __future__ import annotations

import csv
from pathlib import Path
from typing import Any
from unittest.mock import patch

import cv2
import numpy as np
import pytest

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


def test_video_library_merges_ofdvdnet_layout_metadata(tmp_path: Path) -> None:
    source = tmp_path / "ofdvd.mp4"
    source.write_bytes(b"placeholder")
    manifest = tmp_path / "video-library.csv"
    _write_manifest(
        manifest,
        [
            {
                "record_id": "OFDVDNET_001",
                "local_path": str(source),
                "download_status": "exists",
                "source_page_original_link": "https://example.test/ofdvdnet",
            }
        ],
    )
    ofdvd_manifest = tmp_path / "ofdvdnet.csv"
    ofdvd_manifest.write_text(
        "record_id,dataset_id,video_path,original_filename,view_layout,overlay_xyxy,"
        "fluorescence_xyxy,reference_xyxy,readable,domain_boundary\n"
        f"OFDVDNET_001,D046,{source},sample.mp4,three_views,0|0|32|24,32|0|64|24,"
        "0|24|32|48,True,public proxy\n",
        encoding="utf-8",
    )

    service = VideoLibraryService(manifest, ofdvd_manifest_path=ofdvd_manifest)
    candidate = service.get_candidate("OFDVDNET_001")

    assert candidate is not None
    assert candidate["composite_layout_available"] is True
    assert candidate["crop_regions"]["white_light"] == [0, 24, 32, 48]
    assert candidate["crop_regions"]["fluorescence"] == [32, 0, 64, 24]
    assert candidate["source_page_original_link"] == "https://example.test/ofdvdnet"


def test_video_library_reuses_manifest_cache_and_invalidates_on_change(tmp_path: Path) -> None:
    first_video = tmp_path / "first.mp4"
    first_video.write_bytes(b"first")
    second_video = tmp_path / "second.mp4"
    second_video.write_bytes(b"second")
    manifest = tmp_path / "videos.csv"
    _write_manifest(
        manifest,
        [{"record_id": "v1", "local_path": str(first_video), "download_status": "exists"}],
    )

    service = VideoLibraryService(manifest)
    with patch.object(service, "_read_manifest", wraps=service._read_manifest) as read_manifest:
        listed = service.list_candidates(accepted_only=False)
        candidate = service.get_candidate("v1")
        assert listed["count"] == 1
        assert candidate is not None
        assert read_manifest.call_count == 2

        _write_manifest(
            manifest,
            [
                {"record_id": "v1", "local_path": str(first_video), "download_status": "exists"},
                {"record_id": "v2", "local_path": str(second_video), "download_status": "exists"},
            ],
        )
        updated = service.get_candidate("v2")
        assert updated is not None
        assert updated["local_path"] == str(second_video)
        assert read_manifest.call_count == 4


def test_video_library_stops_payload_work_at_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = tmp_path / "videos.csv"
    rows = []
    for index in range(5):
        video = tmp_path / f"video_{index}.mp4"
        video.write_bytes(b"video")
        rows.append({"record_id": f"v{index}", "local_path": str(video), "download_status": "exists"})
    _write_manifest(manifest, rows)
    service = VideoLibraryService(manifest)
    original = service._candidate_payload
    calls = 0

    def counted(row: dict[str, str]) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return original(row)

    monkeypatch.setattr(service, "_candidate_payload", counted)
    payload = service.list_candidates(accepted_only=False, limit=2)

    assert payload["count"] == 2
    assert calls == 2


def test_video_library_degrades_for_invalid_manifest_and_preview_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = tmp_path / "videos.csv"
    manifest.write_bytes(b"record_id,local_path\n\xff\n")
    service = VideoLibraryService(manifest)
    payload = service.list_candidates(accepted_only=False)
    assert payload["exists"] is True
    assert payload["count"] == 0

    video = tmp_path / "preview.mp4"
    _write_mp4(video)
    _write_manifest(
        manifest,
        [{"record_id": "preview", "local_path": str(video), "download_status": "exists"}],
    )
    service = VideoLibraryService(manifest, preview_root=tmp_path / "previews")
    monkeypatch.setattr(cv2, "imwrite", lambda *args, **kwargs: False)
    failed = service.ensure_preview("preview")
    assert failed["preview_status"] == "failed"
    assert "could not be written" in failed["preview_error"]


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
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (80, 60))  # type: ignore[attr-defined]
    for index in range(5):
        frame = np.full((60, 80, 3), index * 30, dtype=np.uint8)
        frame[18:42, 28:52, 1] = 220
        writer.write(frame)
    writer.release()
