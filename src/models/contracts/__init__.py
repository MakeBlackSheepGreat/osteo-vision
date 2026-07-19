"""Model contracts for the medical imaging competition framework.

This module defines the interfaces for model adapters, registries, and checkpoints.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from src.core.schemas import AdapterRequest, AdapterResult, AdapterStatus, ModelSpec


class IModelAdapter(Protocol):
    """Interface for model adapters."""

    def describe(self) -> ModelSpec:
        """Get model specification."""
        ...

    def supports(self, task_type: str, input_type: str, modality: str) -> bool:
        """Check if model supports given task/input/modality."""
        ...

    def warmup(self) -> AdapterStatus:
        """Check if model is available and ready."""
        ...

    def predict(self, request: AdapterRequest) -> AdapterResult:
        """Run inference."""
        ...


class IModelRegistry(Protocol):
    """Interface for model registries."""

    def register(self, name: str, adapter_class: type) -> None:
        """Register a model adapter class."""
        ...

    def get(self, name: str) -> type | None:
        """Get a model adapter class by name."""
        ...

    def list(self) -> list[str]:
        """List all registered model adapter classes."""
        ...

    def build(self, spec: ModelSpec) -> IModelAdapter:
        """Build a model adapter from specification."""
        ...


class ICheckpointManager(Protocol):
    """Interface for checkpoint management."""

    def load(self, path: str | Path) -> Any:
        """Load checkpoint from file."""
        ...

    def save(self, checkpoint: Any, path: str | Path) -> None:
        """Save checkpoint to file."""
        ...

    def validate(self, path: str | Path) -> tuple[bool, str]:
        """Validate checkpoint. Returns (valid, reason)."""
        ...

    def get_metadata(self, path: str | Path) -> dict[str, Any]:
        """Get checkpoint metadata."""
        ...


class IModelSelector(Protocol):
    """Interface for model selection."""

    def select(
        self,
        adapters: list[IModelAdapter],
        task_type: str,
        input_type: str,
        modality: str,
        policy: str = "fixture_fallback",
        explicit_model_id: str | None = None,
    ) -> tuple[IModelAdapter | None, list[AdapterStatus]]:
        """Select best model adapter. Returns (adapter, statuses)."""
        ...
