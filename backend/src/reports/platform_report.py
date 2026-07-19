from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.src.core.disclaimers import ICG_SIGNAL_LIMITATION, PLATFORM_SAFETY_DISCLAIMER
from backend.src.domains.cases.schemas import CaseRecord
from backend.src.reports.platform_report_sections import (
    bone_activity_checkpoint_section_from_run,
    clinical_context_section_from_run,
    patient_conditioning_section_from_run,
    three_channel_quality_section_from_run,
    three_d_evidence_section_from_run,
    video_signal_section_from_run,
)


def build_platform_report(case: CaseRecord, *, export_meta: dict[str, Any] | None = None) -> dict[str, Any]:
    case_payload = case.model_dump(mode="json")
    latest_run = case.analysis_runs[-1].model_dump(mode="json") if case.analysis_runs else None
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
        "quality_flags": [flag.model_dump(mode="json") for flag in case.quality_flags],
        "inputs": [asset.model_dump(mode="json") for asset in case.inputs],
        "analysis_runs": [run.model_dump(mode="json") for run in case.analysis_runs],
        "latest_analysis_run": latest_run,
        "clinical_context_assessment": clinical_context_section_from_run(latest_run),
        "patient_conditioning_evidence": patient_conditioning_section_from_run(latest_run),
        "bone_activity_checkpoint_evidence": bone_activity_checkpoint_section_from_run(latest_run),
        "video_signal_segmentation": video_signal_section_from_run(latest_run),
        "three_channel_quality": three_channel_quality_section_from_run(latest_run),
        "three_d_evidence": three_d_evidence_section_from_run(
            latest_run,
            fallback_evidence=case.three_d_evidence,
        ),
        "rois": [roi.model_dump(mode="json") for roi in case.rois],
        "review_events": [event.model_dump(mode="json") for event in case.review_events],
        "artifacts": [artifact.model_dump(mode="json") for artifact in case.artifacts],
        "warnings": list(case.warnings),
        "export_meta": export_meta or {},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
