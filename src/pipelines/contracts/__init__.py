"""Pipeline contracts for the medical imaging competition framework.

This module defines the interfaces for pipelines and pipeline registries.
"""

from __future__ import annotations

from typing import Any, Protocol

from src.pipelines.base import PipelineContext


class IPipeline(Protocol):
    """Interface for pipelines."""
    
    task_type: str
    
    def run(self, context: PipelineContext) -> dict[str, Any]:
        """Run the pipeline. Returns result dictionary."""
        ...


class IPipelineRegistry(Protocol):
    """Interface for pipeline registries."""
    
    def register(self, name: str, pipeline_class: type) -> None:
        """Register a pipeline class."""
        ...
    
    def get(self, name: str) -> type | None:
        """Get a pipeline class by name."""
        ...
    
    def list(self) -> list[str]:
        """List all registered pipeline classes."""
        ...
    
    def create(self, name: str, **kwargs: Any) -> IPipeline:
        """Create a pipeline instance."""
        ...


class IPipelineStep(Protocol):
    """Interface for pipeline steps."""
    
    name: str
    
    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute the step. Returns updated context."""
        ...
    
    def validate(self, context: dict[str, Any]) -> list[str]:
        """Validate context for this step. Returns list of errors."""
        ...


class IPipelineOrchestrator(Protocol):
    """Interface for pipeline orchestration."""
    
    def add_step(self, step: IPipelineStep) -> None:
        """Add a step to the pipeline."""
        ...
    
    def execute(self, initial_context: dict[str, Any]) -> dict[str, Any]:
        """Execute all steps in order."""
        ...
