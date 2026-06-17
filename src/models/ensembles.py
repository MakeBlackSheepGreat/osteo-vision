from __future__ import annotations

import numpy as np


def normalize_weights(count: int, weights: list[float] | None = None) -> np.ndarray:
    if count <= 0:
        raise ValueError("count must be positive")
    if weights is None:
        return np.full(count, 1.0 / count, dtype=np.float64)
    if len(weights) != count:
        raise ValueError("weights length must match probability count")
    values = np.asarray(weights, dtype=np.float64)
    if np.any(values < 0):
        raise ValueError("weights must be non-negative")
    total = float(values.sum())
    if total <= 0:
        raise ValueError("at least one weight must be positive")
    return values / total


def average_probabilities(probabilities: list[np.ndarray], weights: list[float] | None = None) -> np.ndarray:
    if not probabilities:
        raise ValueError("probabilities must not be empty")
    arrays = [np.asarray(item, dtype=np.float64) for item in probabilities]
    shape = arrays[0].shape
    if any(item.shape != shape for item in arrays):
        raise ValueError("all probability arrays must have the same shape")
    normalized_weights = normalize_weights(len(arrays), weights)
    stacked = np.stack(arrays, axis=0)
    averaged = np.tensordot(normalized_weights, stacked, axes=(0, 0))
    return averaged.astype(np.float32)


def predictive_entropy(probabilities: np.ndarray, class_axis: int = 0, eps: float = 1e-8) -> np.ndarray:
    probs = np.asarray(probabilities, dtype=np.float64)
    clipped = np.clip(probs, eps, 1.0)
    return -np.sum(clipped * np.log(clipped), axis=class_axis).astype(np.float32)


def ensemble_variance(probabilities: list[np.ndarray]) -> np.ndarray:
    if not probabilities:
        raise ValueError("probabilities must not be empty")
    arrays = [np.asarray(item, dtype=np.float64) for item in probabilities]
    shape = arrays[0].shape
    if any(item.shape != shape for item in arrays):
        raise ValueError("all probability arrays must have the same shape")
    return np.var(np.stack(arrays, axis=0), axis=0).astype(np.float32)
