"""Report contracts for the medical imaging competition framework.

This module defines the interfaces for report generation, validation, and writing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class IReportGenerator(Protocol):
    """Interface for report generators."""

    def generate(self, data: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
        """Generate a report. Returns report data."""
        ...


class IReportValidator(Protocol):
    """Interface for report validation."""

    def validate(self, report: dict[str, Any]) -> list[str]:
        """Validate a report. Returns list of errors."""
        ...


class IReportWriter(Protocol):
    """Interface for report writers."""

    def write_json(self, data: dict[str, Any], path: str | Path) -> str:
        """Write report as JSON. Returns output path."""
        ...

    def write_csv(self, data: list[dict[str, Any]], path: str | Path, columns: list[str] | None = None) -> str:
        """Write report as CSV. Returns output path."""
        ...

    def write_markdown(self, data: dict[str, Any], path: str | Path) -> str:
        """Write report as Markdown. Returns output path."""
        ...

    def write_html(self, data: dict[str, Any], path: str | Path) -> str:
        """Write report as HTML. Returns output path."""
        ...


class IReportAggregator(Protocol):
    """Interface for report aggregation."""

    def aggregate(self, reports: list[dict[str, Any]]) -> dict[str, Any]:
        """Aggregate multiple reports. Returns aggregated report."""
        ...
