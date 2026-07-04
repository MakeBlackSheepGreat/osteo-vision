from __future__ import annotations

import csv
import zipfile
from pathlib import Path

import cv2
import numpy as np

from scripts.prepare_ofdvdnet_dataset import prepare_ofdvdnet_dataset


def test_prepare_ofdvdnet_dataset_writes_manifests_and_previews(tmp_path: Path) -> None:
    source_video = tmp_path / "OL-test-record.mp4"
    writer = cv2.VideoWriter(str(source_video), cv2.VideoWriter_fourcc(*"mp4v"), 15.0, (64, 48))
    for index in range(4):
        writer.write(np.full((48, 64, 3), index * 40, dtype=np.uint8))
    writer.release()
    zip_path = tmp_path / "data.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.write(source_video, source_video.name)
    source_manifest = tmp_path / "source_manifest.csv"
    _write_source_manifest(source_manifest)

    payload = prepare_ofdvdnet_dataset(
        zip_path=zip_path,
        extract_dir=tmp_path / "extracted",
        detailed_manifest_path=tmp_path / "ofdvdnet_manifest.csv",
        video_library_manifest_path=tmp_path / "video_library_manifest.csv",
        source_manifest_path=source_manifest,
        preview_dir=tmp_path / "previews",
        report_dir=tmp_path / "reports",
    )

    assert payload["video_count"] == 1
    with Path(payload["detailed_manifest_path"]).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["record_id"] == "OFDVDNET_001"
    assert rows[0]["fluorescence_xyxy"] == "32|0|64|24"
    assert Path(rows[0]["fluorescence_preview_path"]).exists()
    with Path(payload["video_library_manifest_path"]).open("r", encoding="utf-8", newline="") as handle:
        library_rows = list(csv.DictReader(handle))
    assert library_rows[-1]["record_id"] == "OFDVDNET_001"
    assert library_rows[-1]["download_status"] == "exists"


def _write_source_manifest(path: Path) -> None:
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
