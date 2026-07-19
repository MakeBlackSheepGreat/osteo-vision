from __future__ import annotations

import numpy as np
import pytest

from scripts.evaluate_keyframe_segmentation_proxy import (
    binary_precision_recall,
    boundary_f1,
    parse_shape,
    parse_thresholds,
    select_recommended_threshold,
)


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


def test_boundary_f1_is_one_for_identical_mask() -> None:
    mask = np.zeros((20, 24), dtype=bool)
    mask[4:14, 6:18] = True
    assert boundary_f1(mask, mask) == pytest.approx(1.0)


def test_binary_precision_recall_reports_foreground_errors() -> None:
    target = np.asarray([[1, 1], [0, 0]], dtype=bool)
    prediction = np.asarray([[1, 0], [1, 0]], dtype=bool)

    precision, recall = binary_precision_recall(prediction, target)

    assert precision == pytest.approx(0.5)
    assert recall == pytest.approx(0.5)
