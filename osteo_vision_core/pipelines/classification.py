from __future__ import annotations

from osteo_vision_core.core.warnings import STATUS_LOW_CONFIDENCE, warning
from osteo_vision_core.pipelines.base import Pipeline, PipelineContext


class ClassificationPipeline(Pipeline):
    task_type = "classification"

    def run(self, context: PipelineContext) -> dict[str, object]:
        threshold = float(context.runtime.get("default_threshold", 0.5))
        adapter_result = context.adapter_result or {}
        probability = adapter_result.get("probability")
        label = adapter_result.get("class_label")
        if probability is None:
            probability = context.models["classifier"].predict_probability(
                context.input_summary.path, context.input_summary.metadata
            )
        probability = float(probability)
        if label is None:
            label = context.models["classifier"].class_label(probability)
        margin = abs(probability - threshold)
        warnings = []
        if margin <= float(context.runtime.get("low_confidence_margin", 0.1)):
            warnings.append(warning(STATUS_LOW_CONFIDENCE))
        risk_level = _risk_level(probability, context.task_config.get("risk_mapping", {}))
        return {
            "prediction": {"label": label, "probability": probability, "threshold": threshold},
            "probability": probability,
            "score": probability,
            "class_label": label,
            "risk_level": risk_level,
            "threshold": threshold,
            "warnings": warnings,
        }


def _risk_level(probability: float, mapping: dict[str, object]) -> str:
    for name, bounds in mapping.items():
        if isinstance(bounds, list) and len(bounds) == 2 and float(bounds[0]) <= probability <= float(bounds[1]):
            return str(name)
    if probability >= 0.66:
        return "high"
    if probability >= 0.33:
        return "medium"
    return "low"
