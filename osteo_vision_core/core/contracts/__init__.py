"""Core contracts for the medical imaging competition framework.

This module defines the core interfaces and protocols that all modules should implement.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

# ============================================================================
# Configuration Contracts
# ============================================================================


class IConfigLoader(Protocol):
    """Interface for configuration loading."""

    def load(self, path: str | Path) -> dict[str, Any]:
        """Load configuration from file."""
        ...

    def validate(self, config: dict[str, Any]) -> bool:
        """Validate configuration."""
        ...

    def merge(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Merge two configurations."""
        ...


class IConfigValidator(Protocol):
    """Interface for configuration validation."""

    def validate_task_config(self, config: dict[str, Any]) -> list[str]:
        """Validate task configuration. Returns list of errors."""
        ...

    def validate_model_config(self, config: dict[str, Any]) -> list[str]:
        """Validate model configuration. Returns list of errors."""
        ...

    def validate_pipeline_config(self, config: dict[str, Any]) -> list[str]:
        """Validate pipeline configuration. Returns list of errors."""
        ...


# ============================================================================
# Registry Contracts
# ============================================================================


class IRegistry(Protocol):
    """Interface for component registries."""

    def register(self, name: str, component: Any) -> None:
        """Register a component."""
        ...

    def get(self, name: str) -> Any | None:
        """Get a component by name."""
        ...

    def list(self) -> list[str]:
        """List all registered components."""
        ...

    def has(self, name: str) -> bool:
        """Check if a component is registered."""
        ...


# ============================================================================
# Logger Contracts
# ============================================================================


class ILogger(Protocol):
    """Interface for logging."""

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        ...

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        ...

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        ...

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message."""
        ...

    def critical(self, message: str, **kwargs: Any) -> None:
        """Log critical message."""
        ...


# ============================================================================
# Data Contracts
# ============================================================================


@dataclass
class IDataPoint:
    """Interface for data points."""

    id: str
    path: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        raise NotImplementedError


@dataclass
class IBatch:
    """Interface for data batches."""

    data_points: list[IDataPoint]
    labels: list[Any] | None = None

    def __len__(self) -> int:
        """Get batch size."""
        return len(self.data_points)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        raise NotImplementedError


# ============================================================================
# Lifecycle Contracts
# ============================================================================


class IInitializable(Protocol):
    """Interface for initializable components."""

    def initialize(self, config: dict[str, Any]) -> None:
        """Initialize the component."""
        ...


class IStartable(Protocol):
    """Interface for startable components."""

    def start(self) -> None:
        """Start the component."""
        ...

    def stop(self) -> None:
        """Stop the component."""
        ...


class IHealthCheck(Protocol):
    """Interface for health checkable components."""

    def health_check(self) -> dict[str, Any]:
        """Check component health."""
        ...
