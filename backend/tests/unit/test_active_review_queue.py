from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw

from backend.src.services.active_review_queue import (
    ActiveReviewConfig,
    build_active_review_queue,
    build_training_manifest_patch,
)


def _write_manifest(
    path: Path,
    frames: list[dict],
    *,
    source: str = "sample.mp4",
    training_eligible: bool = True,
) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": "osteo-vision-frame-details-manifest-v1",
                "case_id": "case_active_review",
                "run_id": "run_active_review",
                "source_path": source,
                "source_record_id": "PMC_TEST_figure_2",
                "source_group_id": "PMC_TEST",
                "source_url": "https://example.org/articles/PMC_TEST/",
                "license": "CC BY 4.0",
                "usage_policy": "weak_label_training_seed_with_attribution",
                "sampling_weight": 0.25,
                "training_eligible": training_eligible,
                "frames": frames,
            }
        ),
        encoding="utf-8",
    )
    return path


def _frame(
    frame_index: int,
    timestamp: float,
    *,
    uncertainty: float,
    area: float,
    instability: float,
    failure: str = "",
    image_path: str | None = None,
    mask_path: str | None = None,
) -> dict:
    return {
        "frame_key": f"{frame_index}-0",
        "frame_index": frame_index,
        "timestamp_sec": timestamp,
        "evidence_path": image_path or f"frame_{frame_index}.jpg",
        "mask_path": mask_path or f"frame_{frame_index}_mask.png",
        "input_domain": "public_fluorescence_proxy_non_target_domain",
        "target_domain_flag": False,
        "positive_area_fraction": area,
        "failure_reason": failure,
        "review_priority": "high",
        "temporal_stability": {
            "instability_score": instability,
            "flicker_warning": instability >= 0.05,
        },
        "video_signal_segmentation": {
            "bone_gate_mask": {"status": "not_available_pending_review", "path": None},
            "risk_mask": {"summary": {"uncertain_area_fraction": uncertainty}},
        },
    }


def _write_artifacts(
    root: Path,
    index: int,
    *,
    empty_mask: bool = False,
    mask_size: tuple[int, int] = (32, 24),
) -> tuple[Path, Path]:
    image_path = root / f"frame_{index}.jpg"
    mask_path = root / f"frame_{index}_mask.png"
    image = Image.new("RGB", (32, 24), color=(35, 80, 45))
    mask = Image.new("L", mask_size, color=0)
    if not empty_mask:
        draw = ImageDraw.Draw(mask)
        draw.rectangle((6, 5, min(mask_size[0] - 2, 20), min(mask_size[1] - 2, 17)), fill=255)
    image.save(image_path)
    mask.save(mask_path)
    return image_path, mask_path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_active_review_queue_scores_deduplicates_and_enforces_interval(
    tmp_path: Path,
) -> None:
    first = _write_manifest(
        tmp_path / "first.json",
        [
            _frame(10, 1.0, uncertainty=0.9, area=0.0, instability=0.08),
            _frame(20, 1.5, uncertainty=0.8, area=0.2, instability=0.01),
            _frame(30, 5.0, uncertainty=0.7, area=0.9, instability=0.02, failure="fallback"),
        ],
    )
    duplicate = _write_manifest(
        tmp_path / "duplicate.json",
        [_frame(10, 1.0, uncertainty=0.2, area=0.2, instability=0.0)],
    )

    payload = build_active_review_queue(
        [first, duplicate],
        config=ActiveReviewConfig(max_frames=10, max_frames_per_source=10, min_interval_sec=2.0),
    )

    assert payload["summary"]["input_candidate_count"] == 4
    assert payload["summary"]["deduplicated_candidate_count"] == 3
    assert payload["summary"]["duplicate_count"] == 1
    assert payload["summary"]["selected_count"] == 2
    assert {row["frame_index"] for row in payload["rows"]} == {10, 30}
    top = payload["rows"][0]
    assert top["frame_index"] == 10
    assert "high_uncertainty" in top["review_reasons"]
    assert "temporal_jump" in top["review_reasons"]
    assert "mask_area_anomaly" in top["review_reasons"]
    assert top["review_state"] == "review_required"
    assert top["sample_weight"] == 1.0


