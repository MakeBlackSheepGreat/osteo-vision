from __future__ import annotations

import csv
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
                        "source_video_path": "videos/shared_case.mp4",
                        "source_group_id": "source_group_alpha",
                        "source_record_id": "public_source_001",
                        "source_url": "https://example.test/source/001",
                        "license": "CC BY 4.0",
                        "usage_policy": "training_allowed_with_attribution",
                        "sampling_weight": 0.25,
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
                        "source_video_path": "videos/shared_case.mp4",
                        "image_width": 60,
                        "image_height": 40,
                    },
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
            domain_tier="near_domain",
            license="internal_review_feedback_nonredistributable",
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
    assert result["domain_tier_counts"]["near_domain"] == 3
    assert result["source_group_split"]["leakage_detected"] is False
    generated_masks = list((tmp_path / "derived" / "review_masks").glob("*.png"))
    assert generated_masks
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    accepted = next(row for row in rows if row["review_state"] == "accepted")
    modified = next(row for row in rows if row["review_state"] == "modified")
    assert accepted["license"] == "CC BY 4.0"
    assert accepted["usage_policy"] == "training_allowed_with_attribution"
    assert accepted["source_url"] == "https://example.test/source/001"
    assert accepted["source_record_id"] == "public_source_001"
    assert accepted["source_group_id"] == "source_group_alpha"
    assert accepted["sampling_weight"] == "0.25"
    assert accepted["training_eligible"] == "True"
    assert accepted["checksum"] == accepted["image_checksum"]
    assert len(accepted["checksum"]) == 64
    assert len(accepted["label_checksum"]) == 64
    assert modified["license"] == "CC BY 4.0"


def _args(tmp_path: Path, review_manifest: Path) -> Namespace:
    return Namespace(
        input=[str(review_manifest)],
        output_dir=str(tmp_path / "derived"),
        manifest_name="keyframe_training_manifest_from_review.csv",
        dataset_id="review_unit",
        input_domain="unit_review_proxy",
        fluorescence_attribute="proxy_fluorescence",
        domain_tier="near_domain",
        license="fallback_license",
        review_states="accepted,modified",
        accepted_weight=4.0,
        modified_weight=4.0,
        rejected_weight=0.5,
        preview_sample_count=4,
        val_fraction=0.2,
        seed=20260705,
    )


def test_modified_candidate_prefers_valid_modified_mask_and_inherits_row_fields(tmp_path: Path) -> None:
    image_path = tmp_path / "frame.png"
    stale_mask_path = tmp_path / "stale_mask.png"
    modified_mask_path = tmp_path / "modified_mask.png"
    Image.new("RGB", (50, 40), (20, 30, 40)).save(image_path)
    stale = np.zeros((40, 50), dtype=np.uint8)
    stale[1:4, 1:4] = 255
    modified = np.zeros((40, 50), dtype=np.uint8)
    modified[10:30, 15:35] = 255
    Image.fromarray(stale).save(stale_mask_path)
    Image.fromarray(modified).save(modified_mask_path)
    review_manifest = tmp_path / "modified_review.json"
    review_manifest.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "candidate_id": "modified_001",
                        "review_state": "modified",
                        "source_path": str(image_path),
                        "mask_path": str(stale_mask_path),
                        "modified_mask_path": str(modified_mask_path),
                        "source_group_id": "pmc_group",
                        "source_record_id": "PMC_figure_2",
                        "source_url": "https://example.test/pmc",
                        "license": "CC BY",
                        "usage_policy": "training_allowed_with_attribution",
                        "sampling_weight": 0.25,
                    }
                ],
                "rois": [],
            }
        ),
        encoding="utf-8",
    )
    result = build_training_manifest_from_review(_args(tmp_path, review_manifest))
    with Path(result["manifest_path"]).open("r", encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert Path(row["mask_path"]) == modified_mask_path
    assert row["source_record_id"] == "PMC_figure_2"
    assert row["sampling_weight"] == "0.25"
    assert float(row["positive_area_fraction"]) == float((modified > 0).mean())


def test_invalid_review_masks_are_skipped_with_specific_quality_reasons(tmp_path: Path) -> None:
    image_path = tmp_path / "frame.png"
    Image.new("RGB", (20, 20), (0, 0, 0)).save(image_path)
    masks: dict[str, Path] = {}
    arrays = {
        "empty": np.zeros((20, 20), dtype=np.uint8),
        "nonbinary": np.tile(np.arange(20, dtype=np.uint8), (20, 1)),
        "full": np.full((20, 20), 255, dtype=np.uint8),
        "wrong_size": np.ones((10, 10), dtype=np.uint8) * 255,
    }
    for name, array in arrays.items():
        masks[name] = tmp_path / f"{name}.png"
        Image.fromarray(array).save(masks[name])
    review_manifest = tmp_path / "invalid_review.json"
    review_manifest.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "candidate_id": name,
                        "review_state": "accepted",
                        "source_path": str(image_path),
                        "mask_path": str(mask_path),
                        "source_group_id": f"group_{name}",
                    }
                    for name, mask_path in masks.items()
                ],
                "rois": [],
            }
        ),
        encoding="utf-8",
    )
    result = build_training_manifest_from_review(_args(tmp_path, review_manifest))
    reasons = {item["candidate_id"]: item["reason"] for item in result["skipped"]}
    assert result["sample_count"] == 0
    assert reasons["empty"] == "empty_mask"
    assert reasons["nonbinary"].startswith("mask_not_binary")
    assert reasons["full"].startswith("unreasonable_mask_area")
    assert reasons["wrong_size"].startswith("mask_size_mismatch")
