from __future__ import annotations

from typing import Any

import numpy as np


def roi_metric_summary(normalized: np.ndarray, mask: np.ndarray, *, threshold: float = 0.6) -> dict[str, Any]:
    values = np.asarray(normalized, dtype=np.float32)
    selected = np.asarray(mask).astype(bool)
    if values.shape != selected.shape:
        return {"available": False, "reason": "shape_mismatch"}
    if not np.any(selected):
        return {"available": False, "reason": "empty_roi"}
    roi_values = values[selected]
    positive = roi_values >= threshold
    return {
        "available": True,
        "threshold": float(threshold),
        "mean_intensity": round(float(np.mean(roi_values)), 6),
        "max_intensity": round(float(np.max(roi_values)), 6),
        "p95_intensity": round(float(np.percentile(roi_values, 95)), 6),
        "positive_area_px": int(np.count_nonzero(positive)),
        "positive_area_fraction": round(float(np.mean(positive)), 6),
    }
