from __future__ import annotations

from typing import Any

import numpy as np


def identity_calibration(probability: float) -> float:
    return max(0.0, min(1.0, float(probability)))


def sigmoid_with_temperature(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    safe_temperature = max(1e-3, float(temperature))
    scaled = np.clip(np.asarray(logits, dtype=np.float64) / safe_temperature, -60.0, 60.0)
    return (1.0 / (1.0 + np.exp(-scaled))).astype(np.float32)


def binary_brier_score(targets: np.ndarray, probabilities: np.ndarray) -> float:
    target = np.asarray(targets, dtype=np.float32).reshape(-1)
    probability = np.clip(np.asarray(probabilities, dtype=np.float32).reshape(-1), 0.0, 1.0)
    if target.size == 0 or target.size != probability.size:
        raise ValueError("targets and probabilities must have the same non-zero size")
    return float(np.mean((probability - target) ** 2))


def expected_calibration_error(
    targets: np.ndarray,
    probabilities: np.ndarray,
    *,
    bins: int = 15,
) -> dict[str, Any]:
    target = np.asarray(targets, dtype=np.float32).reshape(-1)
    probability = np.clip(np.asarray(probabilities, dtype=np.float32).reshape(-1), 0.0, 1.0)
    if target.size == 0 or target.size != probability.size:
        raise ValueError("targets and probabilities must have the same non-zero size")
    edges = np.linspace(0.0, 1.0, max(2, int(bins)) + 1, dtype=np.float32)
    rows: list[dict[str, Any]] = []
    ece = 0.0
    for index in range(len(edges) - 1):
        lower = float(edges[index])
        upper = float(edges[index + 1])
        selected = (probability >= lower) & (probability < upper if index < len(edges) - 2 else probability <= upper)
        count = int(selected.sum())
        if count == 0:
            rows.append({"lower": lower, "upper": upper, "count": 0, "confidence": None, "accuracy": None})
            continue
        confidence = float(probability[selected].mean())
        accuracy = float(target[selected].mean())
        gap = abs(confidence - accuracy)
        ece += gap * (count / target.size)
        rows.append(
            {
                "lower": lower,
                "upper": upper,
                "count": count,
                "confidence": confidence,
                "accuracy": accuracy,
                "gap": gap,
            }
        )
    return {"ece": float(ece), "bin_count": len(rows), "sample_count": int(target.size), "bins": rows}


def fit_binary_temperature(
    logits: np.ndarray,
    targets: np.ndarray,
    *,
    candidates: np.ndarray | None = None,
    max_samples: int = 250_000,
    seed: int = 20260710,
) -> dict[str, Any]:
    logit = np.asarray(logits, dtype=np.float32).reshape(-1)
    target = np.asarray(targets, dtype=np.float32).reshape(-1)
    if logit.size == 0 or logit.size != target.size:
        raise ValueError("logits and targets must have the same non-zero size")
    if logit.size > max_samples:
        rng = np.random.default_rng(seed)
        indexes = rng.choice(logit.size, size=max_samples, replace=False)
        logit = logit[indexes]
        target = target[indexes]
    temperatures = (
        np.asarray(candidates, dtype=np.float32)
        if candidates is not None
        else np.geomspace(0.35, 5.0, 81, dtype=np.float32)
    )
    best_temperature = 1.0
    best_nll = float("inf")
    for temperature in temperatures:
        probability = np.clip(sigmoid_with_temperature(logit, float(temperature)), 1e-7, 1.0 - 1e-7)
        nll = float(-np.mean(target * np.log(probability) + (1.0 - target) * np.log(1.0 - probability)))
        if nll < best_nll:
            best_nll = nll
            best_temperature = float(temperature)
    uncalibrated = sigmoid_with_temperature(logit, 1.0)
    calibrated = sigmoid_with_temperature(logit, best_temperature)
    return {
        "method": "temperature_scaling_grid_search",
        "temperature": best_temperature,
        "sample_count": int(logit.size),
        "negative_log_likelihood": best_nll,
        "ece_before": expected_calibration_error(target, uncalibrated)["ece"],
        "ece_after": expected_calibration_error(target, calibrated)["ece"],
        "brier_before": binary_brier_score(target, uncalibrated),
        "brier_after": binary_brier_score(target, calibrated),
    }


def predictive_entropy(probability: np.ndarray) -> np.ndarray:
    value = np.clip(np.asarray(probability, dtype=np.float32), 1e-6, 1.0 - 1e-6)
    entropy = -(value * np.log(value) + (1.0 - value) * np.log(1.0 - value))
    return np.clip(entropy / np.log(2.0), 0.0, 1.0).astype(np.float32)
