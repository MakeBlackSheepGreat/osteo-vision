from __future__ import annotations

from src.pipelines.base import Pipeline, PipelineContext


class DetectionPipeline(Pipeline):
    task_type = "detection"

    def run(self, context: PipelineContext) -> dict[str, object]:
        max_candidates = int(context.task_config.get("max_candidates", 3))
        candidates = context.models["detector"].detect(context.input_summary.metadata, max_candidates=max_candidates)
        return {
            "lesion_evidence": {"type": "candidate_boxes", "candidates": candidates},
            "prediction": {"candidate_count": len(candidates), "candidates": candidates},
            "score": candidates[0]["score"] if candidates else None,
        }
