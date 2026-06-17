"""Dataset contracts for the medical imaging competition framework.

This module defines the interfaces for dataset loading, splitting, and management.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class IDatasetLoader(Protocol):
    """Interface for dataset loading."""
    
    def load(self, path: str | Path) -> list[dict[str, Any]]:
        """Load dataset from file or directory."""
        ...
    
    def load_manifest(self, path: str | Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Load dataset manifest. Returns (rows, info)."""
        ...
    
    def validate(self, data: list[dict[str, Any]], contract: dict[str, Any]) -> list[str]:
        """Validate dataset against contract. Returns list of errors."""
        ...


class ISplitStrategy(Protocol):
    """Interface for data splitting strategies."""
    
    def split(
        self,
        data: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Split data. Returns (split_data, split_info)."""
        ...
    
    def validate_split(
        self,
        train: list[dict[str, Any]],
        val: list[dict[str, Any]],
        test: list[dict[str, Any]] | None = None,
    ) -> list[str]:
        """Validate split. Returns list of warnings."""
        ...


class IManifestReader(Protocol):
    """Interface for manifest reading."""
    
    def read(self, path: str | Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Read manifest. Returns (rows, info)."""
        ...
    
    def validate(self, rows: list[dict[str, Any]], contract: dict[str, Any]) -> list[str]:
        """Validate manifest against contract. Returns list of errors."""
        ...


class IDataLeakageDetector(Protocol):
    """Interface for data leakage detection."""
    
    def detect(
        self,
        data: list[dict[str, Any]],
        split_column: str = "patient_id",
    ) -> dict[str, Any]:
        """Detect data leakage. Returns leakage report."""
        ...
