from __future__ import annotations

from typing import Any


def classification_metrics(y_true: list[int], y_score: list[float], threshold: float = 0.5) -> dict[str, Any]:
    if not y_true:
        return {}
    y_pred = [1 if score >= threshold else 0 for score in y_score]
    tp = sum(1 for truth, pred in zip(y_true, y_pred, strict=False) if truth == 1 and pred == 1)
    tn = sum(1 for truth, pred in zip(y_true, y_pred, strict=False) if truth == 0 and pred == 0)
    fp = sum(1 for truth, pred in zip(y_true, y_pred, strict=False) if truth == 0 and pred == 1)
    fn = sum(1 for truth, pred in zip(y_true, y_pred, strict=False) if truth == 1 and pred == 0)
    total = max(1, len(y_true))
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    specificity = tn / max(1, tn + fp)
    f1 = 2 * precision * recall / max(1e-12, precision + recall)
    return {
        "accuracy": (tp + tn) / total,
        "sensitivity": recall,
        "specificity": specificity,
        "precision": precision,
        "f1": f1,
        "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
        "threshold": threshold,
    }


def threshold_sweep(y_true: list[int], y_score: list[float]) -> dict[str, Any]:
    if not y_true:
        return {"available": False, "reason": "labels_missing"}
    candidates = [i / 20 for i in range(1, 20)]
    rows = []
    best = {"threshold": 0.5, "youden_j": -1.0}
    for threshold in candidates:
        metrics = classification_metrics(y_true, y_score, threshold)
        youden = metrics["sensitivity"] + metrics["specificity"] - 1
        rows.append({"threshold": threshold, "youden_j": youden, **metrics})
        if youden > best["youden_j"]:
            best = {"threshold": threshold, "youden_j": youden}
    return {"available": True, "best": best, "rows": rows}
