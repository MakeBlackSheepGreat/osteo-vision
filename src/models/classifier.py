from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


class DeterministicClassifier:
    """A stable fixture classifier used before real checkpoints exist."""

    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = float(threshold)

    def predict_probability(self, input_path: str | Path, metadata: dict[str, Any] | None = None) -> float:
        payload = f"{Path(input_path).as_posix()}|{metadata or {}}".encode("utf-8", errors="ignore")
        value = int(hashlib.sha256(payload).hexdigest()[:8], 16)
        return round((value % 1000) / 1000.0, 6)

    def class_label(self, probability: float) -> str:
        return "positive" if probability >= self.threshold else "negative"
