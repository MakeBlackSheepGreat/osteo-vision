from __future__ import annotations


def identity_calibration(probability: float) -> float:
    return max(0.0, min(1.0, float(probability)))

