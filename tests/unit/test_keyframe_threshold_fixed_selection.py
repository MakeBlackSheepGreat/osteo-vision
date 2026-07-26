from __future__ import annotations

import pytest

from scripts.evaluate_keyframe_segmentation_proxy import fixed_threshold_recommendation


def test_fixed_threshold_uses_validation_value_without_reselecting() -> None:
    rows = [{"threshold": 0.4, "foreground_mean_dice": 0.8}, {"threshold": 0.5, "foreground_mean_dice": 0.9}]

    result = fixed_threshold_recommendation(rows, threshold=0.4)

    assert result["threshold"] == 0.4
    assert result["selected_row"] == rows[0]
    assert result["reason"] == "fixed_threshold_from_validation"


def test_fixed_threshold_requires_scanned_value() -> None:
    with pytest.raises(ValueError, match="absent"):
        fixed_threshold_recommendation([{"threshold": 0.4}], threshold=0.45)
