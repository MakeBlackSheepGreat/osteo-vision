from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from backend.osteo_vision_api.domains.cases.enums import CaseStatus
from backend.osteo_vision_api.domains.cases.schemas import AnalysisRun, CaseRecord
from backend.osteo_vision_api.reports.platform_markdown import build_platform_markdown
from backend.osteo_vision_api.reports.platform_report import build_platform_report
from backend.osteo_vision_api.reports.quantification_csv import write_quantification_csv
from backend.osteo_vision_api.services.analysis_outputs import fusion_ai_candidate_regions
from backend.osteo_vision_api.services.export_core_files import _quantification_rows


def test_task3_boundaries_enter_physician_review_and_export_sections(tmp_path: Path) -> None:
    source_path = tmp_path / "task2_fused.png"
    Image.fromarray(np.zeros((64, 96, 3), dtype=np.uint8)).save(source_path)
    evidence = _task3_evidence(source_path)

    candidates = fusion_ai_candidate_regions("run_task3", evidence, max_per_boundary_type=1)

    assert len(candidates) == 2
    assert {candidate.risk_type for candidate in candidates} == {
        "signal_candidate_boundary",
        "uncertain_boundary",
    }
    assert all(candidate.metadata["task_role"] == "task3_ai_on_task2_fused_image" for candidate in candidates)
    assert all(candidate.metadata["source_path"] == str(source_path) for candidate in candidates)
    assert all(candidate.metadata["clinical_claim_allowed"] is False for candidate in candidates)
    assert candidates[0].metadata["activity_class"] == "low_activity_candidate"

    run = AnalysisRun(
        run_id="run_task3",
        case_id="case_task3",
        status="completed",
        candidate_regions=candidates,
        fused_outputs={"fused_image_ai": evidence},
        quantitative_summary={"task3_review_candidate_count": len(candidates)},
    )
    case = CaseRecord(
        case_id="case_task3",
        title="Task 3 report",
        status=CaseStatus.ANALYZED,
        analysis_runs=[run],
    )

    report = build_platform_report(case)
    section = report["task3_fused_image_ai"]
    assert section["available"] is True
    assert section["candidate_count"] == 3
    assert section["evaluated_candidate_count"] == 3
    assert section["suppressed_candidate_count"] == 0
    assert section["boundary_type_counts"]["uncertain_boundary"] == 1
    assert section["activity_class_counts"]["low_activity_candidate"] == 1
    assert section["spatial_interpretation_allowed"] is False
    markdown = build_platform_markdown(case, report)
    assert "Task 3 Fused-Image AI Review Evidence" in markdown
    assert "Boundary candidate count: `3`" in markdown
    rows = _quantification_rows(case)
    task3_row = next(row for row in rows if row["record_type"] == "task3_fused_image_ai_summary")
    assert task3_row["task3_boundary_candidate_count"] == 3
    assert task3_row["task3_evaluated_boundary_candidate_count"] == 3
    assert task3_row["task3_suppressed_boundary_candidate_count"] == 0
    assert task3_row["task2_registration_fusion_compute_ms"] == 72.0
    assert task3_row["task3_clinical_claim_allowed"] is False
    assert task3_row["task3_low_activity_candidate_count"] == 1
    csv_path = tmp_path / "task3_quantification.csv"
    write_quantification_csv(csv_path, rows)
    csv_text = csv_path.read_text(encoding="utf-8")
    assert "task3_evaluated_boundary_candidate_count" in csv_text.splitlines()[0]
    assert "task3_suppressed_boundary_candidate_count" in csv_text.splitlines()[0]
    assert "task3_fused_image_ai_summary" in csv_text


