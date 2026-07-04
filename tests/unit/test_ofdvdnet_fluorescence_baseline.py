from __future__ import annotations

import csv
from pathlib import Path

import cv2
import numpy as np

from scripts.run_ofdvdnet_fluorescence_baseline import run_ofdvdnet_fluorescence_baseline
from src.datasets.ofdvdnet import read_ofdvdnet_manifest, read_ofdvdnet_sample


def test_ofdvdnet_manifest_reader_and_baseline_outputs(tmp_path: Path) -> None:
    video_path = tmp_path / "ofdvdnet_sample.mp4"
    _write_synthetic_ofdvdnet_video(video_path)
    manifest_path = tmp_path / "ofdvdnet_manifest.csv"
    _write_ofdvdnet_manifest(manifest_path, video_path)

    records = read_ofdvdnet_manifest(manifest_path)
    assert len(records) == 1
    sample = read_ofdvdnet_sample(records[0], relative_position=0.5)
    assert sample["views"]["fluorescence"].shape == (24, 32, 3)
    assert sample["views"]["reference"].shape == (24, 32, 3)

    payload = run_ofdvdnet_fluorescence_baseline(
        manifest_path=manifest_path,
        output_dir=tmp_path / "baseline",
        baseline_manifest_path=tmp_path / "baseline_manifest.csv",
        report_dir=tmp_path / "reports",
    )

    assert payload["processed_record_count"] == 1
    with Path(payload["baseline_manifest_path"]).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["record_id"] == "OFDVDNET_TEST_001"
    assert Path(rows[0]["fluorescence_enhanced_path"]).exists()
    assert Path(rows[0]["pseudo_color_path"]).exists()
    assert Path(rows[0]["fusion_overlay_path"]).exists()
    assert 0.0 <= float(rows[0]["positive_area_fraction"]) <= 1.0
    assert Path(payload["report_paths"]["zh_report"]).exists()


def _write_synthetic_ofdvdnet_video(path: Path) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 15.0, (64, 48))
    for index in range(5):
        frame = np.zeros((48, 64, 3), dtype=np.uint8)
        frame[:24, :32] = (20, 80 + index * 20, 120)
        gradient = np.linspace(0, 255, 32, dtype=np.uint8)
        frame[:24, 32:, 1] = gradient[None, :]
        frame[24:, :32] = (140, 100, 60)
        writer.write(frame)
    writer.release()


def _write_ofdvdnet_manifest(path: Path, video_path: Path) -> None:
    fields = [
        "record_id",
        "dataset_id",
        "video_path",
        "source_zip",
        "original_filename",
        "split",
        "width",
        "height",
        "fps",
        "frame_count",
        "duration_sec",
        "view_layout",
        "overlay_xyxy",
        "fluorescence_xyxy",
        "reference_xyxy",
        "full_preview_path",
        "overlay_preview_path",
        "fluorescence_preview_path",
        "reference_preview_path",
        "source_page_original_link",
        "domain_boundary",
        "readable",
        "probe_error",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
                "record_id": "OFDVDNET_TEST_001",
                "dataset_id": "D046_OFDVDNET",
                "video_path": str(video_path),
                "split": "train",
                "width": 64,
                "height": 48,
                "fps": 15.0,
                "frame_count": 5,
                "duration_sec": 0.333333,
                "view_layout": "top_left_overlay__top_right_fluorescence__bottom_left_reference",
                "overlay_xyxy": "0|0|32|24",
                "fluorescence_xyxy": "32|0|64|24",
                "reference_xyxy": "0|24|32|48",
                "source_page_original_link": "https://datadryad.org/dataset/doi:10.5061/dryad.v6wwpzh3w",
                "domain_boundary": "proxy data",
                "readable": "True",
            }
        )
