"""Preprocessing contracts for the medical imaging competition framework.

This module defines the interfaces for preprocessing, validation, and post-processing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from osteo_vision_core.core.schemas import InputSummary


class IPreprocessor(Protocol):
    """Interface for preprocessors."""

    def preprocess(self, input_path: str | Path, config: dict[str, Any] | None = None) -> dict[str, Any]:
        """Preprocess input data. Returns preprocessed data and metadata."""
        ...

    def validate_input(self, input_path: str | Path) -> tuple[bool, str]:
        """Validate input. Returns (valid, reason)."""
        ...


class IInputValidator(Protocol):
    """Interface for input validation."""

    def validate(self, path: str | Path) -> InputSummary:
        """Validate input and return summary."""
        ...

    def detect_type(self, path: str | Path) -> str:
        """Detect input type."""
        ...

    def assess_quality(self, path: str | Path, input_type: str) -> tuple[bool, str]:
        """Assess input quality. Returns (accepted, reason)."""
        ...


class IPostProcessor(Protocol):
    """Interface for post-processing."""

    def postprocess(self, data: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
        """Post-process data. Returns processed data."""
        ...


class IImageReader(Protocol):
    """Interface for image readers."""

    def read(self, path: str | Path) -> Any:
        """Read image from file."""
        ...

    def get_metadata(self, path: str | Path) -> dict[str, Any]:
        """Get image metadata."""
        ...

    def supports(self, path: str | Path) -> bool:
        """Check if this reader supports the given file."""
        ...


class IImageWriter(Protocol):
    """Interface for image writers."""

    def write(self, data: Any, path: str | Path) -> None:
        """Write image to file."""
        ...

    def supports(self, format: str) -> bool:
        """Check if this writer supports the given format."""
        ...
