from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import numpy as np
from PIL import Image

from tools.build_keyframe_training_manifest_from_review import build_training_manifest_from_review


def test_build_training_manifest_from_review_json(tmp_path: Path) -> None:
    image_path = tmp_path / "frame.jpg"
    mask_path = tmp_path / "candidate_mask.png"
    image = np.zeros((40, 60, 3), dtype=np.uint8)
    image[10:24, 20:36, 1] = 220
    mask = np.zeros((40, 60), dtype=np.uint8)
    mask[10:24, 20:36] = 255
    Image.fromarray(image).save(image_path)
    Image.fromarray(mask).save(mask_path)
    review_manifest = tmp_path / "case_review_manifest.json"
    review_manifest.write_text(
        json.dumps(
            {
                "schema_version": "osteo-vision-review-manifest-v1",
                "case_id": "case_review",
                "candidates": [
                    {
                        "case_id": "case_review",
                        "run_id": "run_video",
                        "candidate_id": "cand_001",
                        "status": "accepted",
                        "frame_index": 3,
                        "timestamp_sec": 0.5,
                        "bbox_normalized": {
                            "type": "rect",
                            "coordinate_space": "normalized",
                            "x": 0.3,
                            "y": 0.25,
                            "width": 0.2,
                            "height": 0.25,
                        },
                        "mask_path": str(mask_path),
                        "source_path": str(image_path),
                        "image_width": 60,
                        "image_height": 40,
                    },
                    {
                        "case_id": "case_review",
                        "run_id": "run_video",
                        "candidate_id": "cand_rejected",
                        "status": "rejected",
                        "frame_index": 4,
                        "timestamp_sec": 0.8,
                        "source_path": str(image_path),
                        "image_width": 60,
                        "image_height": 40,
                    }
                ],
                "rois": [
                    {
                        "case_id": "case_review",
                        "roi_id": "roi_cand_001",
                        "candidate_id": "cand_001",
                        "review_state": "modified",
                        "geometry": {
                            "type": "rect",
                            "coordinate_space": "normalized",
                            "x": 0.1,
                            "y": 0.2,
                            "width": 0.3,
                            "height": 0.4,
                        },
                    }
                ],
                "review_events": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = build_training_manifest_from_review(
        Namespace(
            input=[str(review_manifest)],
            output_dir=str(tmp_path / "derived"),
            manifest_name="keyframe_training_manifest_from_review.csv",
            dataset_id="review_unit",
            input_domain="unit_review_proxy",
            fluorescence_attribute="proxy_fluorescence",
            review_states="accepted,modified,rejected",
            accepted_weight=3.0,
            modified_weight=4.0,
            rejected_weight=0.5,
            preview_sample_count=4,
            val_fraction=0.2,
            seed=20260705,
        )
    )

    manifest_path = Path(result["manifest_path"])
    summary_path = Path(result["summary_path"])
    assert manifest_path.exists()
    assert summary_path.exists()
    text = manifest_path.read_text(encoding="utf-8")
    assert "human_reviewed_ai_candidate_mask" in text
    assert "human_reviewed_roi_geometry_mask" in text
    assert "human_rejected_ai_candidate_negative_mask" in text
    assert "review_unit" in text
    assert result["sample_count"] == 3
    assert result["review_state_counts"]["accepted"] == 1
    assert result["review_state_counts"]["modified"] == 1
    assert result["review_state_counts"]["rejected"] == 1
    assert result["sample_weight_stats"]["max"] == 4.0
    assert result["sample_weight_stats"]["min"] == 0.5
    generated_masks = list((tmp_path / "derived" / "review_masks").glob("*.png"))
    assert generated_masks