def test_review_updates_preserve_states_and_generate_training_patch(
    tmp_path: Path,
) -> None:
    image_1, mask_1 = _write_artifacts(tmp_path, 1)
    image_2, mask_2 = _write_artifacts(tmp_path, 2)
    image_3, mask_3 = _write_artifacts(tmp_path, 3)
    corrected_mask = tmp_path / "corrected_mask.png"
    corrected = Image.new("L", (32, 24), color=0)
    ImageDraw.Draw(corrected).rectangle((10, 7, 25, 20), fill=255)
    corrected.save(corrected_mask)
    manifest = _write_manifest(
        tmp_path / "frames.json",
        [
            _frame(
                1,
                1.0,
                uncertainty=0.9,
                area=0.1,
                instability=0.01,
                image_path=str(image_1),
                mask_path=str(mask_1),
            ),
            _frame(
                2,
                4.0,
                uncertainty=0.8,
                area=0.2,
                instability=0.02,
                image_path=str(image_2),
                mask_path=str(mask_2),
            ),
            _frame(
                3,
                8.0,
                uncertainty=0.7,
                area=0.3,
                instability=0.03,
                image_path=str(image_3),
                mask_path=str(mask_3),
            ),
        ],
    )
    initial = build_active_review_queue(
        [manifest],
        config=ActiveReviewConfig(max_frames=3, max_frames_per_source=3, min_interval_sec=0.0),
    )
    ids = [row["review_id"] for row in initial["rows"]]
    updates = [
        {"review_id": ids[0], "review_state": "accepted", "review_notes": "verified"},
        {
            "review_id": ids[1],
            "review_state": "modified",
            "modified_mask_path": str(corrected_mask),
        },
        {"review_id": ids[2], "review_state": "rejected"},
    ]

    reviewed = build_active_review_queue(
        [manifest],
        config=ActiveReviewConfig(max_frames=3, max_frames_per_source=3, min_interval_sec=0.0),
        review_updates=updates,
    )
    assert [row["review_state"] for row in reviewed["rows"]] == [
        "accepted",
        "modified",
        "rejected",
    ]
    assert [row["sample_weight"] for row in reviewed["rows"]] == [4.0, 4.0, 0.5]

    patch = build_training_manifest_patch(reviewed, source_review_queue_path="queue.json")
    assert patch["summary"]["patch_row_count"] == 3
    assert patch["summary"]["review_state_counts"] == {
        "accepted": 1,
        "modified": 1,
        "rejected": 1,
    }
    by_state = {row["review_state"]: row for row in patch["rows"]}
    assert by_state["modified"]["mask_path"] == str(corrected_mask.resolve())
    assert by_state["modified"]["label_checksum"] == _sha256(corrected_mask)
    assert by_state["modified"]["label_checksum"] != _sha256(mask_2)
    assert by_state["accepted"]["eligible_for_weighted_training"] is True
    assert by_state["accepted"]["training_eligible"] is True
    assert by_state["accepted"]["source_record_id"] == "PMC_TEST_figure_2"
    assert by_state["accepted"]["source_group_id"] == "PMC_TEST"
    assert by_state["accepted"]["source_url"] == "https://example.org/articles/PMC_TEST/"
    assert by_state["accepted"]["license"] == "CC BY 4.0"
    assert by_state["accepted"]["usage_policy"] == "weak_label_training_seed_with_attribution"
    assert by_state["accepted"]["sampling_weight"] == 0.25
    assert by_state["accepted"]["image_checksum"] == _sha256(image_1)
    assert by_state["accepted"]["label_checksum"] == _sha256(mask_1)
    assert by_state["rejected"]["training_action"] == "negative_or_error_analysis"
    assert by_state["rejected"]["training_eligible"] is False


