from __future__ import annotations

from osteo_vision_core.pipelines.base import Pipeline, PipelineContext


class SegmentationPipeline(Pipeline):
    task_type = "segmentation"

    def run(self, context: PipelineContext) -> dict[str, object]:
        adapter_result = context.adapter_result or {}
        if adapter_result.get("segmentation_mask"):
            return {
                "segmentation_mask": adapter_result.get("segmentation_mask", {}),
                "lesion_evidence": adapter_result.get("lesion_evidence", {}),
                "quantification": adapter_result.get("quantification", {}),
                "prediction": adapter_result.get("prediction", {"segmentation_available": True}),
                "score": adapter_result.get("score"),
                "warnings": [],
            }
        mask = context.models["segmenter"].predict_mask(context.case_id, context.input_summary.metadata)
        area = mask.get("area_px")
        return {
            "segmentation_mask": mask,
            "lesion_evidence": {"type": "mask", "source": mask.get("source"), "path": mask.get("path")},
            "quantification": {"area_px": area, "available": True, "source": "fixture_mask"},
            "prediction": {"segmentation_available": True, "mask_path": mask.get("path")},
        }
