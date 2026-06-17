from __future__ import annotations

import numpy as np

from src.metrics.segmentation import (
    binary_segmentation_metrics,
    cldice_score,
    hd95,
    normalized_surface_dice,
    per_label_segmentation_metrics,
)
from src.models.ensembles import average_probabilities, ensemble_variance, normalize_weights, predictive_entropy


def test_binary_metrics_perfect_overlap() -> None:
    mask = np.zeros((5, 5), dtype=np.uint8)
    mask[1:4, 1:4] = 1

    metrics = binary_segmentation_metrics(mask, mask, include_cldice=True)

    assert metrics["dice"] == 1.0
    assert metrics["iou"] == 1.0
    assert metrics["hd95"] == 0.0
    assert metrics["nsd"] == 1.0
    assert metrics["cldice"] == 1.0


def test_surface_metrics_shifted_masks_are_finite() -> None:
    pred = np.zeros((6, 6), dtype=np.uint8)
    true = np.zeros((6, 6), dtype=np.uint8)
    pred[1:4, 1:4] = 1
    true[2:5, 1:4] = 1

    assert hd95(pred, true) is not None
    nsd = normalized_surface_dice(pred, true, tolerance_mm=1.0)
    assert nsd is not None
    assert 0.0 <= nsd <= 1.0


def test_cldice_penalizes_missing_tubular_segment() -> None:
    true = np.zeros((7, 7), dtype=np.uint8)
    pred = np.zeros((7, 7), dtype=np.uint8)
    true[3, 1:6] = 1
    pred[3, 1:3] = 1
    pred[3, 4:6] = 1

    assert cldice_score(pred, true) < 1.0


def test_per_label_metrics_adds_cldice_for_tubular_labels() -> None:
    pred = np.array([[0, 1, 1], [0, 2, 0]])
    true = np.array([[0, 1, 0], [0, 2, 2]])

    metrics = per_label_segmentation_metrics(pred, true, labels=[1, 2], tubular_labels=[2])

    assert "cldice" not in metrics["1"]
    assert "cldice" in metrics["2"]


def test_probability_ensemble_helpers() -> None:
    p1 = np.array([[[0.8, 0.2]], [[0.2, 0.8]]], dtype=np.float32)
    p2 = np.array([[[0.6, 0.4]], [[0.4, 0.6]]], dtype=np.float32)

    weights = normalize_weights(2, [2, 1])
    averaged = average_probabilities([p1, p2], weights=[2, 1])
    entropy = predictive_entropy(averaged, class_axis=0)
    variance = ensemble_variance([p1, p2])

    assert np.allclose(weights, [2 / 3, 1 / 3])
    assert averaged.shape == p1.shape
    assert entropy.shape == (1, 2)
    assert variance.shape == p1.shape
