from __future__ import annotations

import numpy as np

from backend.osteo_vision_api.services.roi_service import roi_metric_summary


def test_roi_metric_summary() -> None:
    image = np.array([[0.1, 0.7], [0.8, 0.2]], dtype=np.float32)
    mask = np.array([[0, 1], [1, 0]], dtype=np.uint8)
    metrics = roi_metric_summary(image, mask, threshold=0.6)
    assert metrics["available"] is True
    assert metrics["positive_area_px"] == 2
    assert metrics["mean_intensity"] == 0.75
