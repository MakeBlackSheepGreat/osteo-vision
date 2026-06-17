from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.core.schemas import InputSummary


@dataclass
class PipelineContext:
    case_id: str
    input_summary: InputSummary
    runtime: dict[str, Any]
    task_config: dict[str, Any]
    models: dict[str, Any]
    adapter_result: dict[str, Any] | None = None


class Pipeline:
    task_type = "base"

    def run(self, context: PipelineContext) -> dict[str, Any]:
        raise NotImplementedError
