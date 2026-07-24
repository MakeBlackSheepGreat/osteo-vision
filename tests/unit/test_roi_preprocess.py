from __future__ import annotations

import numpy as np

from osteo_vision_core.preprocess.roi import filter_candidates_by_roi, roi_intensity_quantification


def test_roi_intensity_quantification_uses_normalized_rectangles() -> None:
    image = np.zeros((10, 10), dtype=np.float32)
    image[2:7, 2:7] = 0.8
    hints = [{"roi_id": "roi_1", "geometry": {"type": "rect", "x": 0.2, "y": 0.2, "width": 0.5, "height": 0.5}}]

    summary = roi_intensity_quantification(image, hints, threshold=0.6)

    assert summary["roi_quantification_count"] == 1
    assert summary["roi_positive_area_fraction"] == 1.0
    assert summary["roi_mean_intensity"] == 0.8


def test_filter_candidates_by_roi_keeps_only_overlapping_boxes() -> None:
    candidates = [
        {"candidate_id": "inside", "bbox_xyxy": [20, 20, 40, 40], "score": 0.9},
        {"candidate_id": "outside", "bbox_xyxy": [70, 70, 90, 90], "score": 0.8},
    ]
    hints = [{"geometry": {"type": "rect", "x": 0.1, "y": 0.1, "width": 0.5, "height": 0.5}}]

    filtered = filter_candidates_by_roi(candidates, hints, width=100, height=100)

    assert [candidate["candidate_id"] for candidate in filtered] == ["inside"]
    assert filtered[0]["roi_overlap_fraction"] > 0
