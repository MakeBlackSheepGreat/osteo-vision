from __future__ import annotations

from typing import Any

from src.pipelines.base import Pipeline, PipelineContext
from src.pipelines.classification import ClassificationPipeline
from src.pipelines.detection import DetectionPipeline
from src.pipelines.quantification import QuantificationPipeline
from src.pipelines.segmentation import SegmentationPipeline


PIPELINES = {
    "classification": ClassificationPipeline,
    "segmentation": SegmentationPipeline,
    "detection": DetectionPipeline,
    "quantification": QuantificationPipeline,
}


class MultitaskPipeline(Pipeline):
    task_type = "multitask"

    def run(self, context: PipelineContext) -> dict[str, Any]:
        merged: dict[str, Any] = {"prediction": {}, "warnings": []}
        steps = context.task_config.get("steps") or ["classification", "segmentation", "detection", "quantification"]
        for step in steps:
            pipeline_cls = PIPELINES.get(str(step))
            if pipeline_cls is None:
                continue
            step_config = dict((context.runtime.get("tasks") or {}).get(str(step), {}))
            step_context = PipelineContext(
                case_id=context.case_id,
                input_summary=context.input_summary,
                runtime=context.runtime,
                task_config=step_config,
                models=context.models,
                adapter_result=context.adapter_result if str(step) == "classification" else None,
            )
            result = pipeline_cls().run(step_context)
            _merge(merged, result)
        return merged


def _merge(target: dict[str, Any], incoming: dict[str, Any]) -> None:
    for key, value in incoming.items():
        if key == "warnings":
            target.setdefault("warnings", []).extend(value)
        elif key == "prediction" and isinstance(value, dict):
            target.setdefault("prediction", {}).update(value)
        elif key in {"lesion_evidence", "quantification", "segmentation_mask", "explanation_evidence"} and isinstance(value, dict):
            target.setdefault(key, {}).update(value)
        else:
            target[key] = value
