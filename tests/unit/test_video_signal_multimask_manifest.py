from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image

from tools.build_video_signal_multimask_training_manifest import build_multimask_manifest


def test_build_video_signal_multimask_manifest_merges_proxy_and_review_rows(tmp_path: Path) -> None:
    image_path = tmp_path / "frame.jpg"
    signal_mask = tmp_path / "signal.png"
    bone_mask = tmp_path / "bone.png"
    for path in (image_path, signal_mask, bone_mask):
        Image.fromarray(np.full((12, 16), 255, dtype=np.uint8)).save(path)
    video_manifest = tmp_path / "video_signal.csv"
    with video_manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "case_id",
                "keyframe_path",
                "fluorescence_signal_mask_path",
                "source_video_path",
                "frame_index",
                "timestamp_sec",
                "review_state",
                "sample_weight",
                "label_source",
                "quality_status",
                "input_domain",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "case_id": "case_proxy",
                "keyframe_path": str(image_path),
                "fluorescence_signal_mask_path": str(signal_mask),
                "source_video_path": "source.mp4",
                "frame_index": 2,
                "timestamp_sec": 0.5,
                "review_state": "review_required",
                "sample_weight": 1.0,
                "label_source": "fluorescence_intensity_proxy_mask",
                "quality_status": "accepted",
                "input_domain": "proxy",
            }
        )
    review_manifest = tmp_path / "review_manifest.json"
    review_manifest.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "case_id": "case_review",
                        "candidate_id": "cand_1",
                        "review_state": "accepted",
                        "source_path": str(image_path),
                        "mask_type": "exposed_bone",
                        "bone_gate_mask_path": str(bone_mask),
                        "label_source": "prompt_assisted_review",
                        "sample_weight": 4.0,
                    }
                ],
                "rois": [],
            }
        ),
        encoding="utf-8",
    )

    summary = build_multimask_manifest(
        argparse.Namespace(
            video_signal_manifest=str(video_manifest),
            review_manifest=[str(review_manifest)],
            output_dir=str(tmp_path / "out"),
            manifest_name="multi.csv",
            include_mask_types="fluorescence_hotspot,exposed_bone",
            val_fraction=0.2,
            seed=20260707,
        )
    )

    assert summary["sample_count"] == 2
    assert summary["mask_type_counts"]["fluorescence_hotspot"] == 1
    assert summary["mask_type_counts"]["exposed_bone"] == 1
    rows = list(csv.DictReader((tmp_path / "out" / "multi.csv").open("r", encoding="utf-8")))
    assert {row["mask_type"] for row in rows} == {"fluorescence_hotspot", "exposed_bone"}
    assert all(row["image_path"] and row["mask_path"] and row["medical_boundary"] for row in rows)
