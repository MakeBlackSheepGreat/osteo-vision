from __future__ import annotations

from src.pipelines.base import Pipeline, PipelineContext


class SegmentationPipeline(Pipeline):
    task_type = "segmentation"

    def run(self, context: PipelineContext) -> dict[str, object]:
        mask = context.models["segmenter"].predict_mask(context.case_id, context.input_summary.metadata)
        area = mask.get("area_px")
        return {
            "segmentation_mask": mask,
            "lesion_evidence": {"type": "mask", "source": mask.get("source"), "path": mask.get("path")},
            "quantification": {"area_px": area, "available": True, "source": "fixture_mask"},
            "prediction": {"segmentation_available": True, "mask_path": mask.get("path")},
        }

