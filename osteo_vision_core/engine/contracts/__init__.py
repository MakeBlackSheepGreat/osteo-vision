"""Engine contracts for the Osteo Vision medical imaging platform.

This module defines the interfaces for inference, training, and benchmarking.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from osteo_vision_core.core.schemas import PredictionResult


class IInferenceService(Protocol):
    """Interface for inference services."""

    def diagnose(
        self,
        input_path: str | Path,
        task_type: str | None = None,
        case_id: str | None = None,
        model_id: str | None = None,
    ) -> PredictionResult:
        """Run inference on a single input."""
        ...

    def model_inventory(self) -> list[dict[str, Any]]:
        """Get list of available models."""
        ...


class IExperimentRunner(Protocol):
    """Interface for experiment runners."""

    def run(self, spec_path: str | Path) -> dict[str, Any]:
        """Run an experiment. Returns experiment results."""
        ...

    def validate_spec(self, spec_path: str | Path) -> list[str]:
        """Validate experiment specification. Returns list of errors."""
        ...


class IBenchmarkEvaluator(Protocol):
    """Interface for benchmark evaluators."""

    def evaluate(
        self,
        config_path: str | Path,
        manifest_path: str | Path,
        output_dir: str | Path,
    ) -> dict[str, Any]:
        """Run benchmark evaluation. Returns evaluation results."""
        ...

    def validate_config(self, config_path: str | Path) -> list[str]:
        """Validate benchmark configuration. Returns list of errors."""
        ...


class ITrainer(Protocol):
    """Interface for trainers."""

    def train(
        self,
        config: dict[str, Any],
        train_data: list[dict[str, Any]],
        val_data: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Train a model. Returns training results."""
        ...

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        """Validate training configuration. Returns list of errors."""
        ...
