from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.warnings import STATUS_CHECKPOINT_MISSING, warning
from src.models.classifier import DeterministicClassifier
from src.models.detector import FixtureDetector
from src.models.segmenter import FixtureSegmenter
from src.models.adapters import build_adapters, inventory_from_adapters, select_adapter


def checkpoint_warning(runtime: dict[str, Any]) -> list[dict[str, Any]]:
    checkpoint = runtime.get("checkpoint_path")
    if checkpoint and not Path(checkpoint).exists():
        if bool(runtime.get("allow_fixture_on_missing_checkpoint", True)):
            return [warning(STATUS_CHECKPOINT_MISSING)]
        return [warning(STATUS_CHECKPOINT_MISSING, blocking=True)]
    return []


def load_fixture_models(runtime: dict[str, Any], visual_dir: str | Path) -> dict[str, Any]:
    threshold = float(runtime.get("default_threshold", runtime.get("threshold", 0.5)))
    return {
        "classifier": DeterministicClassifier(threshold=threshold),
        "segmenter": FixtureSegmenter(visual_dir),
        "detector": FixtureDetector(),
    }


__all__ = [
    "checkpoint_warning",
    "load_fixture_models",
    "build_adapters",
    "inventory_from_adapters",
    "select_adapter",
]
