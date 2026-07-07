from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
from PIL import Image

from tools.build_bone_gate_review_seed_batch import build_bone_gate_seed_batch


def test_build_bone_gate_seed_batch_writes_prompt_assisted_review_rows(tmp_path: Path) -> None:
    keyframe = tmp_path / "frame.jpg"
    signal_mask = tmp_path / "signal.png"
    Image.fromarray(np.full((24, 32, 3), 80, dtype=np.uint8)).save(keyframe)
    mask = np.zeros((24, 32), dtype=np.uint8)
    mask[6:18, 8:26] = 255
    Image.fromarray(mask).save(signal_mask)
    manifest = tmp_path / "video_signal_manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "case_id",
                "source_video_path",
                "source_page_original_link",
                "frame_index",
                "timestamp_sec",
                "keyframe_path",
                "fluorescence_signal_mask_path",
                "quality_status",
                "positive_area_fraction",
                "input_domain",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "case_id": "case_seed_001",
                "source_video_path": "video.mp4",
                "source_page_original_link": "https://example.org/video",
                "frame_index": "10",
                "timestamp_sec": "1.25",
                "keyframe_path": str(keyframe),
                "fluorescence_signal_mask_path": str(signal_mask),
                "quality_status": "accepted",
                "positive_area_fraction": "0.20",
                "input_domain": "proxy",
            }
        )

    summary = build_bone_gate_seed_batch(
        argparse.Namespace(
            video_signal_manifest=str(manifest),
            output_dir=str(tmp_path / "out"),
            limit=5,
            max_per_video=3,
            min_positive_area=0.005,
            bbox_padding=0.05,
        )
    )

    assert summary["sample_count"] == 1
    rows = list(csv.DictReader(Path(summary["csv_manifest_path"]).open("r", encoding="utf-8")))
    assert rows[0]["mask_type"] == "exposed_bone"
    assert rows[0]["label_source"] == "prompt_assisted_review"
    assert rows[0]["review_state"] == "review_required"
    assert Path(rows[0]["bone_gate_mask_path"]).exists()
    assert Path(rows[0]["bone_gate_overlay_path"]).exists()
