from __future__ import annotations


def candidate_recall(found: int, total: int) -> float:
    return 0.0 if total <= 0 else found / total

