from __future__ import annotations

import numpy as np

from src.metrics.calibration import (
    binary_brier_score,
    expected_calibration_error,
    fit_binary_temperature,
    predictive_entropy,
)


def test_calibration_metrics_and_temperature_fit_are_finite() -> None:
    logits = np.asarray([-4.0, -1.0, 1.0, 4.0], dtype=np.float32)
    targets = np.asarray([0, 0, 1, 1], dtype=np.float32)
    fit = fit_binary_temperature(logits, targets, max_samples=100)
    probabilities = 1.0 / (1.0 + np.exp(-logits))
    assert fit["temperature"] > 0
    assert binary_brier_score(targets, probabilities) < 0.1
    assert expected_calibration_error(targets, probabilities)["ece"] >= 0
    entropy = predictive_entropy(probabilities)
    assert entropy.shape == probabilities.shape
    assert np.all((entropy >= 0) & (entropy <= 1))
