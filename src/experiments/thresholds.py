from __future__ import annotations

from typing import Any

from src.metrics.classification import classification_metrics, threshold_sweep


def choose_threshold(y_true: list[int], y_score: list[float], strategy: dict[str, Any]) -> dict[str, Any]:
    kind = str(strategy.get("type", "fixed"))
    if kind == "youden":
        sweep = threshold_sweep(y_true, y_score)
        best = sweep.get("best", {})
        threshold = float(best.get("threshold", 0.5))
        return {"type": "youden", "threshold": threshold, "analysis": sweep}
    if kind == "sensitivity_first":
        return _sensitivity_first(y_true, y_score, strategy)
    threshold = float(strategy.get("threshold", 0.5))
    return {
        "type": "fixed",
        "threshold": threshold,
        "analysis": {
            "available": bool(y_true),
            "metrics": classification_metrics(y_true, y_score, threshold) if y_true else {},
        },
    }


def _sensitivity_first(y_true: list[int], y_score: list[float], strategy: dict[str, Any]) -> dict[str, Any]:
    target = float(strategy.get("min_sensitivity", 0.85))
    candidates = [i / 100 for i in range(1, 100)]
    viable: list[dict[str, Any]] = []
    for threshold in candidates:
        metrics = classification_metrics(y_true, y_score, threshold)
        if metrics["sensitivity"] >= target:
            viable.append({"threshold": threshold, "metrics": metrics})
    if not viable:
        return {
            "type": "sensitivity_first",
            "threshold": 0.5,
            "analysis": {"available": False, "reason": "no threshold meets target sensitivity"},
        }
    best = max(viable, key=lambda item: (item["metrics"]["specificity"], item["metrics"]["f1"]))
    return {
        "type": "sensitivity_first",
        "threshold": best["threshold"],
        "analysis": {"available": True, "target_sensitivity": target, "best": best},
    }
