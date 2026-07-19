from __future__ import annotations

import pytest

from src.datasets.group_splits import assert_no_group_leakage, assign_group_split, group_leakage_report


def test_assign_group_split_keeps_frames_from_one_video_together() -> None:
    splits = {
        assign_group_split("C:/data/video_01.mp4", seed=42, val_fraction=0.2, test_fraction=0.1)
        for _frame_index in range(20)
    }
    assert len(splits) == 1


def test_group_leakage_report_detects_cross_split_source() -> None:
    rows = [
        {"case_id": "a_1", "source_path": "video_a.mp4", "split": "train"},
        {"case_id": "a_2", "source_path": "video_a.mp4", "split": "val"},
    ]
    report = group_leakage_report(rows)
    assert report["leakage_detected"] is True
    assert report["leaking_group_count"] == 1
    with pytest.raises(ValueError, match="crossing splits"):
        assert_no_group_leakage(rows, context="unit test")


def test_explicit_source_group_id_takes_precedence_over_case_id() -> None:
    rows = [
        {"case_id": "frame_1", "source_group_id": "video_a", "split": "train"},
        {"case_id": "frame_2", "source_group_id": "video_a", "split": "val"},
    ]
    report = group_leakage_report(rows)
    assert report["group_count"] == 1
    assert report["leakage_detected"] is True
