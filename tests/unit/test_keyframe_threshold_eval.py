from __future__ import annotations

import pytest

from scripts.evaluate_keyframe_segmentation_proxy import parse_shape, parse_thresholds, select_recommended_threshold


def test_parse_thresholds_accepts_commas_spaces_and_semicolons() -> None:
    assert parse_thresholds("0.5, 0.2;0.35 0.2") == [0.2, 0.35, 0.5]


def test_parse_thresholds_rejects_out_of_range_values() -> None:
    with pytest.raises(ValueError):
        parse_thresholds("0,0.5")


def test_parse_shape_reads_height_width() -> None:
    assert parse_shape("160x256") == (160, 256)


def test_select_recommended_threshold_prefers_guarded_best_dice() -> None:
    rows = [
        {
            "threshold": 0.3,
            "foreground_mean_dice": 0.80,
            "prediction_positive_fraction_mean": 0.15,
            "empty_mask_rate": 0.0,
            "over_segmentation_rate": 0.0,
        },
        {
            "threshold": 0.5,
            "foreground_mean_dice": 0.90,
            "prediction_positive_fraction_mean": 0.12,
            "empty_mask_rate": 0.20,
            "over_segmentation_rate": 0.0,
        },
        {
            "threshold": 0.4,
            "foreground_mean_dice": 0.86,
            "prediction_positive_fraction_mean": 0.11,
            "empty_mask_rate": 0.0,
            "over_segmentation_rate": 0.0,
        },
    ]

    result = select_recommended_threshold(
        rows,
        target_positive_fraction_stats={"median": 0.10},
        max_empty_mask_rate=0.05,
        max_over_segmentation_rate=0.05,
    )

    assert result["threshold"] == 0.4
    assert result["reason"] == "max_dice_with_empty_and_oversegmentation_guards"