def test_pending_and_incomplete_modified_rows_are_excluded_from_patch(
    tmp_path: Path,
) -> None:
    manifest = _write_manifest(
        tmp_path / "frames.json",
        [
            _frame(1, 1.0, uncertainty=0.9, area=0.1, instability=0.01),
            _frame(2, 4.0, uncertainty=0.8, area=0.2, instability=0.02),
        ],
    )
    initial = build_active_review_queue(
        [manifest],
        config=ActiveReviewConfig(max_frames=2, max_frames_per_source=2, min_interval_sec=0.0),
    )
    reviewed = build_active_review_queue(
        [manifest],
        config=ActiveReviewConfig(max_frames=2, max_frames_per_source=2, min_interval_sec=0.0),
        review_updates=[{"review_id": initial["rows"][0]["review_id"], "review_state": "modified"}],
    )

    patch = build_training_manifest_patch(reviewed)

    assert patch["summary"]["patch_row_count"] == 0
    assert {item["reason"] for item in patch["skipped"]} == {
        "review_pending",
        "reviewed_mask_missing",
    }


def test_training_patch_rejects_empty_unreadable_and_misaligned_masks(
    tmp_path: Path,
) -> None:
    image_empty, empty_mask = _write_artifacts(tmp_path, 10, empty_mask=True)
    image_bad, unreadable_mask = _write_artifacts(tmp_path, 20)
    unreadable_mask.write_text("not an image", encoding="utf-8")
    image_mismatch, mismatch_mask = _write_artifacts(tmp_path, 30, mask_size=(16, 12))
    manifest = _write_manifest(
        tmp_path / "invalid_masks.json",
        [
            _frame(
                10,
                1.0,
                uncertainty=0.9,
                area=0.1,
                instability=0.01,
                image_path=str(image_empty),
                mask_path=str(empty_mask),
            ),
            _frame(
                20,
                4.0,
                uncertainty=0.8,
                area=0.2,
                instability=0.02,
                image_path=str(image_bad),
                mask_path=str(unreadable_mask),
            ),
            _frame(
                30,
                8.0,
                uncertainty=0.7,
                area=0.3,
                instability=0.03,
                image_path=str(image_mismatch),
                mask_path=str(mismatch_mask),
            ),
        ],
    )
    initial = build_active_review_queue(
        [manifest],
        config=ActiveReviewConfig(max_frames=3, max_frames_per_source=3, min_interval_sec=0.0),
    )
    reviewed = build_active_review_queue(
        [manifest],
        config=ActiveReviewConfig(max_frames=3, max_frames_per_source=3, min_interval_sec=0.0),
        review_updates=[{"review_id": row["review_id"], "review_state": "accepted"} for row in initial["rows"]],
    )

    patch = build_training_manifest_patch(reviewed)

    assert patch["summary"]["patch_row_count"] == 0
    assert {item["reason"] for item in patch["skipped"]} == {
        "reviewed_mask_empty",
        "reviewed_mask_unreadable",
        "mask_image_size_mismatch",
    }


def test_training_patch_requires_explicit_source_training_permission(
    tmp_path: Path,
) -> None:
    image_path, mask_path = _write_artifacts(tmp_path, 40)
    frame = _frame(
        40,
        1.0,
        uncertainty=0.9,
        area=0.1,
        instability=0.01,
        image_path=str(image_path),
        mask_path=str(mask_path),
    )
    frame["sampling_weight"] = 0.0
    manifest = _write_manifest(
        tmp_path / "ineligible_source.json",
        [frame],
        training_eligible=False,
    )
    initial = build_active_review_queue(
        [manifest],
        config=ActiveReviewConfig(max_frames=1, max_frames_per_source=1, min_interval_sec=0.0),
    )
    reviewed = build_active_review_queue(
        [manifest],
        config=ActiveReviewConfig(max_frames=1, max_frames_per_source=1, min_interval_sec=0.0),
        review_updates=[{"review_id": initial["rows"][0]["review_id"], "review_state": "accepted"}],
    )

    patch = build_training_manifest_patch(reviewed)

    assert patch["summary"]["patch_row_count"] == 1
    row = patch["rows"][0]
    assert row["training_eligible"] is False
    assert row["eligible_for_weighted_training"] is False
    assert row["training_action"] == "reviewed_not_training_approved"
    assert row["sampling_weight"] == 0.0
