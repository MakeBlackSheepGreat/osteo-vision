from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.osteo_vision_api.core.disclaimers import (
    ICG_SIGNAL_LIMITATION,
    PLATFORM_SAFETY_DISCLAIMER,
)
from backend.osteo_vision_api.domains.cases.schemas import CaseRecord
from backend.osteo_vision_api.reports.platform_report_sections import (
    bone_activity_checkpoint_section_from_runs,
    clinical_context_section_from_run,
    patient_conditioning_section_from_run,
    task3_fused_image_section_from_runs,
    three_channel_quality_section_from_run,
    three_d_evidence_section_from_run,
    video_signal_section_from_run,
)


def build_platform_report(case: CaseRecord, *, export_meta: dict[str, Any] | None = None) -> dict[str, Any]:
    run_payloads = [run.model_dump(mode="json") for run in case.analysis_runs]
    input_payloads = [asset.model_dump(mode="json") for asset in case.inputs]
    quality_flag_payloads = [flag.model_dump(mode="json") for flag in case.quality_flags]
    roi_payloads = [roi.model_dump(mode="json") for roi in case.rois]
    review_event_payloads = [event.model_dump(mode="json") for event in case.review_events]
    artifact_payloads = [artifact.model_dump(mode="json") for artifact in case.artifacts]
    case_payload = case.model_dump(
        mode="json",
        exclude={
            "inputs",
            "analysis_runs",
            "review_events",
            "artifacts",
            "rois",
            "quality_flags",
        },
    )
    case_payload.update(
        {
            "inputs": input_payloads,
            "analysis_runs": run_payloads,
            "review_events": review_event_payloads,
            "artifacts": artifact_payloads,
            "rois": roi_payloads,
            "quality_flags": quality_flag_payloads,
        }
    )
    latest_run = run_payloads[-1] if run_payloads else None
    return {
        "case": case_payload,
        "case_id": case.case_id,
        "title": case.title,
        "status": case.status.value,
        "created_at": case.created_at.isoformat(),
        "updated_at": case.updated_at.isoformat(),
        "disclaimer_version": case.disclaimer_version,
        "disclaimer": case.disclaimer or PLATFORM_SAFETY_DISCLAIMER,
        "icg_signal_limitation": ICG_SIGNAL_LIMITATION,
        "review_summary": case.review_summary,
        "quality_flags": quality_flag_payloads,
        "inputs": input_payloads,
        "analysis_runs": run_payloads,
        "latest_analysis_run": latest_run,
        "clinical_context_assessment": clinical_context_section_from_run(latest_run),
        "patient_conditioning_evidence": patient_conditioning_section_from_run(latest_run),
        "task3_fused_image_ai": task3_fused_image_section_from_runs(run_payloads),
        "bone_activity_checkpoint_evidence": bone_activity_checkpoint_section_from_runs(run_payloads),
        "video_signal_segmentation": video_signal_section_from_run(latest_run),
        "three_channel_quality": three_channel_quality_section_from_run(latest_run),
        "three_d_evidence": three_d_evidence_section_from_run(
            latest_run,
            fallback_evidence=case.three_d_evidence,
        ),
        "rois": roi_payloads,
        "review_events": review_event_payloads,
        "artifacts": artifact_payloads,
        "warnings": list(case.warnings),
        "export_meta": export_meta or {},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
