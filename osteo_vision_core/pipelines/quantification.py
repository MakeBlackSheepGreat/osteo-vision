from __future__ import annotations

from osteo_vision_core.pipelines.base import Pipeline, PipelineContext


class QuantificationPipeline(Pipeline):
    task_type = "quantification"

    def run(self, context: PipelineContext) -> dict[str, object]:
        metadata = context.input_summary.metadata
        width = metadata.get("width")
        height = metadata.get("height")
        quant = {
            "available": bool(width and height),
            "diameter_px": max(width or 0, height or 0) if width and height else None,
            "area_px": (width * height) if width and height else None,
            "volume_mm3": None,
            "source": "metadata_fixture",
        }
        return {"quantification": quant, "prediction": {"quantification_available": quant["available"]}}