def test_platform_report_keeps_fused_image_evidence_when_video_run_is_latest(tmp_path: Path) -> None:
    source_path = tmp_path / "task2_fused_latest_selection.png"
    Image.fromarray(np.zeros((32, 48, 3), dtype=np.uint8)).save(source_path)
    evidence = _task3_evidence(source_path)
    fusion_run = AnalysisRun(
        run_id="run_task3_fusion_before_video",
        case_id="case_task3_latest_selection",
        status="completed",
        fused_outputs={"fused_image_ai": evidence},
    )
    video_run = AnalysisRun(
        run_id="run_task3_video_latest",
        case_id="case_task3_latest_selection",
        status="completed",
        fused_outputs={
            "video_segmentation_summary": {
                "analysis_scope": "selected_mp4_keyframes_video_signal_segmentation",
                "selected_frame_count": 1,
            }
        },
    )
    case = CaseRecord(
        case_id="case_task3_latest_selection",
        title="Task 3 latest run selection",
        status=CaseStatus.ANALYZED,
        analysis_runs=[fusion_run, video_run],
    )

    report = build_platform_report(case)

    section = report["task3_fused_image_ai"]
    assert section["available"] is True
    assert section["source_run_id"] == "run_task3_fusion_before_video"
    assert section["source_run_selection"] == "latest_run_with_task3_fused_image_ai"


def _task3_evidence(source_path: Path) -> dict[str, object]:
    return {
        "available": True,
        "execution_state": "completed",
        "model_id": "attention_unet_engineering",
        "model_family": "convnext2d_keyframe_segmenter",
        "task_role": "task3_ai_on_task2_fused_image",
        "spatial_interpretation_allowed": False,
        "clinical_claim_allowed": False,
        "input_contract": {
            "schema_version": "osteo-vision-task3-fused-input-v1",
            "contract_path": str(source_path.with_suffix(".json")),
            "contract_sha256": "a" * 64,
            "engineering_input_eligible": True,
            "model_input": {"path": str(source_path), "dimensions": [96, 64]},
            "task2_provenance": {
                "registration_ms": 40.0,
                "gpu_fusion_ms": 32.0,
                "registration_fusion_compute_ms": 72.0,
                "accelerator": "torch_cuda",
            },
        },
        "lesion_evidence": {
            "overlay_path": str(source_path),
            "mask_path": str(source_path),
            "probability_path": str(source_path),
        },
        "boundary_assessment": {
            "schema_version": "osteo-vision-lesion-boundary-assessment-v2",
            "available": True,
            "candidate_count": 3,
            "boundary_type_counts": {
                "signal_candidate_boundary": 2,
                "high_risk_transition_boundary": 0,
                "uncertain_boundary": 1,
            },
            "activity_class_counts": {
                "low_activity_candidate": 1,
                "transition_candidate": 0,
                "high_activity_candidate": 0,
                "unavailable_pending_reviewed_bone_gate": 2,
            },
            "activity_evidence": {
                "available": True,
                "status": "available_for_physician_review",
            },
            "candidates": [
                {
                    "candidate_id": "signal-1",
                    "bbox_xyxy": [4, 5, 20, 25],
                    "score": 0.9,
                    "confidence": 0.88,
                    "review_confidence": 0.8,
                    "boundary_type": "signal_candidate_boundary",
                    "boundary_pixel_count": 32,
                    "boundary_risk_fraction": 0.4,
                    "boundary_uncertainty_fraction": 0.1,
                    "activity_class": "low_activity_candidate",
                    "activity_overlap_fraction": 0.8,
                    "activity_evidence_available": True,
                },
                {
                    "candidate_id": "signal-2",
                    "bbox_xyxy": [24, 5, 40, 25],
                    "score": 0.85,
                    "confidence": 0.83,
                    "review_confidence": 0.75,
                    "boundary_type": "signal_candidate_boundary",
                },
                {
                    "candidate_id": "uncertain-1",
                    "bbox_xyxy": [44, 5, 60, 25],
                    "score": 0.7,
                    "confidence": 0.68,
                    "review_confidence": 0.4,
                    "boundary_type": "uncertain_boundary",
                },
            ],
            "review_priority": "high",
            "spatial_interpretation_allowed": False,
            "physician_review_required": True,
            "clinical_claim_allowed": False,
            "medical_boundary": "Engineering boundary candidates require physician review.",
        },
    }
