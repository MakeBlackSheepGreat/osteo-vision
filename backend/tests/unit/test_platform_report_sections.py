from __future__ import annotations

from backend.src.domains.cases.schemas import CaseRecord
from backend.src.reports.platform_report import build_platform_report
from backend.src.reports.platform_report_sections import (
    artifact_markdown_lines,
    latest_quantification_from_report,
    platform_safety_lines,
    quality_flag_markdown_lines,
    three_d_evidence_markdown_lines,
    three_d_evidence_section_from_run,
    video_signal_markdown_lines,
    video_signal_section_from_run,
)


def test_platform_report_sections_keep_empty_state_and_safety_boundary() -> None:
    case = CaseRecord(case_id="case_report_sections", title="sections")
    report = build_platform_report(case)

    assert latest_quantification_from_report(report) == {}
    assert quality_flag_markdown_lines(case) == ["- No blocking quality flags recorded."]
    assert artifact_markdown_lines(case) == ["- No evidence artifacts recorded."]
    assert "Platform software for research and competition validation" in platform_safety_lines()[0]
    assert report["video_signal_segmentation"]["available"] is False
    assert report["three_d_evidence"]["available"] is False


def test_video_signal_report_section_summarizes_frame_paths() -> None:
    run = {
        "fused_outputs": {
            "video_segmentation_manifest_path": "video_segmentation_manifest.json",
            "video_segmentation_summary": {
                "analysis_scope": "selected_mp4_keyframes_video_signal_segmentation",
                "selected_frame_count": 1,
                "mask_frame_count": 1,
                "risk_frame_count": 1,
                "video_signal_outputs": ["bone_gate_mask", "fluorescence_signal_mask", "risk_mask", "uncertain_mask"],
                "medical_boundary": "physician review required",
            },
            "frame_details": [
                {
                    "frame_index": 3,
                    "timestamp_sec": 1.2,
                    "overlay_path": "overlay.png",
                    "mask_path": "mask.png",
                    "risk_mask_path": "risk.png",
                    "uncertain_mask_path": "uncertain.png",
                    "positive_area_fraction": 0.1,
                    "review_priority": "high",
                    "video_signal_segmentation": {
                        "bone_gate_mask": {"status": "not_available_pending_review"},
                        "risk_mask": {"path": "risk.png"},
                        "uncertain_mask": {"path": "uncertain.png"},
                    },
                }
            ],
        }
    }

    section = video_signal_section_from_run(run)
    lines = video_signal_markdown_lines(section)

    assert section["available"] is True
    assert section["risk_frame_count"] == 1
    assert section["frame_examples"][0]["bone_gate_status"] == "not_available_pending_review"
    assert any("risk.png" in line for line in lines)


def test_three_d_evidence_report_section_keeps_navigation_boundary() -> None:
    run = {
        "fused_outputs": {
            "three_d_evidence": {
                "model_path": "artifacts/models/case_001_mandible.glb",
                "model_file_name": "case_001_mandible.glb",
                "model_source": "Slicer exported model",
                "model_format": "glb",
                "registration_status": "registered",
                "registration_error_mm": 0.8,
                "coordinate_space": "cbct_ras",
                "navigation_ready": True,
                "doctor_review_status": "approved",
                "registration_markups": [{"status": "accepted"}, {"status": "accepted"}],
                "transform_chain": [{"status": "ready"}, {"status": "missing"}],
                "boundary_note": "Reference layer only after physician review.",
            }
        }
    }

    section = three_d_evidence_section_from_run(run)
    lines = three_d_evidence_markdown_lines(section)

    assert section["available"] is True
    assert section["model_available"] is True
    assert section["transform_ready_count"] == 1
    assert section["markup_ready_count"] == 2
    assert any("Navigation ready" in line for line in lines)
    assert any("Reference layer only" in line for line in lines)
